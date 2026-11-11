// Integer vertex storage is fetched as integer words, then bitcast for the
// translator's float register interface. Exercise sign/zero extension on GPU.
static void vertex_bits_tests(void) {
    uint8_t *memory=mmap(NULL,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(memory==MAP_FAILED)abort();mtl_pool_add(memory,65536);
    const int formats[]={NVN_FORMAT_RGBA8UI,NVN_FORMAT_RGBA8I,NVN_FORMAT_RGBA16UI,NVN_FORMAT_RGBA16I,NVN_FORMAT_RGBA32UI,NVN_FORMAT_RGBA32I};
    for(unsigned f=0;f<8;f++){
        unsigned which=f%6,bytes=which<2?1:which<4?2:4;int signedness=which&1;
        uint32_t values[4]={signedness?(uint32_t)-7:7,12,123,1};for(unsigned i=0;i<4;i++)memcpy(memory+4096+i*bytes,&values[i],bytes);
        tex_t target={.magic=MAGIC('T','E','X',0),.serial=41000+f,.d={.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA8,.width=8,.height=8,.depth=1,.levels=1,.samples=1}};
        prog_t program={.serial=41100+f,.nstage=2};program.sd[0].data=signedness?31:32;program.sd[1].data=10;
        size_t used=0;
#define VIN_EMIT(OP,X) do{size_t n=(8+sizeof(X)+7)&~7ull;op_hdr h={OP,(uint32_t)n};memcpy(memory+used,&h,8);memcpy(memory+used+8,&(X),sizeof(X));used+=n;}while(0)
        p_set_rt rt={.n=1};rt.color[0]=&target;VIN_EMIT(OP_SET_RT,rt);p_clear_color clear={.mask=15,.rgba={0,0,1,1}};VIN_EMIT(OP_CLEAR_COLOR,clear);
        p_viewports vp={.n=1};vp.v[0][2]=vp.v[0][3]=8;VIN_EMIT(OP_VIEWPORTS,vp);p_scissor sc={0,0,8,8};VIN_EMIT(OP_SCISSOR,sc);
        p_bind_program bind={&program,0xff};VIN_EMIT(OP_BIND_PROGRAM,bind);
        p_bind_vattr attr={.n=1};va_st state={.stream=0,.fmt=formats[which]};memcpy(&attr.st[0],&state,4);VIN_EMIT(OP_BIND_VATTR,attr);
        p_bind_vstream stream={.n=1};VIN_EMIT(OP_BIND_VSTREAM,stream);p_bind_vbuf buffer={.n=1};buffer.r[0]=(NVNbufferRange){(uint64_t)(memory+4096),16};VIN_EMIT(OP_BIND_VBUF,buffer);
        p_draw draw={.prim=4,.count=3,.instances=1};VIN_EMIT(OP_DRAW,draw);op_hdr end={OP_END,8};memcpy(memory+used,&end,8);
#undef VIN_EMIT
        mtl_sub_begin();mtl_exec(memory);if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        uint8_t pixels[256];NVNcopyRegion region={0,0,0,8,8,1};mtl_read_texels(&target,0,0,&region,pixels,32,256);int ok=1;
        for(unsigned i=0;i<64;i++)ok&=pixels[i*4]==0 && pixels[i*4+1]==255 && pixels[i*4+2]==0 && pixels[i*4+3]==255;
        checks++;failed+=!ok;printf("vertex raw bits format=%x repeat=%u %s\n",formats[which],f>=6,ok?"PASS":"FAIL");
    }
    mtl_pool_del(memory);munmap(memory,65536);
}
