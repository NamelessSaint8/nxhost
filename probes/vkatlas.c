// Compressed virtual-atlas storage proof. Reuses bounded Vulkan helpers; the
// prototype samples explicitly through a page table and is not a game fallback.
#define main bounded_nvn2_main
#include "vknvn2.c"
#undef main
#define WIDTH 8192u
#define LAYERS 68u
#define LEVELS 14u
#define TILE 128u
static uint32_t mip_base[LEVELS], page_count;
static unsigned pages_at(unsigned mip) { unsigned w = WIDTH >> mip; if (!w) w = 1; return (w+TILE-1)/TILE; }
typedef struct { float u,v,lod; uint32_t layer; } Query;
static const float colors[4][4] = {{2,0,0,1},{0,1,0,1},{0,0,1,1},{0,0,0,1}};
static const float *reference_fetch(int x,int y,unsigned mip,unsigned layer,const uint32_t *pages) {
    int w=(int)(WIDTH>>mip);if(!w)w=1;
    if(x<0)x=0;if(y<0)y=0;if(x>=w)x=w-1;if(y>=w)y=w-1;
    unsigned tiles=pages_at(mip),index=mip_base[mip]+(layer*tiles+(unsigned)y/TILE)*tiles+(unsigned)x/TILE;
    return colors[pages[index]];
}
static void reference(Query q,const uint32_t *pages,float result[4]) {
    float lod=fminf(fmaxf(q.lod,0),13),weight=lod-floorf(lod);unsigned low=(unsigned)floorf(lod);
    memset(result,0,16);
    for(unsigned m=0;m<2;m++) {
        unsigned mip=low+m;if(mip>=LEVELS)mip=LEVELS-1;
        unsigned width=WIDTH>>mip;if(!width)width=1;
        float px=q.u*width-.5f,py=q.v*width-.5f,fx=px-floorf(px),fy=py-floorf(py);
        int x=(int)floorf(px),y=(int)floorf(py);
        for(int dy=0;dy<2;dy++)for(int dx=0;dx<2;dx++) {
            float w=(m?weight:1-weight)*(dx?fx:1-fx)*(dy?fy:1-fy);
            const float *color=reference_fetch(x+dx,y+dy,mip,q.layer,pages);
            for(unsigned c=0;c<4;c++)result[c]+=w*color[c];
        }
    }
}
static void query_requirements(void) {
    const struct {VkFormat f;const char *name;} formats[]={{VK_FORMAT_BC6H_UFLOAT_BLOCK,"BC6H"},{VK_FORMAT_ASTC_4x4_UNORM_BLOCK,"ASTC4x4"},{VK_FORMAT_ASTC_8x8_SRGB_BLOCK,"ASTC8x8s"}};
    for(unsigned f=0;f<3;f++) {
        VkImageCreateInfo ci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=formats[f].f,.extent={WIDTH,WIDTH,1},.mipLevels=LEVELS,.arrayLayers=LAYERS,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,.usage=VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_SAMPLED_BIT,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
        VkImage im;VkResult r=vkCreateImage(dev,&ci,NULL,&im);
        if(r){printf("dense %s create-image result %d (no memory allocation attempted)\n",formats[f].name,r);continue;}
        VkMemoryRequirements req;vkGetImageMemoryRequirements(dev,im,&req);
        printf("dense %s %ux%ux%u levels=%u requires=%llu bytes (%.1f MiB), not allocated\n",formats[f].name,WIDTH,WIDTH,LAYERS,LEVELS,(unsigned long long)req.size,req.size/1048576.0);
        vkDestroyImage(dev,im,NULL);
    }
}
static void atlas_test(const char *root) {
    for(unsigned mip=0;mip<LEVELS;mip++){mip_base[mip]=page_count;unsigned tiles=pages_at(mip);page_count+=tiles*tiles*LAYERS;}
    Buffer pages=buffer((VkDeviceSize)page_count*4,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
    for(unsigned mip=0;mip<LEVELS;mip++){unsigned tiles=pages_at(mip);for(unsigned layer=0;layer<LAYERS;layer++)for(unsigned y=0;y<tiles;y++)for(unsigned x=0;x<tiles;x++)((uint32_t*)pages.map)[mip_base[mip]+(layer*tiles+y)*tiles+x]=(x+2*y+layer+mip)%4;}
    // Interior, horizontal/vertical/corner seams, fractional LOD, array layers,
    // mip tail and clamp-to-edge. Two coordinates alias the same physical tile.
    Query qs[]={{.001f,.001f,0,0},{128.f/WIDTH,.001f,0,0},{.001f,128.f/WIDTH,0,0},{128.f/WIDTH,128.f/WIDTH,0,0},{128.f/WIDTH,128.f/WIDTH,.5f,0},{.61f,.33f,2.35f,67},{.1f,.7f,8.75f,31},{.5f,.5f,13,67},{-1,-1,0,0},{2,2,0,67},{4*128.f/WIDTH+.001f,.001f,0,0}};
    unsigned n=sizeof qs/sizeof*qs;
    Buffer queries=buffer(sizeof qs,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT),results=buffer(n*16,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT),upload=buffer(4*TILE*TILE,VK_BUFFER_USAGE_TRANSFER_SRC_BIT);
    memcpy(queries.map,qs,sizeof qs);
    for(unsigned tile=0;tile<4;tile++) {
        uint8_t block[16]={3};
        for(unsigned endpoint=0;endpoint<2;endpoint++)for(unsigned c=0;c<3;c++) {unsigned value=c==tile?(c==0?528:495):0;for(unsigned bit=0;bit<10;bit++)if(value>>bit&1){unsigned pos=5+(endpoint*3+c)*10+bit;block[pos/8]|=(uint8_t)(1u<<(pos%8));}}
        for(unsigned off=tile*TILE*TILE;off<(tile+1)*TILE*TILE;off+=16)memcpy((uint8_t*)upload.map+off,block,16);
    }
    Image cache=image(VK_FORMAT_BC6H_UFLOAT_BLOCK,TILE,TILE,4,1,VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_SAMPLED_BIT);
    VkDescriptorPool pool=descriptor_pool();VkDescriptorSetLayoutBinding binds[]={{0,VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,1,VK_SHADER_STAGE_COMPUTE_BIT,NULL},{1,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_COMPUTE_BIT,NULL},{2,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_COMPUTE_BIT,NULL},{3,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_COMPUTE_BIT,NULL}};
    VkDescriptorSetLayoutCreateInfo si={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=4,.pBindings=binds};VkDescriptorSetLayout set;REQUIRE(vkCreateDescriptorSetLayout(dev,&si,NULL,&set));
    VkPipelineLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&set};VkPipelineLayout layout;REQUIRE(vkCreatePipelineLayout(dev,&li,NULL,&layout));VkShaderModule sh=shader(root,"virtual-atlas.comp.spv");
    VkComputePipelineCreateInfo pi={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,.stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=sh,.pName="main"},.layout=layout};VkPipeline pipeline;REQUIRE(vkCreateComputePipelines(dev,VK_NULL_HANDLE,1,&pi,NULL,&pipeline));
    VkSamplerCreateInfo sci={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=VK_FILTER_NEAREST,.minFilter=VK_FILTER_NEAREST,.mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST,.addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE};VkSampler sampler;REQUIRE(vkCreateSampler(dev,&sci,NULL,&sampler));
    VkDescriptorSetAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&set};VkDescriptorSet ds;REQUIRE(vkAllocateDescriptorSets(dev,&ai,&ds));
    VkDescriptorImageInfo ii={sampler,cache.view,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};VkDescriptorBufferInfo bo[]={{pages.buffer,0,pages.size},{queries.buffer,0,queries.size},{results.buffer,0,results.size}};VkWriteDescriptorSet wr[4]={{.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds,.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.pImageInfo=&ii}};
    for(unsigned i=1;i<4;i++)wr[i]=(VkWriteDescriptorSet){.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds,.dstBinding=i,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&bo[i-1]};vkUpdateDescriptorSets(dev,4,wr,0,NULL);
    begin();image_barrier(cache,4,1,VK_IMAGE_LAYOUT_UNDEFINED,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,0,VK_ACCESS_TRANSFER_WRITE_BIT,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT);
    VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,4},.imageExtent={TILE,TILE,1}};vkCmdCopyBufferToImage(cmd,upload.buffer,cache.image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,1,&copy);
    image_barrier(cache,4,1,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,VK_ACCESS_TRANSFER_WRITE_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);finish();
    for(unsigned phase=0;phase<2;phase++) {
        if(phase)((uint32_t*)pages.map)[0]=3; // remap one logical page; another alias must retain its content
        begin();vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&ds,0,NULL);vkCmdDispatch(cmd,(n+31)/32,1,1);host_barrier();finish();
        for(unsigned i=0;i<n;i++){float expected[4];reference(qs[i],pages.map,expected);int ok=1;float *got=(float*)results.map+i*4;for(unsigned c=0;c<4;c++)ok&=fabsf(got[c]-expected[c])<.025f;checks++;failed+=!ok;printf("atlas phase=%u query=%u %s rgba=%.4f,%.4f,%.4f,%.4f\n",phase,i,ok?"PASS":"FAIL",got[0],got[1],got[2],got[3]);}
    }
    VkMemoryRequirements pr,ur,qr,rr;vkGetBufferMemoryRequirements(dev,pages.buffer,&pr);vkGetBufferMemoryRequirements(dev,upload.buffer,&ur);vkGetBufferMemoryRequirements(dev,queries.buffer,&qr);vkGetBufferMemoryRequirements(dev,results.buffer,&rr);
    printf("virtual atlas: %u pages, page table payload %llu bytes, compressed physical cache allocation %llu bytes; staging payload %llu, query/result payload %llu bytes\n",page_count,(unsigned long long)pages.size,(unsigned long long)cache.allocated,(unsigned long long)upload.size,(unsigned long long)(queries.size+results.size));
    printf("bound allocation bytes: page table %llu staging %llu query/result %llu image %llu total %llu (excludes driver/pipeline overhead)\n",(unsigned long long)pr.size,(unsigned long long)ur.size,(unsigned long long)(qr.size+rr.size),(unsigned long long)cache.allocated,(unsigned long long)(pr.size+ur.size+qr.size+rr.size+cache.allocated));
    vkDestroyPipeline(dev,pipeline,NULL);vkDestroyShaderModule(dev,sh,NULL);vkDestroySampler(dev,sampler,NULL);vkDestroyPipelineLayout(dev,layout,NULL);vkDestroyDescriptorSetLayout(dev,set,NULL);vkDestroyDescriptorPool(dev,pool,NULL);image_free(cache);buffer_free(upload);buffer_free(results);buffer_free(queries);buffer_free(pages);
}
int main(int argc,char **argv) {
    if(argc!=2)return 2;setbuf(stdout,NULL);
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.apiVersion=VK_API_VERSION_1_2};VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app};VkInstance instance;REQUIRE(vkCreateInstance(&ici,NULL,&instance));uint32_t n=1;REQUIRE(vkEnumeratePhysicalDevices(instance,&n,&pd));vkGetPhysicalDeviceMemoryProperties(pd,&memory);
    uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,NULL);VkQueueFamilyProperties *families=calloc(nq,sizeof*families);vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,families);uint32_t family=0;while(family<nq&&!(families[family].queueFlags&VK_QUEUE_COMPUTE_BIT))family++;free(families);if(family==nq)return 1;
    VkPhysicalDeviceFeatures features;vkGetPhysicalDeviceFeatures(pd,&features);if(!features.textureCompressionBC||!features.textureCompressionASTC_LDR)return 1;
    float priority=1;VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi,.pEnabledFeatures=&features};REQUIRE(vkCreateDevice(pd,&di,NULL,&dev));vkGetDeviceQueue(dev,family,0,&queue);
    VkCommandPoolCreateInfo pci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=family};VkCommandPool pool;REQUIRE(vkCreateCommandPool(dev,&pci,NULL,&pool));VkCommandBufferAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};REQUIRE(vkAllocateCommandBuffers(dev,&ai,&cmd));
    query_requirements();atlas_test(argv[1]);REQUIRE(vkDeviceWaitIdle(dev));vkDestroyCommandPool(dev,pool,NULL);vkDestroyDevice(dev,NULL);vkDestroyInstance(instance,NULL);printf("Virtual atlas: %u checks, %u failed\n",checks,failed);return failed!=0;
}
