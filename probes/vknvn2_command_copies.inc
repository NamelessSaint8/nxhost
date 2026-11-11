// Copy owns parent and child bytes; Call references a child that stays live.
static void command_copy_tests(void){
    uint8_t *memory=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(memory==MAP_FAILED)abort();
    pool_t pool={.mem=memory,.size=65536};NVNcommandBuffer source,copy,caller,nested;
    NVNT_nvnCommandBufferInitialize init=atlas_api("nvnCommandBufferInitialize");
    NVNT_nvnCommandBufferAddCommandMemory add=atlas_api("nvnCommandBufferAddCommandMemory");
    NVNT_nvnCommandBufferBeginRecording begin=atlas_api("nvnCommandBufferBeginRecording");
    NVNT_nvnCommandBufferEndRecording end=atlas_api("nvnCommandBufferEndRecording");
    NVNT_nvnCommandBufferSetRenderTargets targets=atlas_api("nvnCommandBufferSetRenderTargets");
    NVNT_nvnCommandBufferSetViewport viewport=atlas_api("nvnCommandBufferSetViewport");
    NVNT_nvnCommandBufferClearColor clear=atlas_api("nvnCommandBufferClearColor");
    NVNT_nvnCommandBufferCopyCommands duplicate=atlas_api("nvnCommandBufferCopyCommands");
    NVNT_nvnCommandBufferCallCommands call=atlas_api("nvnCommandBufferCallCommands");
    NVNT_nvnCommandBufferSetScissor scissor=atlas_api("nvnCommandBufferSetScissor");
    init(&source,NULL);init(&copy,NULL);init(&caller,NULL);init(&nested,NULL);
    tex_t target={.magic=MAGIC('T','E','X',0),.serial=88001};target.d=(nvn_texdesc){.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA8,.width=32,.height=32,.depth=1,.levels=1,.samples=1};
    const NVNtexture *attachment=(NVNtexture*)&target;
    float colors[3][4]={{1,0,0,1},{0,1,0,1},{0,0,1,1}};NVNcommandHandle handle=0,copied=0,called=0,outer=0;
    for(unsigned phase=0;phase<4;phase++){
        add(&source,(NVNmemoryPool*)&pool,0,8192);begin(&source);viewport(&source,0,0,32,32);targets(&source,1,&attachment,NULL,NULL,NULL);clear(&source,0,colors[phase==0?0:phase==1?2:1],15);handle=end(&source);
        if(phase==0){add(&copy,(NVNmemoryPool*)&pool,8192,128);begin(&copy);scissor(&copy,0,0,32,32);duplicate(&copy,1,&handle);copied=end(&copy);
            // Reuse source bytes for a different valid command stream first.
            add(&source,(NVNmemoryPool*)&pool,0,8192);begin(&source);viewport(&source,0,0,32,32);targets(&source,1,&attachment,NULL,NULL,NULL);clear(&source,0,colors[2],15);handle=end(&source);
        }else if(phase==1){add(&caller,(NVNmemoryPool*)&pool,16384,8192);begin(&caller);call(&caller,1,&handle);called=end(&caller);
            add(&nested,(NVNmemoryPool*)&pool,24576,8192);begin(&nested);duplicate(&nested,1,&called);outer=end(&nested);
        }else if(phase==2){memset(memory+16384,0x41,8192);}else{memset(memory,0x41,8192);}
        NVNcommandHandle submitted=phase==0||phase==3?copied:phase==1?called:outer;
        mtl_sub_begin();mtl_exec((const uint8_t*)(uintptr_t)submitted);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        uint8_t pixels[4096];NVNcopyRegion region={.width=32,.height=32,.depth=1};mtl_read_texels(&target,0,0,&region,pixels,128,sizeof pixels);
        unsigned color=phase==0||phase==3?0:2;uint8_t expected[4]={colors[color][0]*255,colors[color][1]*255,colors[color][2]*255,255};int ok=!memcmp(pixels+4*(32*16+16),expected,4);
        checks++;failed+=!ok;printf("command lifetime phase=%u %s pixel=%u,%u,%u,%u\n",phase,ok?"PASS":"FAIL",pixels[2112],pixels[2113],pixels[2114],pixels[2115]);if(!ok)break;
    }
    munmap(memory,65536);
}
