// Replay a gfx_vk_capture.inc v1 dispatch, with exact raw inputs and view formats.
// NDK clang -O2 -Wall -Wextra -Werror vk_compute_replay.c -o vk_compute_replay -lvulkan
// Arguments: capture-prefix shader.spv output-prefix [pipeline-cache [gx gy gz]]
#include <vulkan/vulkan.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#define VK(x) do{VkResult result_=(x);if(result_){fprintf(stderr,"%s: %d\n",#x,result_);exit(2);}}while(0)
#define REQUIRE(x) do{if(!(x)){fprintf(stderr,"invalid replay: %s\n",#x);exit(2);}}while(0)
typedef struct {uint8_t minf,magf,ws,wt,wr,cmp_mode,cmp_func,reduction;float lod_min,lod_max,lod_bias,aniso,border[4];} sampler_parameters;
typedef struct {VkBuffer buf;VkDeviceMemory mem;void *map;VkDeviceSize size;} buffer;
typedef struct {
    unsigned binding,type,image,w,h,fmt,view_fmt,bpp,swz[4];size_t size;
    buffer data;VkImage img;VkDeviceMemory memory;VkImageView view;VkSampler sampler;
} resource;
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
        .usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    VK(vkCreateBuffer(dev,&ci,NULL,&b.buf));VkMemoryRequirements need;vkGetBufferMemoryRequirements(dev,b.buf,&need);
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=need.size,.memoryTypeIndex=memtype(need.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)};
    VK(vkAllocateMemory(dev,&ai,NULL,&b.mem));VK(vkBindBufferMemory(dev,b.buf,b.mem,0));VK(vkMapMemory(dev,b.mem,0,VK_WHOLE_SIZE,0,&b.map));return b;
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
int main(int argc,char **argv){
    REQUIRE(argc==4||argc==5||argc==8);setvbuf(stdout,NULL,_IOLBF,0);resource resources[32]={0};unsigned nr=0,groups[3]={0};char path[2048],line[512];
    snprintf(path,sizeof path,"%s.tsv",argv[1]);FILE *manifest=fopen(path,"r");if(!manifest){perror(path);return 2;}
    REQUIRE(fgets(line,sizeof line,manifest)&&!strcmp(line,"capture 1\n"));
    while(fgets(line,sizeof line,manifest)){
        char key[32];if(sscanf(line,"dispatch %31s %u %u %u",key,&groups[0],&groups[1],&groups[2])==4)continue;
        REQUIRE(nr<32);resource *r=&resources[nr];unsigned long long bytes;
        if(sscanf(line,"buffer %u %u %llu",&r->binding,&r->type,&bytes)==3){r->size=(size_t)bytes;REQUIRE(r->size&&r->size<=64*1024*1024);}
        else {REQUIRE(sscanf(line,"image %u %u %u %u %u %u %u %u %u %u %u",&r->binding,&r->type,&r->w,&r->h,&r->fmt,&r->view_fmt,&r->bpp,&r->swz[0],&r->swz[1],&r->swz[2],&r->swz[3])==11);r->image=1;r->size=(size_t)r->w*r->h*r->bpp;REQUIRE(r->size&&r->size<=64*1024*1024);}
        for(unsigned j=0;j<nr;j++)REQUIRE(resources[j].binding!=r->binding);nr++;
    }
    fclose(manifest);REQUIRE(nr&&groups[0]&&groups[1]&&groups[2]);if(argc==8)for(unsigned i=0;i<3;i++){unsigned n=(unsigned)strtoul(argv[5+i],NULL,10);REQUIRE(n&&n<=groups[i]);groups[i]=n;}
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_2};VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};VkInstance inst;VK(vkCreateInstance(&ici,NULL,&inst));
    uint32_t count=1;VkPhysicalDevice pd;VK(vkEnumeratePhysicalDevices(inst,&count,&pd));REQUIRE(count);vkGetPhysicalDeviceMemoryProperties(pd,&memory);
    VkPhysicalDeviceProperties props;vkGetPhysicalDeviceProperties(pd,&props);printf("device %s driver %#x dispatch %u %u %u\n",props.deviceName,props.driverVersion,groups[0],groups[1],groups[2]);
    uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,NULL);VkQueueFamilyProperties *families=calloc(nq,sizeof *families);vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,families);
    uint32_t qf=0;while(qf<nq&&!(families[qf].queueFlags&VK_QUEUE_COMPUTE_BIT))qf++;free(families);REQUIRE(qf<nq);float priority=1;
    VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qf,.queueCount=1,.pQueuePriorities=&priority};VkPhysicalDeviceFeatures features;vkGetPhysicalDeviceFeatures(pd,&features);
    VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi,.pEnabledFeatures=&features};VK(vkCreateDevice(pd,&di,NULL,&dev));VkQueue queue;vkGetDeviceQueue(dev,qf,0,&queue);
    VkDescriptorSetLayoutBinding bindings[32];VkDescriptorPoolSize sizes[32];VkWriteDescriptorSet writes[32];VkDescriptorBufferInfo bi[32];VkDescriptorImageInfo ii[32];
    for(unsigned i=0;i<nr;i++){
        resource *r=&resources[i];r->data=make_buffer(r->size);snprintf(path,sizeof path,"%s.b%u.before.bin",argv[1],r->binding);size_t n;void *bytes=load(path,&n);REQUIRE(n==r->size);memcpy(r->data.map,bytes,n);free(bytes);
        bindings[i]=(VkDescriptorSetLayoutBinding){.binding=r->binding,.descriptorType=r->type,.descriptorCount=1,.stageFlags=VK_SHADER_STAGE_COMPUTE_BIT};sizes[i]=(VkDescriptorPoolSize){r->type,1};
        writes[i]=(VkWriteDescriptorSet){.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstBinding=r->binding,.descriptorCount=1,.descriptorType=r->type};
        if(r->image){make_image(r);if(r->type==VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER)make_sampler(r,argv[1]);ii[i]=(VkDescriptorImageInfo){r->sampler,r->view,VK_IMAGE_LAYOUT_GENERAL};writes[i].pImageInfo=&ii[i];}
        else{REQUIRE(r->type==VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER||r->type==VK_DESCRIPTOR_TYPE_STORAGE_BUFFER);bi[i]=(VkDescriptorBufferInfo){r->data.buf,0,r->size};writes[i].pBufferInfo=&bi[i];}
    }
    VkDescriptorSetLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=nr,.pBindings=bindings};VkDescriptorSetLayout dsl;VK(vkCreateDescriptorSetLayout(dev,&li,NULL,&dsl));
    VkPipelineLayoutCreateInfo pli={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&dsl};VkPipelineLayout layout;VK(vkCreatePipelineLayout(dev,&pli,NULL,&layout));
    VkDescriptorPoolCreateInfo dpi={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=1,.poolSizeCount=nr,.pPoolSizes=sizes};VkDescriptorPool pool;VK(vkCreateDescriptorPool(dev,&dpi,NULL,&pool));VkDescriptorSetAllocateInfo sai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&dsl};VkDescriptorSet set;VK(vkAllocateDescriptorSets(dev,&sai,&set));for(unsigned i=0;i<nr;i++)writes[i].dstSet=set;vkUpdateDescriptorSets(dev,nr,writes,0,NULL);
    size_t shader_size;void *shader=load(argv[2],&shader_size);REQUIRE(!(shader_size%4));VkShaderModuleCreateInfo sci={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=shader_size,.pCode=shader};VkShaderModule module;VK(vkCreateShaderModule(dev,&sci,NULL,&module));free(shader);
    size_t cache_size=0;void *cache_data=NULL;if(argc>=5&&strcmp(argv[4],"-"))cache_data=load(argv[4],&cache_size);VkPipelineCacheCreateInfo pci={.sType=VK_STRUCTURE_TYPE_PIPELINE_CACHE_CREATE_INFO,.initialDataSize=cache_size,.pInitialData=cache_data};VkPipelineCache cache;VK(vkCreatePipelineCache(dev,&pci,NULL,&cache));free(cache_data);
    VkComputePipelineCreateInfo ci={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,.stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=module,.pName="main"},.layout=layout};VkPipeline pipeline;double start=now();VK(vkCreateComputePipelines(dev,cache,1,&ci,NULL,&pipeline));printf("pipeline %.2f ms\n",(now()-start)*1000);
    VkCommandPoolCreateInfo cpi={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=qf};VkCommandPool cp;VK(vkCreateCommandPool(dev,&cpi,NULL,&cp));VkCommandBufferAllocateInfo cai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=cp,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};VkCommandBuffer cmd;VK(vkAllocateCommandBuffers(dev,&cai,&cmd));VkCommandBufferBeginInfo begin={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};VK(vkBeginCommandBuffer(cmd,&begin));
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(!r->image)continue;VkImageMemoryBarrier b={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.dstAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,.newLayout=VK_IMAGE_LAYOUT_GENERAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=r->img,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,1,0,1}};vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&b);VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={r->w,r->h,1}};vkCmdCopyBufferToImage(cmd,r->data.buf,r->img,VK_IMAGE_LAYOUT_GENERAL,1,&copy);}
    barrier(cmd);vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&set,0,NULL);vkCmdDispatch(cmd,groups[0],groups[1],groups[2]);barrier(cmd);
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(!r->image||r->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE)continue;VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={r->w,r->h,1}};vkCmdCopyImageToBuffer(cmd,r->img,VK_IMAGE_LAYOUT_GENERAL,r->data.buf,1,&copy);}
    barrier(cmd);VK(vkEndCommandBuffer(cmd));VkFenceCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VkFence fence;VK(vkCreateFence(dev,&fi,NULL,&fence));VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};start=now();VK(vkQueueSubmit(queue,1,&submit,fence));VK(vkWaitForFences(dev,1,&fence,VK_TRUE,10000000000ull));printf("submit and readback %.2f ms\n",(now()-start)*1000);
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(r->type!=VK_DESCRIPTOR_TYPE_STORAGE_IMAGE&&r->type!=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER)continue;snprintf(path,sizeof path,"%s.b%u.after.bin",argv[3],r->binding);save(path,r->data.map,r->size);printf("saved binding %u: %zu bytes\n",r->binding,r->size);}
    VK(vkGetPipelineCacheData(dev,cache,&cache_size,NULL));cache_data=malloc(cache_size);REQUIRE(cache_data);VK(vkGetPipelineCacheData(dev,cache,&cache_size,cache_data));snprintf(path,sizeof path,"%s.cache.bin",argv[3]);save(path,cache_data,cache_size);free(cache_data);
    VK(vkDeviceWaitIdle(dev));vkDestroyFence(dev,fence,NULL);vkDestroyCommandPool(dev,cp,NULL);vkDestroyPipeline(dev,pipeline,NULL);vkDestroyShaderModule(dev,module,NULL);vkDestroyPipelineCache(dev,cache,NULL);vkDestroyDescriptorPool(dev,pool,NULL);vkDestroyPipelineLayout(dev,layout,NULL);vkDestroyDescriptorSetLayout(dev,dsl,NULL);
    for(unsigned i=0;i<nr;i++){resource *r=&resources[i];if(r->sampler)vkDestroySampler(dev,r->sampler,NULL);if(r->view)vkDestroyImageView(dev,r->view,NULL);if(r->img)vkDestroyImage(dev,r->img,NULL);if(r->memory)vkFreeMemory(dev,r->memory,NULL);vkUnmapMemory(dev,r->data.mem);vkDestroyBuffer(dev,r->data.buf,NULL);vkFreeMemory(dev,r->data.mem,NULL);}
    vkDestroyDevice(dev,NULL);vkDestroyInstance(inst,NULL);return 0;
}
