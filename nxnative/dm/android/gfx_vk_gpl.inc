// Share a compiled fragment subset across vertex/input/blend variants. The
// full pipeline layout and compatible render pass remain in the key, so no
// independent-descriptor-set assumptions or interface approximations are made.
typedef struct {
    VkShaderModule module;VkPipelineLayout layout;VkRenderPass render_pass;uint64_t atlas;
    uint32_t samples,a2c,dt,dw,df,st,sf[2],sfail[2],szfail[2],szpass[2];
} fragment_key;
static nvn_hmap g_fragment_libraries={.klen=sizeof(fragment_key)};
static pthread_mutex_t g_fragment_mu=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t g_fragment_ready=PTHREAD_COND_INITIALIZER;
static uint64_t g_fragment_created,g_fragment_reused;
void vk_fragment_library_stats(uint64_t *created,uint64_t *reused){pthread_mutex_lock(&g_fragment_mu);*created=g_fragment_created;*reused=g_fragment_reused;pthread_mutex_unlock(&g_fragment_mu);}
static VkPipeline fragment_library(const pkey *key,VkPipelineLayout layout,VkRenderPass render_pass,const VkPipelineShaderStageCreateInfo *stage,const VkPipelineMultisampleStateCreateInfo *ms,const VkPipelineDepthStencilStateCreateInfo *ds) {
    fragment_key k;memset(&k,0,sizeof k);k.module=stage->module;k.layout=layout;k.render_pass=render_pass;k.atlas=key->atlas[1];k.samples=key->samples;k.a2c=key->a2c;k.dt=key->dt;k.dw=key->dw;k.df=key->df;k.st=key->st;
    memcpy(k.sf,key->sf,sizeof k.sf);memcpy(k.sfail,key->sfail,sizeof k.sfail);memcpy(k.szfail,key->szfail,sizeof k.szfail);memcpy(k.szpass,key->szpass,sizeof k.szpass);
    pthread_mutex_lock(&g_fragment_mu);VkPipeline library;
    while((library=nvn_hm_get(&g_fragment_libraries,&k))==(VkPipeline)2)pthread_cond_wait(&g_fragment_ready,&g_fragment_mu);
    if(library){g_fragment_reused++;pthread_mutex_unlock(&g_fragment_mu);return library==(VkPipeline)1?VK_NULL_HANDLE:library;}
    nvn_hm_put(&g_fragment_libraries,&k,(VkPipeline)2);pthread_mutex_unlock(&g_fragment_mu);
    VkGraphicsPipelineLibraryCreateInfoEXT subset={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_LIBRARY_CREATE_INFO_EXT,.flags=VK_GRAPHICS_PIPELINE_LIBRARY_FRAGMENT_SHADER_BIT_EXT};
    VkDynamicState states[]={VK_DYNAMIC_STATE_STENCIL_COMPARE_MASK,VK_DYNAMIC_STATE_STENCIL_WRITE_MASK,VK_DYNAMIC_STATE_STENCIL_REFERENCE};
    VkPipelineDynamicStateCreateInfo dynamic={.sType=VK_STRUCTURE_TYPE_PIPELINE_DYNAMIC_STATE_CREATE_INFO,.dynamicStateCount=3,.pDynamicStates=states};
    VkGraphicsPipelineCreateInfo info={.sType=VK_STRUCTURE_TYPE_GRAPHICS_PIPELINE_CREATE_INFO,.pNext=&subset,.flags=VK_PIPELINE_CREATE_LIBRARY_BIT_KHR,.stageCount=1,.pStages=stage,.pMultisampleState=ms,.pDepthStencilState=ds,.pDynamicState=&dynamic,.layout=layout,.renderPass=render_pass,.basePipelineIndex=-1};
    VkPipelineCreationFeedback feedback={0};
    VkPipelineCreationFeedbackCreateInfo feedback_ci={.sType=VK_STRUCTURE_TYPE_PIPELINE_CREATION_FEEDBACK_CREATE_INFO,.pNext=info.pNext,.pPipelineCreationFeedback=&feedback};
    if(V.has_cache_feedback)info.pNext=&feedback_ci;
    uint64_t start=tick();VkResult result=vkCreateGraphicsPipelines(V.dev,V.pcache,1,&info,NULL,&library);
    VKLOG("fragment library result=%d ms=%.2f shader=%016llx",result,(tick()-start)/1e6,(unsigned long long)key->key[1]);
    if(result)library=(VkPipeline)1;else vk_pipeline_cache_compiled(V.has_cache_feedback?&feedback:NULL);
    pthread_mutex_lock(&g_fragment_mu);if(!result)g_fragment_created++;nvn_hm_put(&g_fragment_libraries,&k,library);pthread_cond_broadcast(&g_fragment_ready);pthread_mutex_unlock(&g_fragment_mu);
    return library==(VkPipeline)1?VK_NULL_HANDLE:library;
}
