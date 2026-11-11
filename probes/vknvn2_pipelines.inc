// Compile observed game stage combinations with production modules/layouts.
// No fabricated game buffers are bound and no game shader is dispatched.
#include <inttypes.h>
#include <time.h>
static void observed_pipelines(const char *path) {
    FILE *file=fopen(path,"r");if(!file)abort();
    VkAttachmentDescription attachment={.format=VK_FORMAT_R8G8B8A8_UNORM,.samples=VK_SAMPLE_COUNT_1_BIT,.loadOp=VK_ATTACHMENT_LOAD_OP_DONT_CARE,.storeOp=VK_ATTACHMENT_STORE_OP_STORE,.initialLayout=VK_IMAGE_LAYOUT_GENERAL,.finalLayout=VK_IMAGE_LAYOUT_GENERAL};
    VkAttachmentReference color={0,VK_IMAGE_LAYOUT_COLOR_ATTACHMENT_OPTIMAL};
    VkSubpassDescription subpass={.pipelineBindPoint=VK_PIPELINE_BIND_POINT_GRAPHICS,.colorAttachmentCount=1,.pColorAttachments=&color};
    VkAttachmentReference depth={1,VK_IMAGE_LAYOUT_DEPTH_STENCIL_ATTACHMENT_OPTIMAL};
    VkAttachmentDescription attachments[2];
    VkRenderPassCreateInfo pass_info={.sType=VK_STRUCTURE_TYPE_RENDER_PASS_CREATE_INFO,.attachmentCount=1,.pAttachments=attachments,.subpassCount=1,.pSubpasses=&subpass};
    VkViewport viewport={0,0,32,32,0,1};VkRect2D scissor={{0,0},{32,32}};
    VkPipelineViewportStateCreateInfo vp={.sType=VK_STRUCTURE_TYPE_PIPELINE_VIEWPORT_STATE_CREATE_INFO,.viewportCount=1,.pViewports=&viewport,.scissorCount=1,.pScissors=&scissor};
    VkPipelineRasterizationStateCreateInfo raster={.sType=VK_STRUCTURE_TYPE_PIPELINE_RASTERIZATION_STATE_CREATE_INFO,.polygonMode=VK_POLYGON_MODE_FILL,.cullMode=VK_CULL_MODE_NONE,.frontFace=VK_FRONT_FACE_COUNTER_CLOCKWISE,.lineWidth=1};
    VkPipelineMultisampleStateCreateInfo samples={.sType=VK_STRUCTURE_TYPE_PIPELINE_MULTISAMPLE_STATE_CREATE_INFO,.rasterizationSamples=VK_SAMPLE_COUNT_1_BIT};
    VkPipelineColorBlendAttachmentState blend_attachment={.colorWriteMask=15};VkPipelineColorBlendStateCreateInfo blend={.sType=VK_STRUCTURE_TYPE_PIPELINE_COLOR_BLEND_STATE_CREATE_INFO,.attachmentCount=1,.pAttachments=&blend_attachment};
    char line[512];
    while(fgets(line,sizeof line,file)){
        uint64_t task_key,mesh_key,pixel_key;if(line[0]=='#')continue;
        unsigned cf=0x25,df=0,ms=1,dt=0,dw=0,compare=8,cull=0,be=0,src=2,dst=1,srca=2,dsta=1,eq=1,eqa=1,mask=15;
        int fields=sscanf(line,"%"SCNx64" %"SCNx64" %"SCNx64" %x %x %u %u %u %u %u %u %u %u %u %u %u %u %u",&task_key,&mesh_key,&pixel_key,&cf,&df,&ms,&dt,&dw,&compare,&cull,&be,&src,&dst,&srca,&dsta,&eq,&eqa,&mask);
        if(fields!=3 && fields!=18)abort();
        const vkfmt_t *color_format=vk_fmt((int)cf),*depth_format=df?vk_fmt((int)df):NULL;
        if(!color_format || (df && !depth_format) || compare<1 || compare>8 || eq<1 || eq>5 || eqa<1 || eqa>5)abort();
        attachment.format=color_format->vk;attachment.samples=(VkSampleCountFlagBits)ms;attachments[0]=attachment;
        attachments[1]=attachment;if(depth_format)attachments[1].format=depth_format->vk;
        pass_info.attachmentCount=df?2:1;subpass.pDepthStencilAttachment=df?&depth:NULL;
        VkRenderPass pass;VKCHK(vkCreateRenderPass(V.dev,&pass_info,NULL,&pass));
        // These are NVN's ordinary factors; reject unimplemented probe inputs.
        static const VkBlendFactor factors[]={VK_BLEND_FACTOR_ZERO,VK_BLEND_FACTOR_ZERO,VK_BLEND_FACTOR_ONE,VK_BLEND_FACTOR_SRC_COLOR,VK_BLEND_FACTOR_ONE_MINUS_SRC_COLOR,VK_BLEND_FACTOR_SRC_ALPHA,VK_BLEND_FACTOR_ONE_MINUS_SRC_ALPHA,VK_BLEND_FACTOR_DST_ALPHA,VK_BLEND_FACTOR_ONE_MINUS_DST_ALPHA,VK_BLEND_FACTOR_DST_COLOR,VK_BLEND_FACTOR_ONE_MINUS_DST_COLOR,VK_BLEND_FACTOR_SRC_ALPHA_SATURATE};
        if(src>=12 || dst>=12 || srca>=12 || dsta>=12)abort();
        int num=vk_color_num(color_format->vk);
        blend_attachment=(VkPipelineColorBlendAttachmentState){.blendEnable=be && !num,.srcColorBlendFactor=factors[src],.dstColorBlendFactor=factors[dst],.colorBlendOp=(VkBlendOp)(eq-1),.srcAlphaBlendFactor=factors[srca],.dstAlphaBlendFactor=factors[dsta],.alphaBlendOp=(VkBlendOp)(eqa-1),.colorWriteMask=mask};
        samples.rasterizationSamples=(VkSampleCountFlagBits)ms;raster.cullMode=cull;
        VkPipelineDepthStencilStateCreateInfo ds={.sType=VK_STRUCTURE_TYPE_PIPELINE_DEPTH_STENCIL_STATE_CREATE_INFO,.depthTestEnable=dt,.depthWriteEnable=dt && dw,.depthCompareOp=(VkCompareOp)(compare-1)};
        vkshader_t *task=task_key?vk_shader(task_key,6):NULL,*mesh=vk_shader(mesh_key,7),*pixel=vk_shader(pixel_key,1);
        int valid=mesh && pixel && (!task_key || task);
        if(valid){
            VkDescriptorSetLayout sets[5]={task?task->dsl:VK_NULL_HANDLE,pixel->dsl,mesh->dsl};VkPipelineLayout layout=vk_pipeline_layout(sets,3,1);
            VkPipelineShaderStageCreateInfo stages[3];memset(stages,0,sizeof stages);unsigned n=0;
            if(task)stages[n++]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_TASK_BIT_EXT,.module=task->mod,.pName="main"};
            stages[n++]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_MESH_BIT_EXT,.module=mesh->mod,.pName="main"};
            stages[n++]=(VkPipelineShaderStageCreateInfo){.sType=VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,.stage=VK_SHADER_STAGE_FRAGMENT_BIT,.module=vk_shader_module(pixel,0,0,0,0,mesh->mesh.primitive_mask,num==1,num==2),.pName="main"};
            if(!stages[n-1].module)abort();
            VkGraphicsPipelineCreateInfo info={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.stageCount=n,.pStages=stages,.pViewportState=&vp,.pRasterizationState=&raster,.pMultisampleState=&samples,.pDepthStencilState=&ds,.pColorBlendState=&blend,.layout=layout,.renderPass=pass};
            struct timespec before,after;clock_gettime(CLOCK_MONOTONIC,&before);VkPipeline pipeline=VK_NULL_HANDLE;VkResult result=vkCreateGraphicsPipelines(V.dev,VK_NULL_HANDLE,1,&info,NULL,&pipeline);clock_gettime(CLOCK_MONOTONIC,&after);
            valid=result==VK_SUCCESS;printf("observed pipeline task=%016"PRIx64" mesh=%016"PRIx64" pixel=%016"PRIx64" color=%x depth=%x samples=%u blend=%u mask=%x depth_test=%u cull=%u result=%d compile_ms=%.3f %s\n",task_key,mesh_key,pixel_key,cf,df,ms,blend_attachment.blendEnable,mask,dt,cull,result,(after.tv_sec-before.tv_sec)*1000.0+(after.tv_nsec-before.tv_nsec)/1e6,valid?"PASS":"FAIL");
            if(pipeline)vkDestroyPipeline(V.dev,pipeline,NULL);
        }else printf("observed pipeline missing shader FAIL\n");
        checks++;failed+=!valid;vkDestroyRenderPass(V.dev,pass,NULL);
    }
    fclose(file);
}
