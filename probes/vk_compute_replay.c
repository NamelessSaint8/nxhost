// Replay a gfx_vk_capture.inc v1/v2 dispatch with exact inputs and view formats.
// V2 preserves pool aliases and rebases physical pointers. Raw access requires
// raw_memory_guard.py; uncaptured addresses stop with exit 6, before dereference.
// NDK clang -O2 -Wall -Wextra -Werror vk_compute_replay.c -o vk_compute_replay -lvulkan -landroid
// Arguments: capture-prefix shader.spv output-prefix [pipeline-cache [gx gy gz]]
// DM_REPLAY_REPEAT=N and DM_REPLAY_WARMUP=W add independently reset, GPU-timed
// dispatches. Transfers, pipeline creation and host readback are outside samples.
// DM_REPLAY_REQUIRE_CHANGE=1 rejects captures with no observable storage writes.
// DM_REPLAY_TIME_BARRIER=1 includes the completion barrier, as the host does.
// DM_REPLAY_ROBUST=0/1 controls core buffer robustness for compiler comparisons.
// DM_REPLAY_DYNAMIC_UBO=1 makes all uniform descriptors dynamic; 2 keeps
// binding 0 static, matching NVN's support/driver layout in these captures.
// DM_REPLAY_POOL_AHB=1 imports raw pools with the host's Android allocation path.
#define VK_USE_PLATFORM_ANDROID_KHR
#include <android/hardware_buffer.h>
#include <vulkan/vulkan.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <unistd.h>

