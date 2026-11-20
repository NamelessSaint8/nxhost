// Bounded mesh-stage isolation from gfx_vk_mesh_capture.inc manifests.
// NDK clang -O1 -Wall -Wextra -Werror -I<headers> this.c -lvulkan -o replay
// replay capture-prefix [replacement.mesh.spv] [discard|real]
// "real" restores the captured fragment buffers and BC3 texture array. The
// attachment formats match the selected fixture; their contents start cleared.
// This diagnoses draw completion and does not establish game pixel equivalence.
#include <vulkan/vulkan.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr,"invalid capture: %s\n",#x); exit(2); } } while (0)
#define VK(x) do { VkResult r_=(x); if(r_) { fprintf(stderr,"%s: %d\n",#x,r_); exit(3); } } while(0)
static VkDevice dev;
static VkPhysicalDeviceMemoryProperties memory;
static unsigned errors;
static VkBuffer allocated_buffers[64];static VkDeviceMemory allocated_memory[64];static unsigned allocated_count;
static VKAPI_ATTR VkBool32 VKAPI_CALL message(VkDebugUtilsMessageSeverityFlagBitsEXT severity,
        VkDebugUtilsMessageTypeFlagsEXT type,const VkDebugUtilsMessengerCallbackDataEXT *data,void *user) {
    (void)type; (void)user;
    if (severity & VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT) errors++;
    fprintf(stderr,"validation: %s\n",data->pMessage); return VK_FALSE;
}
static void *load(const char *path,size_t *size) {
    FILE *f=fopen(path,"rb"); if(!f) {perror(path);exit(2);}
    CHECK(!fseek(f,0,SEEK_END)); long n=ftell(f); CHECK(n>0); rewind(f);
    void *p=malloc((size_t)n); CHECK(p && fread(p,1,(size_t)n,f)==(size_t)n && !fclose(f));
    *size=(size_t)n; return p;
}
static uint32_t memtype(uint32_t bits,VkMemoryPropertyFlags flags) {
    for(unsigned i=0;i<memory.memoryTypeCount;i++)
        if((bits & (1u<<i)) && (memory.memoryTypes[i].propertyFlags & flags)==flags)return i;
    CHECK(0);return 0;
}
static VkBuffer buffer(size_t bytes,const void *data) {
    VkBuffer b; VkDeviceMemory m;
    VkBufferCreateInfo ci={.sType=VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO,.size=bytes,
        .usage=VK_BUFFER_USAGE_UNIFORM_BUFFER_BIT|VK_BUFFER_USAGE_STORAGE_BUFFER_BIT|VK_BUFFER_USAGE_TRANSFER_SRC_BIT|VK_BUFFER_USAGE_TRANSFER_DST_BIT};
    VK(vkCreateBuffer(dev,&ci,NULL,&b)); VkMemoryRequirements req; vkGetBufferMemoryRequirements(dev,b,&req);
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=req.size,
        .memoryTypeIndex=memtype(req.memoryTypeBits,VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT|VK_MEMORY_PROPERTY_HOST_COHERENT_BIT)};
    VK(vkAllocateMemory(dev,&ai,NULL,&m));VK(vkBindBufferMemory(dev,b,m,0));void *mapped;
    VK(vkMapMemory(dev,m,0,bytes,0,&mapped));memcpy(mapped,data,bytes);vkUnmapMemory(dev,m);
    CHECK(allocated_count<64);allocated_buffers[allocated_count]=b;allocated_memory[allocated_count++]=m;return b;
}
typedef struct {VkImage image;VkDeviceMemory memory;VkImageView view;} image;
static image make_image(unsigned fmt,unsigned w,unsigned h,unsigned levels,unsigned layers,unsigned aspect,unsigned type,unsigned usage,const unsigned swz[4]) {
    image out;VkImageCreateInfo ci={.sType=VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO,.imageType=VK_IMAGE_TYPE_2D,.format=fmt,
        .extent={w,h,1},.mipLevels=levels,.arrayLayers=layers,.samples=1,.tiling=VK_IMAGE_TILING_OPTIMAL,.usage=usage};
    VK(vkCreateImage(dev,&ci,NULL,&out.image));VkMemoryRequirements req;vkGetImageMemoryRequirements(dev,out.image,&req);
    VkMemoryAllocateInfo ai={.sType=VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO,.allocationSize=req.size,.memoryTypeIndex=memtype(req.memoryTypeBits,0)};
    VK(vkAllocateMemory(dev,&ai,NULL,&out.memory));VK(vkBindImageMemory(dev,out.image,out.memory,0));
    VkImageViewCreateInfo vi={.sType=VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO,.image=out.image,.viewType=type,.format=fmt,
        .subresourceRange={aspect,0,levels,0,layers}};
    if(swz)vi.components=(VkComponentMapping){swz[0],swz[1],swz[2],swz[3]};
    VK(vkCreateImageView(dev,&vi,NULL,&out.view));return out;
}
static void free_image(image im) {vkDestroyImageView(dev,im.view,NULL);vkDestroyImage(dev,im.image,NULL);vkFreeMemory(dev,im.memory,NULL);}
static void transition(VkCommandBuffer cb,VkImage im,unsigned aspect,unsigned levels,unsigned layers) {
    VkImageMemoryBarrier barrier={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.dstAccessMask=VK_ACCESS_MEMORY_READ_BIT|VK_ACCESS_MEMORY_WRITE_BIT,
        .oldLayout=VK_IMAGE_LAYOUT_UNDEFINED,.newLayout=VK_IMAGE_LAYOUT_GENERAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,
        .image=im,.subresourceRange={aspect,0,levels,0,layers}};
    vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT,VK_PIPELINE_STAGE_ALL_COMMANDS_BIT,0,0,NULL,0,NULL,1,&barrier);
}
int main(int argc,char **argv) {
    CHECK(argc>=2 && argc<=4);setbuf(stdout,NULL);
    int discard=argc==4 && !strcmp(argv[3],"discard");
    int real=argc==4 && !strcmp(argv[3],"real");
    char path[2048],line[2048];snprintf(path,sizeof path,"%s.tsv",argv[1]);FILE *f=fopen(path,"r");CHECK(f);
    unsigned dynamic=getenv("DM_MESH_DYNAMIC") && atoi(getenv("DM_MESH_DYNAMIC"));
    struct {unsigned stage,binding,type;size_t bytes,offset;char name[128];VkBuffer buf;} inputs[32];unsigned count=0,groups=0;
    unsigned texture_binding=0,texture_fmt=0,texture_w=0,texture_h=0,texture_type=0,texture_aspect=0,texture_levels=0,texture_layers=0,texture_swz[4];
    char texture_name[128]="",sampler_name[128]="";
    while(fgets(line,sizeof line,f)) {
        unsigned stage,binding,type;unsigned long long offset,bytes;char name[128];
        if(sscanf(line,"args %u",&groups)==1)continue;
        if(sscanf(line,"buffer %u %u %u %llu %llu %127s",&stage,&binding,&type,&offset,&bytes,name)==6 && (stage==7 || (real && stage==1))) {
            CHECK(count<32 && strcmp(name,"omitted") && (type==6 || type==7));
            inputs[count].stage=stage;inputs[count].binding=binding;inputs[count].type=type;inputs[count].bytes=bytes;inputs[count].offset=0;
            if(dynamic && type==6 && !(stage==1 && binding==0)){inputs[count].type=8;inputs[count].offset=offset;}
            strcpy(inputs[count++].name,name);
        }
        if(real && !strncmp(line,"image ",6)) {
            unsigned view_fmt,base_level,base_layer,storage;
            CHECK(!texture_fmt && sscanf(line,"image %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %u %127s %127s",
                &stage,&texture_binding,&texture_fmt,&view_fmt,&texture_w,&texture_h,&texture_type,&texture_aspect,&base_level,&texture_levels,
                &base_layer,&texture_layers,&texture_swz[0],&texture_swz[1],&texture_swz[2],&texture_swz[3],&storage,texture_name,sampler_name)==19);
            CHECK(stage==1 && !storage && texture_fmt==view_fmt && texture_fmt==VK_FORMAT_BC3_SRGB_BLOCK && !base_level && !base_layer && texture_levels<=32);
            CHECK(strcmp(texture_name,"omitted") && strcmp(sampler_name,"omitted"));
        }
    }CHECK(!fclose(f) && count && groups);
    const char *layer="VK_LAYER_KHRONOS_validation",*debug=VK_EXT_DEBUG_UTILS_EXTENSION_NAME;
    VkApplicationInfo app={.sType=VK_STRUCTURE_TYPE_APPLICATION_INFO,.pApplicationName="mesh capture isolation",.apiVersion=VK_API_VERSION_1_2};
    VkInstanceCreateInfo ici={.sType=VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,.pApplicationInfo=&app,
        .enabledLayerCount=1,.ppEnabledLayerNames=&layer,.enabledExtensionCount=1,.ppEnabledExtensionNames=&debug};
    VkInstance instance;VK(vkCreateInstance(&ici,NULL,&instance));
    PFN_vkCreateDebugUtilsMessengerEXT create_debug=(PFN_vkCreateDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance,"vkCreateDebugUtilsMessengerEXT");CHECK(create_debug);
    VkDebugUtilsMessengerCreateInfoEXT mi={.sType=VK_STRUCTURE_TYPE_DEBUG_UTILS_MESSENGER_CREATE_INFO_EXT,
        .messageSeverity=VK_DEBUG_UTILS_MESSAGE_SEVERITY_ERROR_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_SEVERITY_WARNING_BIT_EXT,
        .messageType=VK_DEBUG_UTILS_MESSAGE_TYPE_VALIDATION_BIT_EXT|VK_DEBUG_UTILS_MESSAGE_TYPE_GENERAL_BIT_EXT,.pfnUserCallback=message};
    VkDebugUtilsMessengerEXT messenger;VK(create_debug(instance,&mi,NULL,&messenger));
    unsigned n=1;VkPhysicalDevice pd;VK(vkEnumeratePhysicalDevices(instance,&n,&pd));CHECK(n);
    vkGetPhysicalDeviceMemoryProperties(pd,&memory);
    VkPhysicalDeviceMeshShaderFeaturesEXT mesh={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MESH_SHADER_FEATURES_EXT};
    VkPhysicalDeviceFeatures2 features={.sType=VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,.pNext=&mesh};
    vkGetPhysicalDeviceFeatures2(pd,&features);CHECK(mesh.meshShader);
    mesh.taskShader=mesh.multiviewMeshShader=mesh.primitiveFragmentShadingRateMeshShader=mesh.meshShaderQueries=0;
    CHECK(!real || features.features.textureCompressionBC);
    unsigned robust=getenv("DM_MESH_ROBUST") && atoi(getenv("DM_MESH_ROBUST"));
    CHECK(!robust || features.features.robustBufferAccess);
    VkPhysicalDeviceFeatures enabled={.robustBufferAccess=robust,.textureCompressionBC=real,
        .shaderImageGatherExtended=features.features.shaderImageGatherExtended};
    VkQueueFamilyProperties queues[32];n=32;vkGetPhysicalDeviceQueueFamilyProperties(pd,&n,queues);unsigned qf=0;
    while(qf<n && !(queues[qf].queueFlags&VK_QUEUE_GRAPHICS_BIT))qf++;CHECK(qf<n);
    float priority=1;VkDeviceQueueCreateInfo qi={.sType=VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,.queueFamilyIndex=qf,.queueCount=1,.pQueuePriorities=&priority};
    const char *extension=VK_EXT_MESH_SHADER_EXTENSION_NAME;
    VkDeviceCreateInfo di={.sType=VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,.pNext=&mesh,.queueCreateInfoCount=1,.pQueueCreateInfos=&qi,
        .enabledExtensionCount=1,.ppEnabledExtensionNames=&extension,.pEnabledFeatures=&enabled};
    VK(vkCreateDevice(pd,&di,NULL,&dev));VkQueue queue;vkGetDeviceQueue(dev,qf,0,&queue);
    VkDescriptorSetLayoutBinding bindings[2][32];unsigned nbindings[2]={0};VkDescriptorBufferInfo infos[32];VkWriteDescriptorSet writes[32];
    for(unsigned i=0;i<count;i++) {
        snprintf(path,sizeof path,"%s.%s",argv[1],inputs[i].name);size_t bytes;void *data=load(path,&bytes);CHECK(bytes==inputs[i].bytes);
        if(inputs[i].offset){void *padded=calloc(1,bytes+inputs[i].offset);CHECK(padded);memcpy((char *)padded+inputs[i].offset,data,bytes);inputs[i].buf=buffer(bytes+inputs[i].offset,padded);free(padded);}
        else inputs[i].buf=buffer(bytes,data);
        free(data);
        unsigned s=inputs[i].stage==7;bindings[s][nbindings[s]++]=(VkDescriptorSetLayoutBinding){.binding=inputs[i].binding,.descriptorType=inputs[i].type,.descriptorCount=1,.stageFlags=s?VK_SHADER_STAGE_MESH_BIT_EXT:VK_SHADER_STAGE_FRAGMENT_BIT};
        infos[i]=(VkDescriptorBufferInfo){inputs[i].buf,0,bytes};
    }
    VkDescriptorSetLayout layouts[3];VkDescriptorSetLayoutCreateInfo li={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO};
    VK(vkCreateDescriptorSetLayout(dev,&li,NULL,&layouts[0]));
    if(real)bindings[0][nbindings[0]++]=(VkDescriptorSetLayoutBinding){texture_binding,VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,1,VK_SHADER_STAGE_FRAGMENT_BIT,NULL};
    for(unsigned i=0;i<2;i++){li.bindingCount=nbindings[i];li.pBindings=bindings[i];VK(vkCreateDescriptorSetLayout(dev,&li,NULL,&layouts[i+1]));}
    VkPushConstantRange push={VK_SHADER_STAGE_MESH_BIT_EXT,0,8};VkPipelineLayout layout;
    VkPipelineLayoutCreateInfo pli={.sType=VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO,.setLayoutCount=3,.pSetLayouts=layouts,.pushConstantRangeCount=1,.pPushConstantRanges=&push};
    VK(vkCreatePipelineLayout(dev,&pli,NULL,&layout));
    VkDescriptorPoolSize sizes[4]={{VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER,32},{VK_DESCRIPTOR_TYPE_STORAGE_BUFFER,32},{VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,1},{VK_DESCRIPTOR_TYPE_UNIFORM_BUFFER_DYNAMIC,32}};
    VkDescriptorPoolCreateInfo dpi={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO,.maxSets=2,.poolSizeCount=4,.pPoolSizes=sizes};
    VkDescriptorPool pool;VK(vkCreateDescriptorPool(dev,&dpi,NULL,&pool));VkDescriptorSet sets[2];
    VkDescriptorSetAllocateInfo dai={.sType=VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO,.descriptorPool=pool,.descriptorSetCount=2,.pSetLayouts=&layouts[1]};
    VK(vkAllocateDescriptorSets(dev,&dai,sets));
    for(unsigned i=0;i<count;i++)writes[i]=(VkWriteDescriptorSet){.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=sets[inputs[i].stage==7],.dstBinding=inputs[i].binding,.descriptorCount=1,.descriptorType=inputs[i].type,.pBufferInfo=&infos[i]};
    vkUpdateDescriptorSets(dev,count,writes,0,NULL);
    snprintf(path,sizeof path,"%s.stage7.spv",argv[1]);size_t bytes;void *code=load(argc>=3?argv[2]:path,&bytes);CHECK(!(bytes&3));
    VkShaderModuleCreateInfo si={.sType=VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO,.codeSize=bytes,.pCode=code};VkShaderModule shader;
    VK(vkCreateShaderModule(dev,&si,NULL,&shader));free(code);
    // Attachmentless pass exercises mesh output assembly without game textures.
    snprintf(path,sizeof path,"%s.stage1.spv",argv[1]);
    code=load(real?path:"mesh-isolate.frag.spv",&bytes);si.codeSize=bytes;si.pCode=code;VkShaderModule fragment;
    VK(vkCreateShaderModule(dev,&si,NULL,&fragment));free(code);
    image color=make_image(VK_FORMAT_B10G11R11_UFLOAT_PACK32,854,480,1,1,VK_IMAGE_ASPECT_COLOR_BIT,VK_IMAGE_VIEW_TYPE_2D,VK_IMAGE_USAGE_COLOR_ATTACHMENT_BIT,NULL);
    image depth=make_image(VK_FORMAT_D32_SFLOAT,854,480,1,1,VK_IMAGE_ASPECT_DEPTH_BIT,VK_IMAGE_VIEW_TYPE_2D,VK_IMAGE_USAGE_DEPTH_STENCIL_ATTACHMENT_BIT|VK_IMAGE_USAGE_TRANSFER_SRC_BIT,NULL);
    VkAttachmentDescription attachments[2]={
        {.format=VK_FORMAT_B10G11R11_UFLOAT_PACK32,.samples=1,.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED,.finalLayout=VK_IMAGE_LAYOUT_GENERAL},
        {.format=VK_FORMAT_D32_SFLOAT,.samples=1,.loadOp=VK_ATTACHMENT_LOAD_OP_CLEAR,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,.initialLayout=VK_IMAGE_LAYOUT_UNDEFINED,.finalLayout=VK_IMAGE_LAYOUT_GENERAL}};
    VkAttachmentReference cr={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL},dr={1,VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL};
    VkSubpassDescription subpass={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&cr,.pDepthStencilAttachment=&dr};
    VkRenderPassCreateInfo ri={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=2,.pAttachments=attachments,.subpassCount=1,.pSubpasses=&subpass};
    VkRenderPass pass;VK(vkCreateRenderPass(dev,&ri,NULL,&pass));
    VkImageView views[2]={color.view,depth.view};
    VkFramebufferCreateInfo fi={.sType=VK_STRUCTURE_TYPE_FRAMEBUFFER_CREATE_INFO,.renderPass=pass,.attachmentCount=2,.pAttachments=views,.width=854,.height=480,.layers=1};VkFramebuffer framebuffer;
    VK(vkCreateFramebuffer(dev,&fi,NULL,&framebuffer));
    VkViewport viewport={0,0,854,480,0,1};VkRect2D scissor={{0,0},{854,480}};
    VkPipelineViewportStateCreateInfo vp={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.pViewports=&viewport,.scissorCount=1,.pScissors=&scissor};
    VkPipelineRasterizationStateCreateInfo raster={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.rasterizerDiscardEnable=discard,.polygonMode=VK_POLYGON_MODE_FILL,.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE,.lineWidth=1};
    VkPipelineMultisampleStateCreateInfo samples={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=1};
    VkPipelineDepthStencilStateCreateInfo ds={.sType=VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO,.depthTestEnable=1,.depthWriteEnable=1,.depthCompareOp=VK_COMPARE_OP_LESS};
    VkPipelineColorBlendAttachmentState ba={0};VkPipelineColorBlendStateCreateInfo blend={.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&ba};
    VkPipelineShaderStageCreateInfo stages[2]={
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_MESH_BIT_EXT,.module=shader,.pName="main"},
        {.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=fragment,.pName="main"}};
    VkGraphicsPipelineCreateInfo pi={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=2,.pStages=stages,.pViewportState=&vp,.pRasterizationState=&raster,.pMultisampleState=&samples,.pDepthStencilState=&ds,.pColorBlendState=&blend,.layout=layout,.renderPass=pass};
    VkPipeline pipeline;VK(vkCreateGraphicsPipelines(dev,VK_NULL_HANDLE,1,&pi,NULL,&pipeline));
    CHECK(!errors);VkCommandPool cp;VkCommandPoolCreateInfo ci={.sType=VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO,.queueFamilyIndex=qf};VK(vkCreateCommandPool(dev,&ci,NULL,&cp));
    VkCommandBuffer cb;VkCommandBufferAllocateInfo cai={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,.commandPool=cp,.level=VK_COMMAND_BUFFER_LEVEL_PRIMARY,.commandBufferCount=1};VK(vkAllocateCommandBuffers(dev,&cai,&cb));
    VkCommandBufferBeginInfo bi={.sType=VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO};VK(vkBeginCommandBuffer(cb,&bi));
    image texture={0};VkSampler sampler=VK_NULL_HANDLE;
    if(real) {
        texture=make_image(texture_fmt,texture_w,texture_h,texture_levels,texture_layers,texture_aspect,texture_type,VK_IMAGE_USAGE_SAMPLED_BIT|VK_IMAGE_USAGE_TRANSFER_DST_BIT,texture_swz);
        snprintf(path,sizeof path,"%s.%s",argv[1],texture_name);void *data=load(path,&bytes);VkBuffer upload=buffer(bytes,data);free(data);
        transition(cb,texture.image,texture_aspect,texture_levels,texture_layers);
        VkBufferImageCopy copies[32];size_t offset=0;
        for(unsigned i=0;i<texture_levels;i++) {
            unsigned w=texture_w>>i,h=texture_h>>i;w=w?w:1;h=h?h:1;offset=(offset+15)&~(size_t)15;
            copies[i]=(VkBufferImageCopy){.bufferOffset=offset,.imageSubresource={texture_aspect,i,0,texture_layers},.imageExtent={w,h,1}};
            offset+=(size_t)((w+3)/4)*((h+3)/4)*16*texture_layers;
        }CHECK(offset==bytes);
        vkCmdCopyBufferToImage(cb,upload,texture.image,VK_IMAGE_LAYOUT_GENERAL,texture_levels,copies);
        VkMemoryBarrier mb={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_SHADER_READ_BIT};
        vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_FRAGMENT_SHADER_BIT,0,1,&mb,0,NULL,0,NULL);
        typedef struct {uint8_t minf,magf,ws,wt,wr,cmp_mode,cmp_func,reduction;float lod_min,lod_max,lod_bias,aniso,border[4];} sampler_parameters;
        snprintf(path,sizeof path,"%s.%s",argv[1],sampler_name);sampler_parameters *sp=load(path,&bytes);
        CHECK(bytes==sizeof *sp && sp->ws==1 && sp->wt==1 && sp->wr==1 && sp->aniso<=1 && !sp->cmp_mode && !sp->reduction);
        VkSamplerCreateInfo sci={.sType=VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO,.magFilter=sp->magf?VK_FILTER_LINEAR:VK_FILTER_NEAREST,
            .minFilter=(sp->minf==1 || sp->minf==3 || sp->minf==5)?VK_FILTER_LINEAR:VK_FILTER_NEAREST,
            .mipmapMode=sp->minf>=4?VK_SAMPLER_MIPMAP_MODE_LINEAR:VK_SAMPLER_MIPMAP_MODE_NEAREST,
            .addressModeU=VK_SAMPLER_ADDRESS_MODE_REPEAT,.addressModeV=VK_SAMPLER_ADDRESS_MODE_REPEAT,.addressModeW=VK_SAMPLER_ADDRESS_MODE_REPEAT,
            .mipLodBias=sp->lod_bias,.minLod=sp->lod_min,.maxLod=sp->minf<=1?.25f:sp->lod_max};
        VK(vkCreateSampler(dev,&sci,NULL,&sampler));free(sp);
        VkDescriptorImageInfo ii={sampler,texture.view,VK_IMAGE_LAYOUT_GENERAL};
        VkWriteDescriptorSet wr={.sType=VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET,.dstSet=sets[0],.dstBinding=texture_binding,.descriptorCount=1,.descriptorType=VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER,.pImageInfo=&ii};
        vkUpdateDescriptorSets(dev,1,&wr,0,NULL);
    }
    VkClearValue clears[2]={{{{0,0,0,0}}},{.depthStencil={1,0}}};
    VkRenderPassBeginInfo begin={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_BEGIN_INFO,.renderPass=pass,.framebuffer=framebuffer,.renderArea=scissor,.clearValueCount=2,.pClearValues=clears};
    vkCmdBeginRenderPass(cb,&begin,VK_SUBPASS_CONTENTS_INLINE);vkCmdBindPipeline(cb,VK_PIPELINE_BIND_POINT_GRAPHICS,pipeline);
    uint32_t offsets[32];unsigned noffsets=0;
    for(unsigned stage_index=0;stage_index<2;stage_index++)for(unsigned binding=0;binding<256;binding++)for(unsigned i=0;i<count;i++)
        if(inputs[i].type==8 && (inputs[i].stage==7)==stage_index && inputs[i].binding==binding){CHECK(inputs[i].offset<=UINT32_MAX);offsets[noffsets++]=(uint32_t)inputs[i].offset;}
    vkCmdBindDescriptorSets(cb,VK_PIPELINE_BIND_POINT_GRAPHICS,layout,1,2,sets,noffsets,offsets);uint32_t args[2]={0,groups};
    vkCmdPushConstants(cb,layout,VK_SHADER_STAGE_MESH_BIT_EXT,0,sizeof args,args);
    PFN_vkCmdDrawMeshTasksEXT draw=(PFN_vkCmdDrawMeshTasksEXT)vkGetDeviceProcAddr(dev,"vkCmdDrawMeshTasksEXT");CHECK(draw);draw(cb,groups,1,1);
    vkCmdEndRenderPass(cb);
    size_t depth_bytes=854u*480u*4u;void *empty=calloc(1,depth_bytes);CHECK(empty);VkBuffer readback=buffer(depth_bytes,empty);free(empty);
    VkDeviceMemory readback_memory=allocated_memory[allocated_count-1];
    VkImageMemoryBarrier rb={.sType=VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_DEPTH_STENCIL_ATTACHMENT_WRITE_BIT,.dstAccessMask=VK_ACCESS_TRANSFER_READ_BIT,
        .oldLayout=VK_IMAGE_LAYOUT_GENERAL,.newLayout=VK_IMAGE_LAYOUT_GENERAL,.srcQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,.dstQueueFamilyIndex=VK_QUEUE_FAMILY_IGNORED,
        .image=depth.image,.subresourceRange={VK_IMAGE_ASPECT_DEPTH_BIT,0,1,0,1}};
    vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_EARLY_FRAGMENT_TESTS_BIT|VK_PIPELINE_STAGE_LATE_FRAGMENT_TESTS_BIT,VK_PIPELINE_STAGE_TRANSFER_BIT,0,0,NULL,0,NULL,1,&rb);
    VkBufferImageCopy depth_copy={.imageSubresource={VK_IMAGE_ASPECT_DEPTH_BIT,0,0,1},.imageExtent={854,480,1}};
    vkCmdCopyImageToBuffer(cb,depth.image,VK_IMAGE_LAYOUT_GENERAL,readback,1,&depth_copy);
    VkMemoryBarrier host={.sType=VK_STRUCTURE_TYPE_MEMORY_BARRIER,.srcAccessMask=VK_ACCESS_TRANSFER_WRITE_BIT,.dstAccessMask=VK_ACCESS_HOST_READ_BIT};
    vkCmdPipelineBarrier(cb,VK_PIPELINE_STAGE_TRANSFER_BIT,VK_PIPELINE_STAGE_HOST_BIT,0,1,&host,0,NULL,0,NULL);
    VK(vkEndCommandBuffer(cb));CHECK(!errors);
    VkFence fence;VkFenceCreateInfo fci={.sType=VK_STRUCTURE_TYPE_FENCE_CREATE_INFO};VK(vkCreateFence(dev,&fci,NULL,&fence));
    VkSubmitInfo submit={.sType=VK_STRUCTURE_TYPE_SUBMIT_INFO,.commandBufferCount=1,.pCommandBuffers=&cb};
    printf("submitting %u groups discard=%d robust=%u dynamic=%u\n",groups,discard,robust,dynamic);VK(vkQueueSubmit(queue,1,&submit,fence));
    VkResult result=vkWaitForFences(dev,1,&fence,VK_TRUE,10000000000ull);
    printf("fence result=%d validation_errors=%u\n",result,errors);
    if(result || errors)return 1;
    void *pixels;VK(vkMapMemory(dev,readback_memory,0,depth_bytes,0,&pixels));
    uint64_t hash=14695981039346656037ull;unsigned changed=0,nonfinite=0;
    for(size_t i=0;i<depth_bytes;i++)hash=(hash^((unsigned char *)pixels)[i])*1099511628211ull;
    for(size_t i=0;i<depth_bytes/4;i++){float z=((float *)pixels)[i];changed+=z!=1.0f;nonfinite+=!isfinite(z);}
    printf("depth hash=%016llx changed=%u nonfinite=%u\n",(unsigned long long)hash,changed,nonfinite);
    const char *depth_out=getenv("DM_MESH_DEPTH_OUT");
    if(depth_out){FILE *output=fopen(depth_out,"wb");CHECK(output && fwrite(pixels,1,depth_bytes,output)==depth_bytes && !fclose(output));}
    vkUnmapMemory(dev,readback_memory);
    VK(vkDeviceWaitIdle(dev));vkDestroyFence(dev,fence,NULL);vkDestroyCommandPool(dev,cp,NULL);
    vkDestroyPipeline(dev,pipeline,NULL);vkDestroyShaderModule(dev,shader,NULL);vkDestroyShaderModule(dev,fragment,NULL);
    vkDestroyFramebuffer(dev,framebuffer,NULL);vkDestroyRenderPass(dev,pass,NULL);free_image(color);free_image(depth);
    if(real){vkDestroySampler(dev,sampler,NULL);free_image(texture);}
    vkDestroyDescriptorPool(dev,pool,NULL);vkDestroyPipelineLayout(dev,layout,NULL);
    for(unsigned i=0;i<3;i++)vkDestroyDescriptorSetLayout(dev,layouts[i],NULL);
    for(unsigned i=0;i<allocated_count;i++){vkDestroyBuffer(dev,allocated_buffers[i],NULL);vkFreeMemory(dev,allocated_memory[i],NULL);}
    vkDestroyDevice(dev,NULL);
    PFN_vkDestroyDebugUtilsMessengerEXT destroy_debug=(PFN_vkDestroyDebugUtilsMessengerEXT)vkGetInstanceProcAddr(instance,"vkDestroyDebugUtilsMessengerEXT");
    destroy_debug(instance,messenger,NULL);vkDestroyInstance(instance,NULL);return errors?1:0;
}
