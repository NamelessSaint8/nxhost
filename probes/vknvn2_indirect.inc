// Native GPU-produced indirect counts. Only the second draw has vertices, so
// count 0/1 must keep the blue clear; count 2+ must draw the green triangle.
#define INDIRECT_EMIT(OP,X) driver_emit(OP,&(X),sizeof(X))
static void indirect_tests(void){
    uint8_t *mem=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();mtl_pool_add(mem,65536);
    for(unsigned indexed=0;indexed<2;indexed++)for(unsigned phase=0;phase<5;phase++){
        unsigned requested=(unsigned[]){0,1,2,100,1}[phase];dm_guest_write_prepare(mem+8192,4096);memset(mem+8192,0,4096);
        uint32_t *args=(uint32_t*)(mem+8192);args[1]=1;args[8]=3;args[9]=1;
        uint32_t *indices=(uint32_t*)(mem+8704);indices[0]=0;indices[1]=1;indices[2]=2;
        *(uint32_t*)(mem+8800)=requested;*(uint32_t*)(mem+8804)=999;
        tex_t target={.magic=MAGIC('T','E','X',0),.serial=39000+indexed*10+phase};target.d=(nvn_texdesc){.width=32,.height=32,.depth=1,.levels=1,.samples=1,.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA8};
        prog_t program={.serial=39100+indexed*10+phase,.nstage=2};program.sd[0].data=9;program.sd[1].data=10;
        driver_begin(mem);p_set_rt rt={.n=1};rt.color[0]=&target;INDIRECT_EMIT(OP_SET_RT,rt);p_viewports vp={.n=1};vp.v[0][2]=vp.v[0][3]=32;INDIRECT_EMIT(OP_VIEWPORTS,vp);p_scissor sc={0,0,32,32};INDIRECT_EMIT(OP_SCISSOR,sc);
        p_clear_color clear={.index=0,.mask=15,.rgba={0,0,1,1}};INDIRECT_EMIT(OP_CLEAR_COLOR,clear);p_bind_program bind={&program,0xff};INDIRECT_EMIT(OP_BIND_PROGRAM,bind);
        for(unsigned i=0;i<2;i++)if(indexed){p_draw_idx d={.prim=4,.itype=2,.instances=1,.ibuf=(uint64_t)indices,.ind=(uint64_t)(mem+9216+i*32),.mdi_cnt=(uint64_t)(mem+8804),.mdi_i=(int)i};INDIRECT_EMIT(OP_DRAW_IDX,d);}
            else{p_draw d={.prim=4,.instances=1,.ind=(uint64_t)(mem+9216+i*32),.mdi_cnt=(uint64_t)(mem+8804),.mdi_i=(int)i};INDIRECT_EMIT(OP_DRAW,d);}
        mtl_sub_begin();mtl_sub_copy((uint64_t)(mem+8192),(uint64_t)(mem+9216),64);mtl_sub_copy((uint64_t)(mem+8800),(uint64_t)(mem+8804),4);driver_end();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        uint8_t pixels[4096];NVNcopyRegion region={0,0,0,32,32,1};mtl_read_texels(&target,0,0,&region,pixels,128,4096);uint8_t *p=pixels+(16*32+16)*4;int green=requested>=2;
        int ok=p[0]==0 && p[1]==(green?255:0) && p[2]==(green?0:255) && p[3]==255;checks++;failed+=!ok;printf("indirect count indexed=%u GPU-count=%u stride=32 %s pixel=%u,%u,%u,%u\n",indexed,requested,ok?"PASS":"FAIL",p[0],p[1],p[2],p[3]);
    }
    mtl_pool_del(mem);munmap(mem,65536);
}

#undef INDIRECT_EMIT