#define VK(x) do{VkResult result_=(x);if(result_){fprintf(stderr,"%s: %d\n",#x,result_);exit(2);}}while(0)
#define REQUIRE(x) do{if(!(x)){fprintf(stderr,"invalid replay: %s\n",#x);exit(2);}}while(0)
typedef struct {uint8_t minf,magf,ws,wt,wr,cmp_mode,cmp_func,reduction;float lod_min,lod_max,lod_bias,aniso,border[4];} sampler_parameters;
typedef struct {VkBuffer buf;VkDeviceMemory mem;void *map;VkDeviceSize size,offset;AHardwareBuffer *ahb;} buffer;
typedef struct {
    unsigned binding,type,image,w,h,fmt,view_fmt,bpp,swz[4];size_t size;
    buffer data;VkImage img;VkDeviceMemory memory;VkImageView view;VkSampler sampler;void *before,*expected;unsigned alias;
} resource;
typedef struct {uint64_t guest;size_t size;buffer data;void *before,*expected;} raw_pool;
static VkDevice dev;static VkPhysicalDeviceMemoryProperties memory;
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static void *load(const char *path,size_t *size){
    FILE *f=fopen(path,"rb");if(!f){perror(path);exit(2);}REQUIRE(!fseek(f,0,SEEK_END));long n=ftell(f);REQUIRE(n>0);rewind(f);
    void *p=malloc((size_t)n);REQUIRE(p);REQUIRE(fread(p,1,(size_t)n,f)==(size_t)n);REQUIRE(!fclose(f));*size=(size_t)n;return p;
}
static void save(const char *path,const void *p,size_t size){FILE *f=fopen(path,"wb");if(!f){perror(path);exit(2);}REQUIRE(fwrite(p,1,size,f)==size);REQUIRE(!fclose(f));}
static uint32_t memtype(uint32_t bits,VkMemoryPropertyFlags flags){
    for(uint32_t i=0;i<memory.memoryTypeCount;i++)if((bits&(1u<<i)) && (memory.memoryTypes[i].propertyFlags&flags)==flags)return i;
    REQUIRE(0);return 0;
}
static buffer make_buffer(size_t size){
    buffer b={.size=size};VkBufferCreateInfo ci={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=size,
        .usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT|VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT};
    VK(vkCreateBuffer(dev,&ci,NULL,&b.buf));VkMemoryRequirements need;vkGetBufferMemoryRequirements(dev,b.buf,&need);
    VkMemoryAllocateFlagsInfo flags={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO,.flags=VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT};
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.pNext=&flags,.allocationSize=need.size,.memoryTypeIndex=memtype(need.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)};
    VK(vkAllocateMemory(dev,&ai,NULL,&b.mem));VK(vkBindBufferMemory(dev,b.buf,b.mem,0));VK(vkMapMemory(dev,b.mem,0,VK_WHOLE_SIZE,0,&b.map));return b;
}
// Match pool_zero_copy's AHB usage, dma-buf mapping and dedicated Vulkan import.
// Only raw pools take this route; descriptors keep the existing scratch route.
static buffer make_ahb_pool(size_t size){
    REQUIRE(size&&size<=UINT32_MAX);buffer b={.size=size};
    AHardwareBuffer_Desc desc={(uint32_t)size,1,1,AHARDWAREBUFFER_FORMAT_BLOB,
        AHARDWAREBUFFER_USAGE_CPU_READ_OFTEN|AHARDWAREBUFFER_USAGE_CPU_WRITE_OFTEN|AHARDWAREBUFFER_USAGE_GPU_DATA_BUFFER,0,0,0};
    REQUIRE(!AHardwareBuffer_allocate(&desc,&b.ahb));
    int sockets[2];REQUIRE(!socketpair(AF_UNIX,SOCK_SEQPACKET|SOCK_CLOEXEC,0,sockets));
    REQUIRE(!AHardwareBuffer_sendHandleToUnixSocket(b.ahb,sockets[0]));
    char data[4096],control[CMSG_SPACE(sizeof(int)*16)];struct iovec iov={data,sizeof data};
    struct msghdr msg={.msg_iov=&iov,.msg_iovlen=1,.msg_control=control,.msg_controllen=sizeof control};
    REQUIRE(recvmsg(sockets[1],&msg,0)>=0&&!(msg.msg_flags&MSG_CTRUNC));close(sockets[0]);close(sockets[1]);
    int mapped=0;
    for(struct cmsghdr *c=CMSG_FIRSTHDR(&msg);c;c=CMSG_NXTHDR(&msg,c))if(c->cmsg_level==SOL_SOCKET&&c->cmsg_type==SCM_RIGHTS){
        size_t count=(c->cmsg_len-CMSG_LEN(0))/sizeof(int);int *fds=(int*)CMSG_DATA(c);
        for(size_t i=0;i<count;i++){if(!mapped){b.map=mmap(NULL,size,PROT_READ|PROT_WRITE,MAP_SHARED,fds[i],0);REQUIRE(b.map!=MAP_FAILED);mapped=1;}close(fds[i]);}
    }
    REQUIRE(mapped);
    VkExternalMemoryBufferCreateInfo external={.sType=VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,.handleTypes=VK_EXTERNAL_MEMORY_HANDLE_TYPE_ANDROID_HARDWARE_BUFFER_BIT_ANDROID};
    VkBufferCreateInfo ci={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.pNext=&external,.size=size,
        .usage=VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT|VK_BUFFER_USAGE_UNIFORM_TEXEL_BUFFER_BIT|VK_BUFFER_USAGE_STORAGE_TEXEL_BUFFER_BIT|
               VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_INDEX_BUFFER_BIT|VK_BUFFER_USAGE_VERTEX_BUFFER_BIT|
               VK_BUFFER_USAGE_INDIRECT_BUFFER_BIT|VK_BUFFER_USAGE_SHADER_DEVICE_ADDRESS_BIT};
    VK(vkCreateBuffer(dev,&ci,NULL,&b.buf));
    VkAndroidHardwareBufferPropertiesANDROID properties={.sType=VK_STRUCTURE_TYPE_ANDROID_HARDWARE_BUFFER_PROPERTIES_ANDROID};
    PFN_vkGetAndroidHardwareBufferPropertiesANDROID get_properties=(PFN_vkGetAndroidHardwareBufferPropertiesANDROID)vkGetDeviceProcAddr(dev,"vkGetAndroidHardwareBufferPropertiesANDROID");
    REQUIRE(get_properties);VK(get_properties(dev,b.ahb,&properties));
    uint32_t type=memtype(properties.memoryTypeBits,0);
    printf("AHB pool %zu bytes memory type %u flags %#x\n",size,type,memory.memoryTypes[type].propertyFlags);
    VkMemoryDedicatedAllocateInfo dedicated={.sType=VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO,.buffer=b.buf};
    VkMemoryAllocateFlagsInfo flags={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_FLAGS_INFO,.pNext=&dedicated,.flags=VK_MEMORY_ALLOCATE_DEVICE_ADDRESS_BIT};
    VkImportAndroidHardwareBufferInfoANDROID import={.sType=VK_STRUCTURE_TYPE_IMPORT_ANDROID_HARDWARE_BUFFER_INFO_ANDROID,.pNext=&flags,.buffer=b.ahb};
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.pNext=&import,.allocationSize=properties.allocationSize,.memoryTypeIndex=type};
    VK(vkAllocateMemory(dev,&ai,NULL,&b.mem));VK(vkBindBufferMemory(dev,b.buf,b.mem,0));return b;
}
static void free_buffer(buffer *b){
    if(b->ahb)REQUIRE(!munmap(b->map,b->size));else vkUnmapMemory(dev,b->mem);
    vkDestroyBuffer(dev,b->buf,NULL);vkFreeMemory(dev,b->mem,NULL);if(b->ahb)AHardwareBuffer_release(b->ahb);
}
static VkSamplerAddressMode wrap(unsigned x){
    switch(x){case 1:return VK_SAMPLER_ADDRESS_MODE_REPEAT;case 6:return VK_SAMPLER_ADDRESS_MODE_MIRRORED_REPEAT;
    case 2:case 3:return VK_SAMPLER_ADDRESS_MODE_MIRROR_CLAMP_TO_EDGE;case 4:case 5:return VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_BORDER;default:return VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE;}
}
static void make_sampler(resource *r,const char *prefix){
    char path[2048];snprintf(path,sizeof path,"%s.b%u.sampler.bin",prefix,r->binding);size_t n;sampler_parameters *p=load(path,&n);REQUIRE(n==sizeof *p);
    REQUIRE(!p->reduction); // Unsupported samplers fail explicitly; v1 has no extension chain.
    VkSamplerCreateInfo ci={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=p->magf?VK_FILTER_LINEAR:VK_FILTER_NEAREST,
        .minFilter=p->minf==1||p->minf==3||p->minf==5?VK_FILTER_LINEAR:VK_FILTER_NEAREST,
        .mipmapMode=p->minf==4||p->minf==5?VK_SAMPLER_MIPMAP_MODE_LINEAR:VK_SAMPLER_MIPMAP_MODE_NEAREST,
        .addressModeU=wrap(p->ws),.addressModeV=wrap(p->wt),.addressModeW=wrap(p->wr),.mipLodBias=p->lod_bias,
        .anisotropyEnable=p->aniso>1,.maxAnisotropy=p->aniso>1?p->aniso:1,.compareEnable=p->cmp_mode==1,
        .compareOp=p->cmp_func>=1&&p->cmp_func<=8?(VkCompareOp)(p->cmp_func-1):VK_COMPARE_OP_ALWAYS,
        .minLod=p->lod_min,.maxLod=p->minf<=1?.25f:p->lod_max};
    if(p->border[0]==1&&p->border[1]==1&&p->border[2]==1&&p->border[3]==1)ci.borderColor=VK_BORDER_COLOR_FLOAT_OPAQUE_WHITE;
    else if(!p->border[0]&&!p->border[1]&&!p->border[2]&&p->border[3]==1)ci.borderColor=VK_BORDER_COLOR_FLOAT_OPAQUE_BLACK;
    else {REQUIRE(!p->border[0]&&!p->border[1]&&!p->border[2]&&!p->border[3]);ci.borderColor=VK_BORDER_COLOR_FLOAT_TRANSPARENT_BLACK;}
    VK(vkCreateSampler(dev,&ci,NULL,&r->sampler));free(p);
}
static void make_image(resource *r){
    VkImageCreateInfo ci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.flags=VK_IMAGE_CREATE_MUTABLE_FORMAT_BIT|VK_IMAGE_CREATE_EXTENDED_USAGE_BIT,
        .imageType=VK_IMAGE_TYPE_2D,.format=r->fmt,.extent={r->w,r->h,1},.mipLevels=1,.arrayLayers=1,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,
        .usage=VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT|(r->type==VK_DESCRIPTOR_TYPE_STORAGE_IMAGE?VK_IMAGE_USAGE_STORAGE_BIT:VK_IMAGE_USAGE_SAMPLED_BIT)};
    VK(vkCreateImage(dev,&ci,NULL,&r->img));VkMemoryRequirements need;vkGetImageMemoryRequirements(dev,r->img,&need);
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=need.size,.memoryTypeIndex=memtype(need.memoryTypeBits,0)};
    VK(vkAllocateMemory(dev,&ai,NULL,&r->memory));VK(vkBindImageMemory(dev,r->img,r->memory,0));
    VkImageViewCreateInfo vi={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=r->img,.viewType=VK_IMAGE_VIEW_TYPE_2D,.format=r->view_fmt,
        .components={r->swz[0],r->swz[1],r->swz[2],r->swz[3]},.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};
    VK(vkCreateImageView(dev,&vi,NULL,&r->view));
}
static void barrier(VkCommandBuffer cmd){VkMemoryBarrier b={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_MEMORY_WRITE_BIT|VK_ACCESS_HOST_WRITE_BIT,.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT|VK_ACCESS_HOST_READ_BIT};vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT|VK_PIPELINE_STAGE_HOST_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT|VK_PIPELINE_STAGE_HOST_BIT,0,1,&b,0,NULL,0,NULL);}
static unsigned count_env(const char *key,unsigned fallback){const char *s=getenv(key);if(!s)return fallback;char *end;unsigned long n=strtoul(s,&end,10);REQUIRE(*s&&!*end&&n<=10000);return (unsigned)n;}
static int compare_time(const void *a,const void *b){double x=*(const double*)a,y=*(const double*)b;return (x>y)-(x<y);}
static void submit_wait(VkQueue queue,VkCommandBuffer cmd,VkFence fence){
    VK(vkEndCommandBuffer(cmd));VK(vkResetFences(dev,1,&fence));VkSubmitInfo s={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};
    VK(vkQueueSubmit(queue,1,&s,fence));VK(vkWaitForFences(dev,1,&fence,VK_TRUE,30000000000ull));
}
int main(int argc,char **argv){
    REQUIRE(argc==4||argc==5||argc==8);setvbuf(stdout,NULL,_IOLBF,0);resource resources[32]={0};unsigned nr=0,groups[3]={0};char path[2048],line[512];
    raw_pool pools[16]={0};unsigned npool=0,version=0;int map_binding=-1,log_binding=-1,guard_index=-1,address_binding=-1,owned_map=-1,owned_binding=-1;
    uint64_t owned_guest=0;unsigned owned_flags=0;
    snprintf(path,sizeof path,"%s.tsv",argv[1]);FILE *manifest=fopen(path,"r");if(!manifest){perror(path);return 2;}
    REQUIRE(fgets(line,sizeof line,manifest)&&sscanf(line,"capture %u",&version)==1&&(version==1||version==2));
    while(fgets(line,sizeof line,manifest)){
        char key[32];if(sscanf(line,"dispatch %31s %u %u %u",key,&groups[0],&groups[1],&groups[2])==4)continue;
        if(!strncmp(line,"address_table ",14)){
            unsigned binding;REQUIRE(version==1&&address_binding<0&&sscanf(line,"address_table %u",&binding)==1&&binding==4);
            address_binding=(int)binding;continue;
        }
        if(!strncmp(line,"owned_pool ",11)){
            unsigned mb,pb;unsigned long long guest;
            REQUIRE(version==1&&owned_map<0&&sscanf(line,"owned_pool %u %u %llu %u",&mb,&pb,&guest,&owned_flags)==4&&mb<32&&pb<32&&mb!=pb&&owned_flags<=1);
            owned_map=(int)mb;owned_binding=(int)pb;owned_guest=guest;continue;
        }
        if(!strncmp(line,"global_memory ",14)){
            unsigned binding;char kind[16];REQUIRE(version==2&&sscanf(line,"global_memory %u %15s",&binding,kind)==2);
            if(!strcmp(kind,"map")){REQUIRE(map_binding<0);map_binding=(int)binding;}else{REQUIRE(!strcmp(kind,"log")&&log_binding<0);log_binding=(int)binding;}continue;
        }
        if(!strncmp(line,"pool ",5)){
            unsigned index;unsigned long long guest,size;REQUIRE(version==2&&npool<16&&sscanf(line,"pool %u %llu %llu",&index,&guest,&size)==3&&index==npool&&size&&size<=64*1024*1024&&guest+size>=guest);
            pools[npool++]=(raw_pool){.guest=guest,.size=(size_t)size};continue;
        }
        if(!strncmp(line,"alias ",6)){
            unsigned binding,pool;unsigned long long offset;REQUIRE(version==2&&sscanf(line,"alias %u %u %llu",&binding,&pool,&offset)==3&&pool<npool);
            unsigned i=0;while(i<nr&&resources[i].binding!=binding)i++;REQUIRE(i<nr&&!resources[i].image&&!resources[i].alias&&offset<=pools[pool].size&&resources[i].size<=pools[pool].size-offset);
            resources[i].alias=pool+1;resources[i].data.offset=offset;continue;
        }
        REQUIRE(nr<32);resource *r=&resources[nr];unsigned long long bytes;
        if(sscanf(line,"buffer %u %u %llu",&r->binding,&r->type,&bytes)==3){r->size=(size_t)bytes;REQUIRE(r->size&&r->size<=64*1024*1024);}
        else {REQUIRE(sscanf(line,"image %u %u %u %u %u %u %u %u %u %u %u",&r->binding,&r->type,&r->w,&r->h,&r->fmt,&r->view_fmt,&r->bpp,&r->swz[0],&r->swz[1],&r->swz[2],&r->swz[3])==11);r->image=1;r->size=(size_t)r->w*r->h*r->bpp;REQUIRE(r->size&&r->size<=64*1024*1024);}
        for(unsigned j=0;j<nr;j++)REQUIRE(resources[j].binding!=r->binding);nr++;
    }
    fclose(manifest);REQUIRE(nr&&groups[0]&&groups[1]&&groups[2]);if(argc==8)for(unsigned i=0;i<3;i++){unsigned n=(unsigned)strtoul(argv[5+i],NULL,10);REQUIRE(n&&n<=groups[i]);groups[i]=n;}
    if(map_binding>=0){
        REQUIRE(npool&&nr<32);for(unsigned i=0;i<nr;i++)REQUIRE(resources[i].binding!=30);
        guard_index=(int)nr;resources[nr++]=(resource){.binding=30,.type=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.size=272,.before=calloc(1,272)};REQUIRE(resources[guard_index].before);
    }
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_2};VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};VkInstance inst;VK(vkCreateInstance(&ici,NULL,&inst));
    uint32_t count=1;VkPhysicalDevice pd;VK(vkEnumeratePhysicalDevices(inst,&count,&pd));REQUIRE(count);vkGetPhysicalDeviceMemoryProperties(pd,&memory);
    VkPhysicalDeviceProperties props;vkGetPhysicalDeviceProperties(pd,&props);printf("device %s driver %#x dispatch %u %u %u\n",props.deviceName,props.driverVersion,groups[0],groups[1],groups[2]);
    uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,NULL);VkQueueFamilyProperties *families=calloc(nq,sizeof *families);vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,families);
    uint32_t qf=0;while(qf<nq&&!(families[qf].queueFlags&VK_QUEUE_COMPUTE_BIT))qf++;REQUIRE(qf<nq);uint32_t timestamp_bits=families[qf].timestampValidBits;free(families);float priority=1;
    VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qf,.queueCount=1,.pQueuePriorities=&priority};VkPhysicalDeviceFeatures features;vkGetPhysicalDeviceFeatures(pd,&features);
    const char *robust=getenv("DM_REPLAY_ROBUST");
    if(robust){unsigned enabled=count_env("DM_REPLAY_ROBUST",0);REQUIRE(enabled<=1&&(!enabled||features.robustBufferAccess));features.robustBufferAccess=enabled;}
    printf("core robustBufferAccess %u\n",features.robustBufferAccess);
    unsigned cooperative=count_env("DM_REPLAY_COOPERATIVE",0);REQUIRE(cooperative<=1);
    VkPhysicalDeviceSubgroupSizeControlFeatures subgroup={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_SIZE_CONTROL_FEATURES};
    VkPhysicalDeviceCooperativeMatrixFeaturesKHR matrix={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_COOPERATIVE_MATRIX_FEATURES_KHR,.pNext=&subgroup};
    VkPhysicalDeviceVulkan12Features f12={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES,.pNext=cooperative?&matrix:NULL};
    VkPhysicalDeviceFeatures2 available={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,.pNext=&f12};vkGetPhysicalDeviceFeatures2(pd,&available);
    REQUIRE(f12.bufferDeviceAddress);f12.bufferDeviceAddressCaptureReplay=f12.bufferDeviceAddressMultiDevice=VK_FALSE;
    unsigned ahb_pools=count_env("DM_REPLAY_POOL_AHB",0);REQUIRE(ahb_pools<=1);
    const char *extensions[3];unsigned extension_count=0;
    if(ahb_pools)extensions[extension_count++]=VK_ANDROID_EXTERNAL_MEMORY_ANDROID_HARDWARE_BUFFER_EXTENSION_NAME;
    if(cooperative){
        REQUIRE(matrix.cooperativeMatrix&&subgroup.subgroupSizeControl&&f12.shaderFloat16&&f12.vulkanMemoryModel);
        extensions[extension_count++]=VK_KHR_COOPERATIVE_MATRIX_EXTENSION_NAME;
        extensions[extension_count++]=VK_EXT_SUBGROUP_SIZE_CONTROL_EXTENSION_NAME;
        PFN_vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR get_matrix=(PFN_vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR)vkGetInstanceProcAddr(inst,"vkGetPhysicalDeviceCooperativeMatrixPropertiesKHR");
        REQUIRE(get_matrix);uint32_t n=0;VK(get_matrix(pd,&n,NULL));
        VkCooperativeMatrixPropertiesKHR *tiles=calloc(n,sizeof *tiles);REQUIRE(tiles);
        for(uint32_t i=0;i<n;i++)tiles[i].sType=VK_STRUCTURE_TYPE_COOPERATIVE_MATRIX_PROPERTIES_KHR;
        VK(get_matrix(pd,&n,tiles));int supported=0;
        for(uint32_t i=0;i<n;i++){VkCooperativeMatrixPropertiesKHR *t=&tiles[i];
            if(t->AType==VK_COMPONENT_TYPE_FLOAT16_KHR&&t->BType==VK_COMPONENT_TYPE_FLOAT16_KHR)
                printf("cooperative tile %ux%ux%u C=%u D=%u scope=%u\n",t->MSize,t->NSize,t->KSize,t->CType,t->ResultType,t->scope);
            if(t->AType==VK_COMPONENT_TYPE_FLOAT16_KHR&&t->BType==VK_COMPONENT_TYPE_FLOAT16_KHR&&t->CType==VK_COMPONENT_TYPE_FLOAT16_KHR&&t->ResultType==VK_COMPONENT_TYPE_FLOAT16_KHR&&t->scope==VK_SCOPE_SUBGROUP_KHR){
                printf("F16 cooperative tile %ux%ux%u\n",t->MSize,t->NSize,t->KSize);
                supported|=t->MSize==64&&t->NSize==16&&t->KSize==16&&!t->saturatingAccumulation;
            }
        }free(tiles);REQUIRE(supported);
        VkPhysicalDeviceSubgroupSizeControlProperties sg={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_SUBGROUP_SIZE_CONTROL_PROPERTIES};
        VkPhysicalDeviceProperties2 p2={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2,.pNext=&sg};vkGetPhysicalDeviceProperties2(pd,&p2);
        REQUIRE(sg.minSubgroupSize<=64&&sg.maxSubgroupSize>=64&&(sg.requiredSubgroupSizeStages&VK_SHADER_STAGE_COMPUTE_BIT));
    }
    VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.pNext=&f12,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi,.pEnabledFeatures=&features,
        .enabledExtensionCount=extension_count,.ppEnabledExtensionNames=extensions};VK(vkCreateDevice(pd,&di,NULL,&dev));VkQueue queue;vkGetDeviceQueue(dev,qf,0,&queue);
    for(unsigned i=0;i<npool;i++){
        raw_pool *p=&pools[i];p->data=ahb_pools?make_ahb_pool(p->size):make_buffer(p->size);snprintf(path,sizeof path,"%s.p%u.before.bin",argv[1],i);size_t n;p->before=load(path,&n);REQUIRE(n==p->size);memcpy(p->data.map,p->before,n);
        if(guard_index>=0){VkBufferDeviceAddressInfo info={.sType=VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO,.buffer=p->data.buf};uint64_t a=vkGetBufferDeviceAddress(dev,&info);REQUIRE(a);uint64_t range[2]={a,a+p->size};memcpy((uint8_t*)resources[guard_index].before+16+16*i,range,16);}
    }
    VkDescriptorSetLayoutBinding bindings[32];VkDescriptorPoolSize sizes[32];VkWriteDescriptorSet writes[32];VkDescriptorBufferInfo bi[32];VkDescriptorImageInfo ii[32];
    unsigned dynamic_ubo=count_env("DM_REPLAY_DYNAMIC_UBO",0),ndyn=0;uint32_t offsets[32]={0};REQUIRE(dynamic_ubo<=2);
    for(unsigned i=0;i<nr;i++){
        resource *r=&resources[i];
        if(r->alias){VkDeviceSize off=r->data.offset;r->data=pools[r->alias-1].data;r->data.offset=off;r->data.map=(uint8_t*)r->data.map+off;}
        else r->data=make_buffer(r->size);
        if(!r->before){snprintf(path,sizeof path,"%s.b%u.before.bin",argv[1],r->binding);size_t n;r->before=load(path,&n);REQUIRE(n==r->size);}
        if(r->alias)REQUIRE(!memcmp(r->data.map,r->before,r->size));
        if((int)r->binding==map_binding){
            REQUIRE(r->size==4096*32&&!r->alias);uint64_t *table=r->before;
            for(unsigned k=0;k<4096;k++){
                table[k*4+2]=0;for(unsigned j=0;j<npool;j++)if(table[k*4]==pools[j].guest&&table[k*4+1]==pools[j].guest+pools[j].size){
                    VkBufferDeviceAddressInfo info={.sType=VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO,.buffer=pools[j].data.buf};table[k*4+2]=vkGetBufferDeviceAddress(dev,&info)-pools[j].guest;
                }
            }
        }
        memcpy(r->data.map,r->before,r->size);
        VkDescriptorType dtype=r->type;
        if(dynamic_ubo&&dtype==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER&&(dynamic_ubo==1||r->binding!=0)){dtype=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC;ndyn++;}
        bindings[i]=(VkDescriptorSetLayoutBinding){.binding=r->binding,.descriptorType=dtype,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};sizes[i]=(VkDescriptorPoolSize){dtype,1};
        writes[i]=(VkWriteDescriptorSet){.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstBinding=r->binding,.descriptorCount=1,.descriptorType=dtype};
        if(r->image){make_image(r);if(r->type==VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER)make_sampler(r,argv[1]);ii[i]=(VkDescriptorImageInfo){r->sampler,r->view,VK_IMAGE_LAYOUT_GENERAL};writes[i].pImageInfo=&ii[i];}
        else{REQUIRE(r->type==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER||r->type==VK_DESCRIPTOR_TYPE_STORAGE_BUFFER);bi[i]=(VkDescriptorBufferInfo){r->data.buf,r->data.offset,r->size};writes[i].pBufferInfo=&bi[i];}
    }
    // Self-contained descriptor-vs-physical-address diagnostic. The shader gets
    // addresses only for these four owned SSBO allocations, never guest pointers.
    // Keep real v2 captures on their existing per-access guarded contract.
    if(address_binding>=0){
        REQUIRE(version==1&&nr==5);resource *table=NULL;uint32_t ranges[16]={0};
        for(unsigned i=0;i<nr;i++){
            resource *r=&resources[i];REQUIRE(!r->image&&!r->alias&&r->type==VK_DESCRIPTOR_TYPE_STORAGE_BUFFER&&r->binding<=4&&r->size<=UINT32_MAX);
            if(r->binding==4){table=r;continue;}
            VkBufferDeviceAddressInfo info={.sType=VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO,.buffer=r->data.buf};
            uint64_t address=vkGetBufferDeviceAddress(dev,&info);REQUIRE(address);
            ranges[r->binding*4]=(uint32_t)address;ranges[r->binding*4+1]=(uint32_t)(address>>32);ranges[r->binding*4+2]=(uint32_t)r->size;
        }
        REQUIRE(table&&table->size==sizeof ranges);memcpy(table->before,ranges,sizeof ranges);memcpy(table->data.map,ranges,sizeof ranges);
    }
    if(owned_map>=0){
        REQUIRE(version==1&&address_binding<0);resource *table=NULL,*backing=NULL;
        for(unsigned i=0;i<nr;i++){
            if(resources[i].binding==(unsigned)owned_map)table=&resources[i];
            if(resources[i].binding==(unsigned)owned_binding)backing=&resources[i];
        }
        REQUIRE(table&&backing&&!table->image&&!backing->image&&!table->alias&&!backing->alias&&table->type==VK_DESCRIPTOR_TYPE_STORAGE_BUFFER&&backing->type==VK_DESCRIPTOR_TYPE_STORAGE_BUFFER&&table->size==4096*32&&owned_guest+backing->size>owned_guest);
        VkBufferDeviceAddressInfo info={.sType=VK_STRUCTURE_TYPE_BUFFER_DEVICE_ADDRESS_INFO,.buffer=backing->data.buf};uint64_t address=vkGetBufferDeviceAddress(dev,&info);REQUIRE(address);
        uint64_t *words=table->before;memset(words,0,table->size);
        for(unsigned i=1;i<4096;i++)words[i*4]=UINT64_MAX;
        words[4]=owned_guest;words[5]=owned_guest+backing->size;words[6]=address-owned_guest;words[7]=owned_flags;
        memcpy(table->data.map,table->before,table->size);
    }
    VkDescriptorSetLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=nr,.pBindings=bindings};VkDescriptorSetLayout dsl;VK(vkCreateDescriptorSetLayout(dev,&li,NULL,&dsl));
    VkPipelineLayoutCreateInfo pli={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&dsl};VkPipelineLayout layout;VK(vkCreatePipelineLayout(dev,&pli,NULL,&layout));
    VkDescriptorPoolCreateInfo dpi={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=1,.poolSizeCount=nr,.pPoolSizes=sizes};VkDescriptorPool pool;VK(vkCreateDescriptorPool(dev,&dpi,NULL,&pool));VkDescriptorSetAllocateInfo sai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&dsl};VkDescriptorSet set;VK(vkAllocateDescriptorSets(dev,&sai,&set));for(unsigned i=0;i<nr;i++)writes[i].dstSet=set;vkUpdateDescriptorSets(dev,nr,writes,0,NULL);
    size_t shader_size;void *shader=load(argv[2],&shader_size);REQUIRE(!(shader_size%4));
    if(guard_index>=0){int marked=0;uint32_t *w=shader;for(size_t i=5;i<shader_size/4;){unsigned n=w[i]>>16;REQUIRE(n&&i+n<=shader_size/4);if((w[i]&65535)==5&&n>2&&!strncmp((char*)(w+i+2),"dm_replay_raw_guard_v1",(n-2)*4))marked=1;i+=n;}REQUIRE(marked);}
    VkShaderModuleCreateInfo sci={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=shader_size,.pCode=shader};VkShaderModule module;VK(vkCreateShaderModule(dev,&sci,NULL,&module));free(shader);
    size_t cache_size=0;void *cache_data=NULL;if(argc>=5&&strcmp(argv[4],"-"))cache_data=load(argv[4],&cache_size);VkPipelineCacheCreateInfo pci={.sType=VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO,.initialDataSize=cache_size,.pInitialData=cache_data};VkPipelineCache cache;VK(vkCreatePipelineCache(dev,&pci,NULL,&cache));free(cache_data);
    VkPipelineShaderStageRequiredSubgroupSizeCreateInfo required_subgroup={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_REQUIRED_SUBGROUP_SIZE_CREATE_INFO,.requiredSubgroupSize=64};
    VkComputePipelineCreateInfo ci={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,.stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.pNext=cooperative?&required_subgroup:NULL,.stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=module,.pName="main"},.layout=layout};VkPipeline pipeline;double start=now();VK(vkCreateComputePipelines(dev,cache,1,&ci,NULL,&pipeline));printf("pipeline %.2f ms\n",(now()-start)*1000);
    VkCommandPoolCreateInfo cpi={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=qf};VkCommandPool cp;VK(vkCreateCommandPool(dev,&cpi,NULL,&cp));VkCommandBufferAllocateInfo cai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=cp,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};VkCommandBuffer cmd;VK(vkAllocateCommandBuffers(dev,&cai,&cmd));VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};VK(vkBeginCommandBuffer(cmd,&begin));
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(!r->image)continue;VkImageMemoryBarrier b={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,.newLayout=VK_IMAGE_LAYOUT_GENERAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=r->img,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&b);VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={r->w,r->h,1}};vkCmdCopyBufferToImage(cmd,r->data.buf,r->img,VK_IMAGE_LAYOUT_GENERAL,1,&copy);}
    barrier(cmd);vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&set,ndyn,offsets);vkCmdDispatch(cmd,groups[0],groups[1],groups[2]);barrier(cmd);
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(!r->image||r->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE)continue;VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={r->w,r->h,1}};vkCmdCopyImageToBuffer(cmd,r->img,VK_IMAGE_LAYOUT_GENERAL,r->data.buf,1,&copy);}
    barrier(cmd);VK(vkEndCommandBuffer(cmd));VkFenceCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VkFence fence;VK(vkCreateFence(dev,&fi,NULL,&fence));VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};start=now();VK(vkQueueSubmit(queue,1,&submit,fence));VK(vkWaitForFences(dev,1,&fence,VK_TRUE,10000000000ull));printf("submit and readback %.2f ms\n",(now()-start)*1000);
    if(guard_index>=0&&*(uint32_t*)resources[guard_index].data.map){fprintf(stderr,"raw replay reached %u uncaptured physical accesses\n",*(uint32_t*)resources[guard_index].data.map);return 6;}
    unsigned changed_storage=0;
    for(unsigned i=0;i<npool;i++){
        raw_pool *p=&pools[i];snprintf(path,sizeof path,"%s.p%u.after.bin",argv[3],i);save(path,p->data.map,p->size);
        p->expected=malloc(p->size);REQUIRE(p->expected);memcpy(p->expected,p->data.map,p->size);changed_storage+=memcmp(p->before,p->expected,p->size)!=0;
        snprintf(path,sizeof path,"%s.p%u.after.bin",argv[1],i);size_t n;void *captured=load(path,&n);REQUIRE(n==p->size);
        size_t differences=0;for(size_t j=0;j<n;j++)differences+=((uint8_t*)captured)[j]!=((uint8_t*)p->data.map)[j];free(captured);
        printf("pool %u: %zu changed bytes vs capture\n",i,differences);
        if(differences&&!count_env("DM_REPLAY_ALLOW_DIFFERENCE",0))return 5;
    }
    if(version==2)for(unsigned i=0;i<nr;i++){
        resource *r=&resources[i];if(r->alias || (int)i==guard_index || (int)r->binding==map_binding || (int)r->binding==log_binding || (r->type!=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER&&r->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE))continue;
        snprintf(path,sizeof path,"%s.b%u.after.bin",argv[1],r->binding);FILE *f=fopen(path,"rb");if(!f)continue;fclose(f);
        size_t n;void *captured=load(path,&n);REQUIRE(n==r->size);size_t differences=0;
        for(size_t j=0;j<n;j++)differences+=((uint8_t*)captured)[j]!=((uint8_t*)r->data.map)[j];free(captured);
        printf("binding %u: %zu changed bytes vs capture\n",r->binding,differences);if(differences&&!count_env("DM_REPLAY_ALLOW_DIFFERENCE",0))return 5;
    }
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(r->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE&&r->type!=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER)continue;snprintf(path,sizeof path,"%s.b%u.after.bin",argv[3],r->binding);save(path,r->data.map,r->size);printf("saved binding %u: %zu bytes\n",r->binding,r->size);r->expected=malloc(r->size);REQUIRE(r->expected);memcpy(r->expected,r->data.map,r->size);changed_storage+=memcmp(r->before,r->expected,r->size)!=0;}
    printf("observable storage writes: %u changed buffers/images\n",changed_storage);
    if(count_env("DM_REPLAY_REQUIRE_CHANGE",0)&&!changed_storage){fprintf(stderr,"no observable storage writes: output equivalence would be inconclusive\n");return 4;}
    unsigned repeat=count_env("DM_REPLAY_REPEAT",0),warmup=count_env("DM_REPLAY_WARMUP",3);
    if(repeat){
        REQUIRE(timestamp_bits&&props.limits.timestampPeriod>0);
        VkQueryPoolCreateInfo qci={.sType=VK_STRUCTURE_TYPE_QUERY_POOL_CREATE_INFO,.queryType=VK_QUERY_TYPE_TIMESTAMP,.queryCount=2};VkQueryPool queries;VK(vkCreateQueryPool(dev,&qci,NULL,&queries));
        double *times=calloc(repeat,sizeof *times);REQUIRE(times);
        for(unsigned iteration=0;iteration<warmup+repeat;iteration++){
            // Restore every input, including writable resources. Separate setup
            // submission prevents uploads from entering the dispatch's timestamps.
            for(unsigned i=0;i<npool;i++)memcpy(pools[i].data.map,pools[i].before,pools[i].size);
            for(unsigned i=0;i<nr;i++)if(!resources[i].alias)memcpy(resources[i].data.map,resources[i].before,resources[i].size);
            VK(vkResetCommandBuffer(cmd,0));VK(vkBeginCommandBuffer(cmd,&begin));barrier(cmd);
            for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(!r->image)continue;VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={r->w,r->h,1}};vkCmdCopyBufferToImage(cmd,r->data.buf,r->img,VK_IMAGE_LAYOUT_GENERAL,1,&copy);}
            barrier(cmd);submit_wait(queue,cmd,fence);
            VK(vkResetCommandBuffer(cmd,0));VK(vkBeginCommandBuffer(cmd,&begin));vkCmdResetQueryPool(cmd,queries,0,2);
            vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&set,ndyn,offsets);
            vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,queries,0);vkCmdDispatch(cmd,groups[0],groups[1],groups[2]);
            int time_barrier=count_env("DM_REPLAY_TIME_BARRIER",0);
            if(time_barrier)barrier(cmd);
            vkCmdWriteTimestamp(cmd,VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT,queries,1);
            if(!time_barrier)barrier(cmd);
            for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(!r->image||r->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE)continue;VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={r->w,r->h,1}};vkCmdCopyImageToBuffer(cmd,r->img,VK_IMAGE_LAYOUT_GENERAL,r->data.buf,1,&copy);}
            barrier(cmd);submit_wait(queue,cmd,fence);
            uint64_t ticks[2];VK(vkGetQueryPoolResults(dev,queries,0,2,sizeof ticks,ticks,sizeof ticks[0],VK_QUERY_RESULT_64_BIT|VK_QUERY_RESULT_WAIT_BIT));
            uint64_t mask=timestamp_bits==64?UINT64_MAX:((1ull<<timestamp_bits)-1);double ms=((ticks[1]-ticks[0])&mask)*props.limits.timestampPeriod/1e6;
            for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if((int)r->binding!=log_binding&&r->expected&&memcmp(r->expected,r->data.map,r->size)){fprintf(stderr,"unstable replay output: binding %u iteration %u\n",r->binding,iteration);return 3;}}
            for(unsigned i=0;i<npool;i++)if(memcmp(pools[i].expected,pools[i].data.map,pools[i].size)){fprintf(stderr,"unstable replay pool %u iteration %u\n",i,iteration);return 3;}
            if(iteration>=warmup)times[iteration-warmup]=ms;
        }
        double *sorted=malloc(repeat*sizeof *sorted);REQUIRE(sorted);memcpy(sorted,times,repeat*sizeof *times);qsort(sorted,repeat,sizeof *sorted,compare_time);
        printf("{\"type\":\"gpu_benchmark\",\"warmup\":%u,\"samples\":%u,\"changed_storage\":%u,\"median_ms\":%.6f,\"p95_ms\":%.6f,\"samples_ms\":[",warmup,repeat,changed_storage,sorted[repeat/2],sorted[((repeat*95+99)/100)-1]);
        for(unsigned i=0;i<repeat;i++)printf("%s%.6f",i?",":"",times[i]);puts("]}");free(times);free(sorted);vkDestroyQueryPool(dev,queries,NULL);
    }
    VK(vkGetPipelineCacheData(dev,cache,&cache_size,NULL));cache_data=malloc(cache_size);REQUIRE(cache_data);VK(vkGetPipelineCacheData(dev,cache,&cache_size,cache_data));snprintf(path,sizeof path,"%s.cache.bin",argv[3]);save(path,cache_data,cache_size);free(cache_data);
    VK(vkDeviceWaitIdle(dev));vkDestroyFence(dev,fence,NULL);vkDestroyCommandPool(dev,cp,NULL);vkDestroyPipeline(dev,pipeline,NULL);vkDestroyShaderModule(dev,module,NULL);vkDestroyPipelineCache(dev,cache,NULL);vkDestroyDescriptorPool(dev,pool,NULL);vkDestroyPipelineLayout(dev,layout,NULL);vkDestroyDescriptorSetLayout(dev,dsl,NULL);
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];free(r->before);free(r->expected);if(r->sampler)vkDestroySampler(dev,r->sampler,NULL);if(r->view)vkDestroyImageView(dev,r->view,NULL);if(r->img)vkDestroyImage(dev,r->img,NULL);if(r->memory)vkFreeMemory(dev,r->memory,NULL);if(!r->alias)free_buffer(&r->data);}
    for(unsigned i=0;i<npool;i++){raw_pool *p=&pools[i];free(p->before);free(p->expected);free_buffer(&p->data);}
    vkDestroyDevice(dev,NULL);vkDestroyInstance(inst,NULL);return 0;
}
