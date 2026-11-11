// Bounded Android GPU proof: translated NVN2 task/mesh rasterization and native
// compressed array textures, verified by pixels and byte-exact GPU readbacks.
// NDK clang -O1 -Wall vknvn2.c -o vknvn2 -lvulkan -lm
// vknvn2 <shader folder> [output folder]; no game runtime or window is created.
#include <vulkan/vulkan.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static VkDevice dev; static VkPhysicalDevice pd; static VkQueue queue;
static VkCommandBuffer cmd; static VkPhysicalDeviceMemoryProperties memory;
static PFN_vkCmdDrawMeshTasksEXT draw_mesh;
static unsigned checks,failed;
static unsigned validation_errors;
static VKAPI_ATTR VkBool32 VKAPI_CALL validation(VkDebugUtilsMessageSeverityFlagBitsEXT severity,VkDebugUtilsMessageTypeFlagsEXT types,const VkDebugUtilsMessengerCallbackDataEXT *data,void *user){
    (void)types;(void)user;if(severity&VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT)validation_errors++;
    fprintf(stderr,"validation: %s\n",data->pMessage);return VK_FALSE;
}
#define REQUIRE(call) do { VkResult r_=(call);if(r_!=VK_SUCCESS){fprintf(stderr,"FAIL %s: %d\n",#call,r_);exit(1);} } while(0)
#define CHECK(c,label) do {checks++;if(!(c)){failed++;fprintf(stderr,"FAIL %s\n",label);}else printf("PASS %s\n",label);}while(0)
typedef struct {VkBuffer buffer;VkDeviceMemory memory;void *map;VkDeviceSize size;} Buffer;
typedef struct {VkImage image;VkDeviceMemory memory;VkImageView view;VkDeviceSize allocated;} Image;
static uint32_t type(uint32_t bits,VkMemoryPropertyFlags flags){
    for(uint32_t i=0;i<memory.memoryTypeCount;i++)if((bits&(1u<<i))&&(memory.memoryTypes[i].propertyFlags&flags)==flags)return i;
    fprintf(stderr,"no compatible memory type\n");exit(1);
}
static Buffer buffer(VkDeviceSize size,VkBufferUsageFlags usage){
    Buffer b={.size=size};VkBufferCreateInfo ci={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=size,.usage=usage,.sharingMode=VK_SHARING_MODE_EXCLUSIVE};
    REQUIRE(vkCreateBuffer(dev,&ci,NULL,&b.buffer));VkMemoryRequirements need;vkGetBufferMemoryRequirements(dev,b.buffer,&need);
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=need.size,.memoryTypeIndex=type(need.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)};
    REQUIRE(vkAllocateMemory(dev,&ai,NULL,&b.memory));REQUIRE(vkBindBufferMemory(dev,b.buffer,b.memory,0));REQUIRE(vkMapMemory(dev,b.memory,0,size,0,&b.map));memset(b.map,0,(size_t)size);return b;
}
static void buffer_free(Buffer b){vkUnmapMemory(dev,b.memory);vkDestroyBuffer(dev,b.buffer,NULL);vkFreeMemory(dev,b.memory,NULL);}
static Image image(VkFormat format,uint32_t width,uint32_t height,uint32_t layers,uint32_t levels,VkImageUsageFlags usage){
    Image im={0};VkImageCreateInfo ci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=format,.extent={width,height,1},.mipLevels=levels,.arrayLayers=layers,.samples=VK_SAMPLE_COUNT_1_BIT,.tiling=VK_IMAGE_TILING_OPTIMAL,.usage=usage,.sharingMode=VK_SHARING_MODE_EXCLUSIVE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED};
    REQUIRE(vkCreateImage(dev,&ci,NULL,&im.image));VkMemoryRequirements need;vkGetImageMemoryRequirements(dev,im.image,&need);im.allocated=need.size;
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=need.size,.memoryTypeIndex=type(need.memoryTypeBits,VK_MEMORY_PROPERTY_DEVICE_LOCAL_BIT)};
    REQUIRE(vkAllocateMemory(dev,&ai,NULL,&im.memory));REQUIRE(vkBindImageMemory(dev,im.image,im.memory,0));
    VkImageViewCreateInfo vi={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=im.image,.viewType=layers>1?VK_IMAGE_VIEW_TYPE_2D_ARRAY:VK_IMAGE_VIEW_TYPE_2D,.format=format,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,levels,0,layers}};
    REQUIRE(vkCreateImageView(dev,&vi,NULL,&im.view));return im;
}
static void image_free(Image im){vkDestroyImageView(dev,im.view,NULL);vkDestroyImage(dev,im.image,NULL);vkFreeMemory(dev,im.memory,NULL);}
static VkShaderModule shader(const char *root,const char *name){
    char path[2048];snprintf(path,sizeof path,"%s/%s",root,name);FILE*f=fopen(path,"rb");if(!f){perror(path);exit(1);}fseek(f,0,SEEK_END);long size=ftell(f);rewind(f);uint32_t*p=malloc((size_t)size);if(!p||fread(p,1,(size_t)size,f)!=(size_t)size)exit(1);fclose(f);
    VkShaderModuleCreateInfo ci={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=(size_t)size,.pCode=p};VkShaderModule sh;REQUIRE(vkCreateShaderModule(dev,&ci,NULL,&sh));free(p);return sh;
}
static void begin(void){REQUIRE(vkResetCommandBuffer(cmd,0));VkCommandBufferBeginInfo bi={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,.flags=VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};REQUIRE(vkBeginCommandBuffer(cmd,&bi));}
static void finish(void){
    REQUIRE(vkEndCommandBuffer(cmd));VkFence fence;VkFenceCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};REQUIRE(vkCreateFence(dev,&fi,NULL,&fence));
    VkSubmitInfo si={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cmd};REQUIRE(vkQueueSubmit(queue,1,&si,fence));REQUIRE(vkWaitForFences(dev,1,&fence,VK_TRUE,10000000000ull));vkDestroyFence(dev,fence,NULL);
}
static void image_barrier(Image im,uint32_t layers,uint32_t levels,VkImageLayout old,VkImageLayout next,VkAccessFlags src,VkAccessFlags dst,VkPipelineStageFlags from,VkPipelineStageFlags to){
    VkImageMemoryBarrier b={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.srcAccessMask=src,.dstAccessMask=dst,.oldLayout=old,.newLayout=next,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.image=im.image,.subresourceRange={VK_IMAGE_ASPECT_COLOR_BIT,0,levels,0,layers}};
    vkCmdPipelineBarrier(cmd,from,to,0,0,NULL,0,NULL,1,&b);
}
static void host_barrier(void){VkMemoryBarrier b={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT|VK_ACCESS_SHADER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};vkCmdPipelineBarrier(cmd,VK_PIPELINE_STAGE_TRANSFER_BIT|VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&b,0,NULL,0,NULL);}
static void save_ppm(const char *root,const char *name,const uint8_t *rgba){
    if(!root)return;char path[2048];snprintf(path,sizeof path,"%s/%s.ppm",root,name);FILE*f=fopen(path,"wb");if(!f){perror(path);exit(1);}fprintf(f,"P6\n32 32\n255\n");for(unsigned i=0;i<1024;i++)fwrite(rgba+i*4,1,3,f);fclose(f);
}
static VkDescriptorPool descriptor_pool(void){
    VkDescriptorPoolSize sizes[]={{VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,16},{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,24},{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,8}};
    VkDescriptorPoolCreateInfo ci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.flags=VK_DESCRIPTOR_POOL_CREATE_FREE_DESCRIPTOR_SET_BIT,.maxSets=24,.poolSizeCount=3,.pPoolSizes=sizes};VkDescriptorPool p;REQUIRE(vkCreateDescriptorPool(dev,&ci,NULL,&p));return p;
}
// Compile actual game stages against layouts reflected from their SPIR-V.
// They are never dispatched here: their game buffers are not part of this proof.
static void real_pipelines(const char *root,VkRenderPass pass,const VkPipelineViewportStateCreateInfo *vp,const VkPipelineRasterizationStateCreateInfo *raster,const VkPipelineMultisampleStateCreateInfo *ms,const VkPipelineColorBlendStateCreateInfo *bs){
    char path[2048];snprintf(path,sizeof path,"%s/real-stages.tsv",root);FILE *list=fopen(path,"r");if(!list){printf("real game stage compilation not requested\n");return;}
    char key[80];unsigned kind,task_input,total=0;
    while(fscanf(list,"%79s %u %u",key,&kind,&task_input)==3){
        const char *names[2];unsigned stages[2],n;
        if(kind==6){names[0]=key;stages[0]=6;names[1]="mesh";stages[1]=7;n=2;}
        else if(task_input){names[0]="task";stages[0]=6;names[1]=key;stages[1]=7;n=2;}
        else{names[0]=key;stages[0]=7;n=1;}
        VkDescriptorSetLayout sets[2];VkShaderModule mods[3];VkPipelineShaderStageCreateInfo shader_stages[3];
        for(unsigned set=0;set<2;set++){
            VkDescriptorSetLayoutBinding bindings[128];unsigned nb=0;
            for(unsigned i=0;i<n;i++)if((stages[i]==6?0u:1u)==set){
                snprintf(path,sizeof path,"%s/%s.layout.tsv",root,names[i]);FILE *f=fopen(path,"r");if(!f){perror(path);exit(1);}unsigned binding,descriptor,count;
                while(fscanf(f,"%u %u %u",&binding,&descriptor,&count)==3){if(nb==128||!count)exit(1);bindings[nb++]=(VkDescriptorSetLayoutBinding){binding,(VkDescriptorType)descriptor,count,stages[i]==6?VK_SHADER_STAGE_TASK_BIT_EXT:VK_SHADER_STAGE_MESH_BIT_EXT,NULL};}fclose(f);
            }
            VkDescriptorSetLayoutCreateInfo ci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=nb,.pBindings=bindings};REQUIRE(vkCreateDescriptorSetLayout(dev,&ci,NULL,&sets[set]));
        }
        VkPushConstantRange push={VK_SHADER_STAGE_TASK_BIT_EXT|VK_SHADER_STAGE_MESH_BIT_EXT,0,16};VkPipelineLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=2,.pSetLayouts=sets,.pushConstantRangeCount=1,.pPushConstantRanges=&push};VkPipelineLayout layout;REQUIRE(vkCreatePipelineLayout(dev,&li,NULL,&layout));
        for(unsigned i=0;i<n;i++){char name[128];snprintf(name,sizeof name,"%s.vk.spv",names[i]);mods[i]=shader(root,name);shader_stages[i]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=stages[i]==6?VK_SHADER_STAGE_TASK_BIT_EXT:VK_SHADER_STAGE_MESH_BIT_EXT,.module=mods[i],.pName="main"};}
        char fsname[128];snprintf(fsname,sizeof fsname,"%s.proof.frag.spv",key);mods[n]=shader(root,fsname);shader_stages[n]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=mods[n],.pName="main"};n++;
        VkGraphicsPipelineCreateInfo pi={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=n,.pStages=shader_stages,.pViewportState=vp,.pRasterizationState=raster,.pMultisampleState=ms,.pColorBlendState=bs,.layout=layout,.renderPass=pass};VkPipeline pipeline=VK_NULL_HANDLE;VkResult result=vkCreateGraphicsPipelines(dev,VK_NULL_HANDLE,1,&pi,NULL,&pipeline);
        printf("real stage %s kind %u pipeline %d\n",key,kind,result);CHECK(result==VK_SUCCESS,"actual game task/mesh pipeline compiles");total++;
        if(pipeline)vkDestroyPipeline(dev,pipeline,NULL);for(unsigned i=0;i<n;i++)vkDestroyShaderModule(dev,mods[i],NULL);vkDestroyPipelineLayout(dev,layout,NULL);for(unsigned i=0;i<2;i++)vkDestroyDescriptorSetLayout(dev,sets[i],NULL);
    }
    fclose(list);printf("actual game stage pipelines tested %u\n",total);
}
static void mesh_test(const char *root,const char *out){
    VkDescriptorPool pool=descriptor_pool();VkDescriptorSetLayout sets[2];VkDescriptorSet ds[2];Buffer cb[2],sb[2];
    for(unsigned i=0;i<2;i++){
        VkShaderStageFlags stages=VK_SHADER_STAGE_TASK_BIT_EXT|VK_SHADER_STAGE_MESH_BIT_EXT;
        VkDescriptorSetLayoutBinding bindings[]={{8,VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,1,stages,NULL},{9,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,stages,NULL}};
        VkDescriptorSetLayoutCreateInfo ci={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=2,.pBindings=bindings};REQUIRE(vkCreateDescriptorSetLayout(dev,&ci,NULL,&sets[i]));
        VkDescriptorSetAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&sets[i]};REQUIRE(vkAllocateDescriptorSets(dev,&ai,&ds[i]));
        cb[i]=buffer(16,VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT);sb[i]=buffer(16,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
        VkDescriptorBufferInfo bi[]={{cb[i].buffer,0,16},{sb[i].buffer,0,16}};
        VkWriteDescriptorSet wr[]={{.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds[i],.dstBinding=8,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,.pBufferInfo=&bi[0]},
            {.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds[i],.dstBinding=9,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&bi[1]}};vkUpdateDescriptorSets(dev,2,wr,0,NULL);
    }
    VkShaderStageFlags flags=VK_SHADER_STAGE_TASK_BIT_EXT|VK_SHADER_STAGE_MESH_BIT_EXT|VK_SHADER_STAGE_FRAGMENT_BIT;
    VkPushConstantRange push={flags,0,16};VkPipelineLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=2,.pSetLayouts=sets,.pushConstantRangeCount=1,.pPushConstantRanges=&push};VkPipelineLayout layout;REQUIRE(vkCreatePipelineLayout(dev,&li,NULL,&layout));
    Image target=image(VK_FORMAT_R8G8B8A8_UNORM,32,32,1,1,VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT);
    VkAttachmentDescription attachment={.format=VK_FORMAT_R8G8B8A8_UNORM,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,.stencilLoadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,.stencilStoreOp=VK_ATTACHMENT_STORE_OP_DONT_CARE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED,.finalLayout=VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
    VkAttachmentReference ref={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};VkSubpassDescription sub={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&ref};
    VkRenderPassCreateInfo ri={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=1,.pAttachments=&attachment,.subpassCount=1,.pSubpasses=&sub};VkRenderPass pass;REQUIRE(vkCreateRenderPass(dev,&ri,NULL,&pass));
    VkFramebufferCreateInfo fbi={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=pass,.attachmentCount=1,.pAttachments=&target.view,.width=32,.height=32,.layers=1};VkFramebuffer fb;REQUIRE(vkCreateFramebuffer(dev,&fbi,NULL,&fb));
    VkViewport viewport={0,0,32,32,0,1};VkRect2D scissor={{0,0},{32,32}};VkPipelineViewportStateCreateInfo vp={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.pViewports=&viewport,.scissorCount=1,.pScissors=&scissor};
    VkPipelineRasterizationStateCreateInfo raster={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE,.lineWidth=1};VkPipelineMultisampleStateCreateInfo ms={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
    VkPipelineColorBlendAttachmentState blend={.colorWriteMask=15};VkPipelineColorBlendStateCreateInfo bs={.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&blend};
    VkShaderModule fragment=shader(root,"proof.frag.spv"),mesh=shader(root,"mesh.vk.spv"),direct=shader(root,"direct.vk.spv"),task=shader(root,"task.vk.spv"),empty=shader(root,"empty.vk.spv");Buffer pixels=buffer(4096,VK_BUFFER_USAGE_TRANSFER_DST_BIT);
    const char *names[]={"direct-mesh","task-mesh","empty-task","bad-task-binding","bad-mesh-binding","zero-task-count"};
    for(unsigned mode=0;mode<6;mode++){
        *(uint32_t*)cb[0].map=mode==3?99:6;*(uint32_t*)sb[0].map=16;*(uint32_t*)cb[1].map=7;*(uint32_t*)sb[1].map=mode==4?99:17;
        VkPipelineShaderStageCreateInfo stages[3];unsigned n=0;
        if(mode)stages[n++]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_TASK_BIT_EXT,.module=mode==2?empty:task,.pName="main"};
        stages[n++]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_MESH_BIT_EXT,.module=mode?mesh:direct,.pName="main"};
        stages[n++]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=fragment,.pName="main"};
        VkGraphicsPipelineCreateInfo pi={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=n,.pStages=stages,.pViewportState=&vp,.pRasterizationState=&raster,.pMultisampleState=&ms,.pColorBlendState=&bs,.layout=layout,.renderPass=pass};VkPipeline pipeline;REQUIRE(vkCreateGraphicsPipelines(dev,VK_NULL_HANDLE,1,&pi,NULL,&pipeline));
        begin();VkClearValue clear={.color={{0,0,1,1}}};VkRenderPassBeginInfo bi={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=pass,.framebuffer=fb,.renderArea={{0,0},{32,32}},.clearValueCount=1,.pClearValues=&clear};vkCmdBeginRenderPass(cmd,&bi,VK_SUBPASS_CONTENTS_INLINE);
        vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_GRAPHICS,layout,0,2,ds,0,NULL);uint32_t pc[]={0x3f800000,1,mode,0};vkCmdPushConstants(cmd,layout,flags,0,16,pc);draw_mesh(cmd,mode==5?0:1,1,1);vkCmdEndRenderPass(cmd);
        image_barrier(target,1,1,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,VK_ACCESS_COLOR_ATTACHMENT_WRITE_BIT,VK_ACCESS_TRANSFER_READ_BIT,VK_PIPELINE_STAGE_COLOR_ATTACHMENT_OUTPUT_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT);
        VkBufferImageCopy copy={.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,0,0,1},.imageExtent={32,32,1}};vkCmdCopyImageToBuffer(cmd,target.image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,pixels.buffer,1,&copy);host_barrier();finish();
        uint8_t *p=(uint8_t*)pixels.map+(16*32+16)*4;int red=mode==4,blue=mode==2||mode==3||mode==5;
        printf("mesh %s center %u,%u,%u,%u\n",names[mode],p[0],p[1],p[2],p[3]);CHECK(p[0]==(red?255:0)&&p[1]==(!red&&!blue?255:0)&&p[2]==(blue?255:0)&&p[3]==255,names[mode]);save_ppm(out,names[mode],pixels.map);vkDestroyPipeline(dev,pipeline,NULL);
    }
    real_pipelines(root,pass,&vp,&raster,&ms,&bs);
    buffer_free(pixels);VkShaderModule mods[]={fragment,mesh,direct,task,empty};for(unsigned i=0;i<5;i++)vkDestroyShaderModule(dev,mods[i],NULL);
    vkDestroyFramebuffer(dev,fb,NULL);vkDestroyRenderPass(dev,pass,NULL);image_free(target);vkDestroyPipelineLayout(dev,layout,NULL);vkDestroyDescriptorPool(dev,pool,NULL);
    for(unsigned i=0;i<2;i++){vkDestroyDescriptorSetLayout(dev,sets[i],NULL);buffer_free(cb[i]);buffer_free(sb[i]);}
}
static void texture_test(const char *root){
    const struct{VkFormat format;const char *name;unsigned block,bits;}formats[]={{VK_FORMAT_BC1_RGBA_UNORM_BLOCK,"BC1",4,8},{VK_FORMAT_BC6H_UFLOAT_BLOCK,"BC6H",4,16},{VK_FORMAT_ASTC_4x4_UNORM_BLOCK,"ASTC4x4",4,16},{VK_FORMAT_ASTC_8x8_SRGB_BLOCK,"ASTC8x8s",8,16}};
    VkDescriptorPool pool=descriptor_pool();VkDescriptorSetLayoutBinding binds[]={{0,VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,1,VK_SHADER_STAGE_COMPUTE_BIT,NULL},{1,VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,1,VK_SHADER_STAGE_COMPUTE_BIT,NULL}};
    VkDescriptorSetLayoutCreateInfo si={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,.bindingCount=2,.pBindings=binds};VkDescriptorSetLayout set;REQUIRE(vkCreateDescriptorSetLayout(dev,&si,NULL,&set));VkPipelineLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=1,.pSetLayouts=&set};VkPipelineLayout layout;REQUIRE(vkCreatePipelineLayout(dev,&li,NULL,&layout));
    VkShaderModule sh=shader(root,"proof.comp.spv");VkComputePipelineCreateInfo pi={.sType=VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,.stage={.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_COMPUTE_BIT,.module=sh,.pName="main"},.layout=layout};VkPipeline pipeline;REQUIRE(vkCreateComputePipelines(dev,VK_NULL_HANDLE,1,&pi,NULL,&pipeline));
    VkSamplerCreateInfo sci={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=VK_FILTER_NEAREST,.minFilter=VK_FILTER_NEAREST,.mipmapMode=VK_SAMPLER_MIPMAP_MODE_NEAREST,.addressModeU=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeV=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.addressModeW=VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,.maxLod=3};VkSampler sampler;REQUIRE(vkCreateSampler(dev,&sci,NULL,&sampler));
    for(unsigned fmt=0;fmt<4;fmt++){
        VkBufferImageCopy regions[12];VkDeviceSize size=0;unsigned index=0;
        for(unsigned mip=0;mip<3;mip++)for(unsigned layer=0;layer<4;layer++){unsigned width=1024u>>mip;regions[index++]=(VkBufferImageCopy){.bufferOffset=size,.imageSubresource={VK_IMAGE_ASPECT_COLOR_BIT,mip,layer,1},.imageExtent={width,width,1}};size+=(VkDeviceSize)(width/formats[fmt].block)*(width/formats[fmt].block)*formats[fmt].bits;}
        Buffer upload=buffer(size,VK_BUFFER_USAGE_TRANSFER_SRC_BIT),back=buffer(size,VK_BUFFER_USAGE_TRANSFER_DST_BIT),decoded=buffer(12*16,VK_BUFFER_USAGE_STORAGE_BUFFER_BIT);
        for(unsigned i=0;i<12;i++){
            unsigned color=(regions[i].imageSubresource.baseArrayLayer+regions[i].imageSubresource.mipLevel)%4;uint8_t block[16]={0};
            if(fmt==0){uint16_t endpoint=color==0?0xf800:color==1?0x07e0:color==2?0x001f:0x8410;memcpy(block,&endpoint,2);}
            if(fmt==1){
                // BC6H mode 11 (selector 00011): two explicit 10-bit RGB
                // endpoints, identical here, followed by zero interpolation
                // indices. Quantized 495 is 1.0; 528 is approximately 2.0.
                block[0]=3;
                for(unsigned endpoint=0;endpoint<2;endpoint++)for(unsigned c=0;c<3;c++){
                    unsigned q=c==color?(c==0?528:495):0;
                    for(unsigned bit=0;bit<10;bit++)if(q&(1u<<bit)){unsigned pos=5+(endpoint*3+c)*10+bit;block[pos/8]|=(uint8_t)(1u<<(pos%8));}
                }
            }
            if(fmt>=2){const uint8_t astc[]={0xfc,0xfd,0xff,0xff,0xff,0xff,0xff,0xff,0,0,0,0,0,0,255,255};memcpy(block,astc,16);if(color<3)block[8+2*color]=block[9+2*color]=255;else for(unsigned c=8;c<14;c++)block[c]=128;}
            VkDeviceSize end=i+1<12?regions[i+1].bufferOffset:size;for(VkDeviceSize off=regions[i].bufferOffset;off<end;off+=formats[fmt].bits)memcpy((uint8_t*)upload.map+off,block,formats[fmt].bits);
        }
        Image im=image(formats[fmt].format,1024,1024,4,3,VK_IMAGE_USAGE_TRANSFER_DST_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT|VK_IMAGE_USAGE_SAMPLED_BIT);
        uint64_t rgba8=4ull*(1024*1024+512*512+256*256)*4;
        printf("texture %s: payload %llu, actual allocation %llu, RGBA8 equivalent %llu bytes\n",formats[fmt].name,(unsigned long long)size,(unsigned long long)im.allocated,(unsigned long long)rgba8);CHECK(im.allocated<rgba8,"compressed image allocation remains smaller than RGBA8");
        VkDescriptorSetAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=1,.pSetLayouts=&set};VkDescriptorSet ds;REQUIRE(vkAllocateDescriptorSets(dev,&ai,&ds));VkDescriptorImageInfo ii={sampler,im.view,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL};VkDescriptorBufferInfo bo={decoded.buffer,0,decoded.size};VkWriteDescriptorSet wr[]={{.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds,.dstBinding=0,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.pImageInfo=&ii},{.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=ds,.dstBinding=1,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,.pBufferInfo=&bo}};vkUpdateDescriptorSets(dev,2,wr,0,NULL);
        begin();image_barrier(im,4,3,VK_IMAGE_LAYOUT_UNDEFINED,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,0,VK_ACCESS_TRANSFER_WRITE_BIT,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT);
        vkCmdCopyBufferToImage(cmd,upload.buffer,im.image,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,12,regions);image_barrier(im,4,3,VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,VK_ACCESS_TRANSFER_WRITE_BIT,VK_ACCESS_TRANSFER_READ_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT);vkCmdCopyImageToBuffer(cmd,im.image,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,back.buffer,12,regions);
        image_barrier(im,4,3,VK_IMAGE_LAYOUT_TRANSFER_SRC_OPTIMAL,VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL,VK_ACCESS_TRANSFER_READ_BIT,VK_ACCESS_SHADER_READ_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_COMPUTE_SHADER_BIT);vkCmdBindPipeline(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,pipeline);vkCmdBindDescriptorSets(cmd,VK_PIPELINE_BIND_POINT_COMPUTE,layout,0,1,&ds,0,NULL);vkCmdDispatch(cmd,12,1,1);host_barrier();finish();
        CHECK(!memcmp(upload.map,back.map,(size_t)size),"compressed blocks survive GPU upload/readback byte for byte");float *colors=decoded.map;int good=1;
        for(unsigned i=0;i<12;i++){unsigned color=(i%4+i/4)%4;for(unsigned c=0;c<4;c++){
            float want=c==3?1.f:(c==color?(fmt==1&&c==0?2.f:1.f):0.f);
            if(c<3&&color==3){if(fmt==0)want=(c==1?130.f:132.f)/255.f;else if(fmt==2)want=128.f/255.f;else if(fmt==3)want=powf((128.f/255.f+.055f)/1.055f,2.4f);}
            if(fabsf(colors[i*4+c]-want)>.006f||!isfinite(colors[i*4+c]))good=0;
        }}
        if(!good)for(unsigned i=0;i<12;i++)printf("  sample %u: %g %g %g %g\n",i,colors[i*4],colors[i*4+1],colors[i*4+2],colors[i*4+3]);CHECK(good,"all compressed layers and mips decode to their expected GPU colours");
        REQUIRE(vkFreeDescriptorSets(dev,pool,1,&ds));image_free(im);buffer_free(upload);buffer_free(back);buffer_free(decoded);
    }
    vkDestroySampler(dev,sampler,NULL);vkDestroyPipeline(dev,pipeline,NULL);vkDestroyShaderModule(dev,sh,NULL);vkDestroyPipelineLayout(dev,layout,NULL);vkDestroyDescriptorPool(dev,pool,NULL);vkDestroyDescriptorSetLayout(dev,set,NULL);
}
int main(int argc,char**argv){
    if(argc<2||argc>3){fprintf(stderr,"usage: vknvn2 shader-folder [output-folder]\n");return 2;}setbuf(stdout,NULL);
    int validate=getenv("DM_VK_VALIDATE")!=NULL;const char *layer="VK_LAYER_KHRONOS_validation",*debug=VK_EXT_DEBUG_UTILS_EXTENSION_NAME;
    VkDebugUtilsMessengerCreateInfoEXT debug_ci={.sType=VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,.messageSeverity=VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT,.messageType=VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_PERFORMANCE_BIT_EXT,.pfnUserCallback=validation};
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="nxhost bounded NVN2 proof",.apiVersion=VK_API_VERSION_1_2};VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pNext=validate?&debug_ci:NULL,.pApplicationInfo=&app,.enabledLayerCount=validate?1:0,.ppEnabledLayerNames=&layer,.enabledExtensionCount=validate?1:0,.ppEnabledExtensionNames=&debug};VkInstance instance;REQUIRE(vkCreateInstance(&ici,NULL,&instance));
    VkDebugUtilsMessengerEXT messenger=VK_NULL_HANDLE;if(validate){PFN_vkCreateDebugUtilsMessengerEXT create=(PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance,"vkCreateDebugUtilsMessengerEXT");if(!create)return 1;REQUIRE(create(instance,&debug_ci,NULL,&messenger));}
    uint32_t np=1;REQUIRE(vkEnumeratePhysicalDevices(instance,&np,&pd));if(!np)return 1;
    VkPhysicalDeviceProperties props;vkGetPhysicalDeviceProperties(pd,&props);printf("device %s API %u.%u.%u\n",props.deviceName,VK_API_VERSION_MAJOR(props.apiVersion),VK_API_VERSION_MINOR(props.apiVersion),VK_API_VERSION_PATCH(props.apiVersion));vkGetPhysicalDeviceMemoryProperties(pd,&memory);
    VkPhysicalDeviceMeshShaderFeaturesEXT mesh={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MESH_SHADER_FEATURES_EXT};VkPhysicalDeviceVulkan12Features v12={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_2_FEATURES,.pNext=&mesh};VkPhysicalDeviceVulkan11Features v11={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_VULKAN_1_1_FEATURES,.pNext=&v12};VkPhysicalDeviceFeatures2 features={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,.pNext=&v11};vkGetPhysicalDeviceFeatures2(pd,&features);if(!mesh.meshShader||!mesh.taskShader||!features.features.textureCompressionBC||!features.features.textureCompressionASTC_LDR){fprintf(stderr,"required mesh/task/compression feature unavailable\n");return 1;}
    uint32_t nq=0;vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,NULL);VkQueueFamilyProperties *families=calloc(nq,sizeof*families);vkGetPhysicalDeviceQueueFamilyProperties(pd,&nq,families);uint32_t family=0;while(family<nq&&(families[family].queueFlags&(VK_QUEUE_GRAPHICS_BIT|VK_QUEUE_COMPUTE_BIT))!=(VK_QUEUE_GRAPHICS_BIT|VK_QUEUE_COMPUTE_BIT))family++;free(families);if(family==nq)return 1;
    float priority=1;VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=family,.queueCount=1,.pQueuePriorities=&priority};const char*ext=VK_EXT_MESH_SHADER_EXTENSION_NAME;VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.pNext=&features,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi,.enabledExtensionCount=1,.ppEnabledExtensionNames=&ext};REQUIRE(vkCreateDevice(pd,&di,NULL,&dev));vkGetDeviceQueue(dev,family,0,&queue);draw_mesh=(PFN_vkCmdDrawMeshTasksEXT)vkGetDeviceProcAddr(dev,"vkCmdDrawMeshTasksEXT");if(!draw_mesh)return 1;
    VkCommandPoolCreateInfo pci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.flags=VK_COMMAND_POOL_CREATE_RESET_COMMAND_BUFFER_BIT,.queueFamilyIndex=family};VkCommandPool pool;REQUIRE(vkCreateCommandPool(dev,&pci,NULL,&pool));VkCommandBufferAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=pool,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};REQUIRE(vkAllocateCommandBuffers(dev,&ai,&cmd));
    mesh_test(argv[1],argc==3?argv[2]:NULL);texture_test(argv[1]);REQUIRE(vkDeviceWaitIdle(dev));vkDestroyCommandPool(dev,pool,NULL);vkDestroyDevice(dev,NULL);
    if(validate){CHECK(!validation_errors,"Vulkan validation reports no errors");PFN_vkDestroyDebugUtilsMessengerEXT destroy=(PFN_vkDestroyDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance,"vkDestroyDebugUtilsMessengerEXT");destroy(instance,messenger,NULL);}
    vkDestroyInstance(instance,NULL);printf("NVN2 Vulkan proof: %u checks, %u failed\n",checks,failed);return failed?1:0;
}
