// Driver ABI checks through real replay/descriptors and GPU-produced dispatch args.
static uint8_t *driver_job;static size_t driver_used;static uint8_t driver_pushed[2][256];
static prog_t driver_programs[8];static unsigned driver_program_slot;
static void driver_check(int ok,const char *name,unsigned phase) { checks++;failed+=!ok;printf("driver phase=%u %s %s\n",phase,name,ok?"PASS":"FAIL"); }
static void driver_emit(uint32_t op,const void *data,size_t size) {
    size_t len=(8+size+7)&~7ull;if(driver_used+len+8>65536)abort();op_hdr h={op,(uint32_t)len};memcpy(driver_job+driver_used,&h,8);memcpy(driver_job+driver_used+8,data,size);driver_used+=len;
}
#define DRIVER_EMIT(OP,X) driver_emit(OP,&(X),sizeof(X))
static void driver_begin(uint8_t *mem) { driver_job=mem;driver_used=0; }
static void driver_end(void) { op_hdr end={OP_END,8};memcpy(driver_job+driver_used,&end,8);mtl_exec(driver_job); }
static void driver_push(int compute,unsigned offset,unsigned bytes,const void *data) {
    struct { uint16_t compute,offset;uint32_t size;uint8_t data[256]; } p={.compute=(uint16_t)compute,.offset=(uint16_t)offset,.size=bytes};
    if(offset+bytes>256)abort();if(bytes)memcpy(p.data,data,bytes);driver_emit(OP_PUSH_CONST,&p,8+bytes);memcpy(driver_pushed[compute]+offset,data,bytes);
}
static void driver_bind(unsigned key) {
    prog_t *p=&driver_programs[driver_program_slot++%8];memset(p,0,sizeof*p);p->serial=35000+key;p->nstage=1;p->sd[0].data=key;p_bind_program b={p,0xff};DRIVER_EMIT(OP_BIND_PROGRAM,b);
}
typedef struct { unsigned phase,key;uint32_t expected[9][4]; } driver_result;
static void driver_read(uint8_t *mem,driver_result *r,unsigned phase,unsigned key,const uint32_t dim[3],int indirect) {
    driver_bind(key);uint64_t out=(uint64_t)(mem+65536+phase*512);p_bind_buf b={.stage=5,.index=0,.addr=out,.size=144};DRIVER_EMIT(OP_BIND_SSBO,b);
    b=(p_bind_buf){.stage=5,.index=15,.addr=(uint64_t)(mem+0x92000),.size=64};DRIVER_EMIT(OP_BIND_SSBO,b);
    b=(p_bind_buf){.stage=5,.index=0,.addr=(uint64_t)(mem+0x90000),.size=48};DRIVER_EMIT(OP_BIND_UBO,b);
    b=(p_bind_buf){.stage=5,.index=15,.addr=(uint64_t)(mem+0x91000),.size=80};DRIVER_EMIT(OP_BIND_UBO,b);
    r->phase=phase;r->key=key;memcpy(r->expected[0],driver_pushed[1],16);memcpy(r->expected[1],driver_pushed[1]+240,16);
    if(key==12)memcpy(r->expected[2]+1,dim,12);memcpy(r->expected[3],dim,12);memcpy(r->expected[4],dim,12);
    uint64_t addresses[4]={(uint64_t)(mem+0x90000),out,(uint64_t)(mem+0x92000),(uint64_t)(mem+0x91000)};uint32_t sizes[4]={48,144,64,80};
    for(unsigned i=0;i<4;i++){r->expected[5+i][0]=(uint32_t)addresses[i];r->expected[5+i][1]=(uint32_t)(addresses[i]>>32);r->expected[5+i][2]=sizes[i];}
    r->expected[8][3]=*(const uint32_t*)(mem+0x91000);
    p_dispatch d={.x=indirect?0:(int)dim[0],.y=indirect?0:(int)dim[1],.z=indirect?0:(int)dim[2],.ind=indirect?(uint64_t)(mem+0x80000):0};DRIVER_EMIT(OP_DISPATCH,d);
}
static void driver_write_args(uint8_t *mem,const uint32_t dim[4]) {
    driver_push(1,0,16,dim);driver_bind(14);p_bind_buf b={.stage=5,.index=0,.addr=(uint64_t)(mem+0x80000),.size=16};DRIVER_EMIT(OP_BIND_SSBO,b);p_dispatch d={.x=1,.y=1,.z=1};DRIVER_EMIT(OP_DISPATCH,d);
}
static void driver_verify(const uint8_t *mem,const driver_result *r) {
    static const char *names[]={"compute push head","compute push tail","architecture-specific low dimensions","canonical dispatch dimensions","actual Vulkan group counts","uniform0 table","storage0 table","storage15 table","uniform15 table and actual constant value"};
    const uint8_t *out=mem+65536+r->phase*512;
    for(unsigned i=0;i<9;i++){int ok=!memcmp(out+i*16,r->expected[i],16);driver_check(ok,names[i],r->phase);if(!ok){const uint32_t *got=(const uint32_t*)(out+i*16);printf("driver got=%u,%u,%u,%u expected=%u,%u,%u,%u\n",got[0],got[1],got[2],got[3],r->expected[i][0],r->expected[i][1],r->expected[i][2],r->expected[i][3]);}}
}
static void driver_graphics(uint8_t *mem) {
    tex_t target={.magic=MAGIC('T','E','X',0),.serial=36000,.d={.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA8,.width=32,.height=8,.depth=1,.levels=1,.samples=1}};
    prog_t program={.serial=36001,.nstage=2};program.sd[0].data=15;program.sd[1].data=16;
    mtl_sub_begin();driver_begin(mem);p_set_rt rt={.n=1};rt.color[0]=&target;DRIVER_EMIT(OP_SET_RT,rt);p_clear_color clear={.index=0,.mask=15,.rgba={0,0,1,1}};DRIVER_EMIT(OP_CLEAR_COLOR,clear);
    p_bind_program bind={&program,0xff};DRIVER_EMIT(OP_BIND_PROGRAM,bind);p_scissor sc={0,0,32,8};DRIVER_EMIT(OP_SCISSOR,sc);
    uint32_t block[64]={32,64,96,4};block[63]=255;driver_push(0,0,256,block);
    for(unsigned i=0;i<4;i++){
        if(i==1){uint32_t compute[4]={9,8,7,6};driver_push(1,0,16,compute);}
        if(i==2){uint32_t value=128;driver_push(0,4,4,&value);driver_push(0,252,4,&value);uint8_t red=80;driver_push(0,0,1,&red);}
        if(i==3)driver_push(0,252,0,block);
        p_viewports vp={.n=1};vp.v[0][0]=(float)(i*8);vp.v[0][2]=vp.v[0][3]=8;DRIVER_EMIT(OP_VIEWPORTS,vp);p_draw draw={.prim=4,.count=3,.instances=1};DRIVER_EMIT(OP_DRAW,draw);
    }
    driver_end();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();uint8_t pixels[1024];NVNcopyRegion region={0,0,0,32,8,1};mtl_read_texels(&target,0,0,&region,pixels,128,1024);
    const unsigned expected[4][4]={{32,64,96,255},{32,64,96,255},{80,128,96,128},{80,128,96,128}};
    for(unsigned i=0;i<4;i++){int ok=1;const uint8_t *p=pixels+(4*32+i*8+4)*4;for(unsigned c=0;c<4;c++)ok&=abs((int)p[c]-(int)expected[i][c])<=1;driver_check(ok,"graphics stages see immutable push revisions",i);}
    driver_result result={0};const uint32_t dim[3]={2,2,1};mtl_sub_begin();driver_begin(mem);driver_read(mem,&result,12,12,dim,0);driver_end();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();driver_verify(mem,&result);
}
static void driver_native(uint8_t *mem,unsigned mode) {
    tex_t target={.magic=MAGIC('T','E','X',0),.serial=37000+mode,.d={.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_RGBA8,.width=32,.height=32,.depth=1,.levels=1,.samples=1}};
    int task=mode==1 || mode==2;prog_t program={.serial=37100+mode,.nstage=2};program.sd[0].data=task?6:5;program.sd[1].data=task?18:19;if(task)program.sd[program.nstage++].data=17;
    mtl_sub_begin();driver_begin(mem);uint32_t block[64]={mode==2?31:32,64,mode==3?95:96,4};block[63]=255;driver_push(0,0,256,block);
    p_set_rt rt={.n=1};rt.color[0]=&target;DRIVER_EMIT(OP_SET_RT,rt);p_clear_color clear={.index=0,.mask=15,.rgba={0,0,1,1}};DRIVER_EMIT(OP_CLEAR_COLOR,clear);
    p_viewports vp={.n=1};vp.v[0][2]=vp.v[0][3]=32;DRIVER_EMIT(OP_VIEWPORTS,vp);p_scissor sc={0,0,32,32};DRIVER_EMIT(OP_SCISSOR,sc);p_bind_program bind={&program,0xff};DRIVER_EMIT(OP_BIND_PROGRAM,bind);
    for(unsigned st=6;st<=7;st++){uint32_t *cb=(uint32_t*)(mem+0x94000+st*512),*sb=cb+64;cb[0]=st;sb[0]=st+10;p_bind_buf b={.stage=(int)st,.index=0,.addr=(uint64_t)cb,.size=64};DRIVER_EMIT(OP_BIND_UBO,b);b.addr=(uint64_t)sb;DRIVER_EMIT(OP_BIND_SSBO,b);}
    p_draw_mesh draw={.first=0x3f800000,.count=1};DRIVER_EMIT(OP_DRAW_MESH,draw);driver_end();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();uint8_t pixels[4096];NVNcopyRegion region={0,0,0,32,32,1};mtl_read_texels(&target,0,0,&region,pixels,128,4096);const uint8_t *p=pixels+(16*32+16)*4;
    const uint8_t expected[4][4]={{0,255,0,255},{0,255,0,255},{0,0,255,255},{255,0,0,255}};driver_check(!memcmp(p,expected[mode],4),"native task/mesh graphics push gate",mode);
}
static void driver_formatless(uint8_t *mem) {
    tex_t image={.magic=MAGIC('T','E','X',0),.serial=38000,.d={.target=NVN_TEXTURE_TARGET_2D,.format=NVN_FORMAT_R32F,.flags=NVN_TEXTURE_FLAGS_IMAGE,.width=4,.height=4,.depth=1,.levels=1,.samples=1}};
    mtl_reg_image(303,&image,NULL);mtl_sub_begin();driver_begin(mem);driver_bind(20);p_bind_handles bind={.stage=5,.n=1};bind.h[0]=303;DRIVER_EMIT(OP_BIND_IMG,bind);p_bind_buf output={.stage=5,.index=0,.addr=(uint64_t)(mem+0x98000),.size=16};DRIVER_EMIT(OP_BIND_SSBO,output);p_dispatch d={.x=1,.y=1,.z=1};DRIVER_EMIT(OP_DISPATCH,d);driver_end();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();float value;memcpy(&value,mem+0x98000,4);driver_check(value==.625f,"formatless image write/read reaches storage buffer",0);
    float pixels[16];NVNcopyRegion region={0,0,0,4,4,1};mtl_read_texels(&image,0,0,&region,(uint8_t*)pixels,16,64);driver_check(pixels[0]==.625f,"formatless write reaches the real Vulkan image",0);
}
static void storage_bits_tests(void) {
    uint8_t *mem=mmap(NULL,1048576,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();mtl_pool_add(mem,1048576);
    samp_par sampler={.minf=0,.magf=0,.ws=7,.wt=7,.wr=7};mtl_reg_samp(1,&sampler);
    const int formats[]={NVN_FORMAT_R8UI,NVN_FORMAT_R8I,NVN_FORMAT_R16UI,NVN_FORMAT_R16I,NVN_FORMAT_R32UI,NVN_FORMAT_R32I};
    for(unsigned f=0;f<6;f++)for(unsigned phase=0;phase<2;phase++){
        uint32_t bits=f<2?8:f<4?16:32,value=bits==32?(phase?0xfedcba98u:0x12345a7bu):phase?(f&1?(uint32_t)-7:152u):123u;
        uint32_t expected=bits==32?value:value&((1u<<bits)-1);if((f&1) && bits<32 && (expected>>(bits-1)))expected|=~((1u<<bits)-1);
        tex_t image={.magic=MAGIC('T','E','X',0),.serial=39000+f*2+phase,.set_swz=1,.swz=0,.d={.target=NVN_TEXTURE_TARGET_2D,.format=formats[f],.flags=NVN_TEXTURE_FLAGS_IMAGE,.width=4,.height=4,.depth=1,.levels=1,.samples=1}};
        // A sampled view returns zero; image access must ignore that swizzle.
        mtl_reg_image(304,&image,NULL);uint32_t *result=(uint32_t*)(mem+0x98000);result[0]=value;result[1]=result[2]=0xdeadbeef;
        mtl_sub_begin();driver_begin(mem);p_bind_buf output={.stage=5,.index=0,.addr=(uint64_t)result,.size=16};DRIVER_EMIT(OP_BIND_SSBO,output);
        p_bind_handles images={.stage=5,.n=1};images.h[0]=304;DRIVER_EMIT(OP_BIND_IMG,images);images.h[0]|=1u<<20;DRIVER_EMIT(OP_BIND_TEX,images);
        p_dispatch dispatch={.x=1,.y=1,.z=1};driver_bind(29);DRIVER_EMIT(OP_DISPATCH,dispatch);driver_bind(30);DRIVER_EMIT(OP_DISPATCH,dispatch);driver_bind(29);DRIVER_EMIT(OP_DISPATCH,dispatch);
        driver_end();if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();
        driver_check(result[1]==expected,"integer image read/write preserves raw words and sign extension",f*2+phase);
        if(result[1]!=expected)printf("storage bits got=%08x expected=%08x input=%08x format=%x\n",result[1],expected,value,formats[f]);
        driver_check(result[2]==0,"sampled and storage views of one handle have separate swizzle caches",f*2+phase);
        uint8_t pixels[64]={0};NVNcopyRegion region={0,0,0,4,4,1};unsigned bytes=bits/8;mtl_read_texels(&image,0,0,&region,pixels,4*bytes,16*bytes);uint32_t got=0;memcpy(&got,pixels,bytes);
        driver_check(got==(bits==32?value:value&((1u<<bits)-1)),"integer write reaches the actual narrow Vulkan image",f*2+phase);
    }
    mtl_pool_del(mem);munmap(mem,1048576);
}
static void shared_spill_tests(void) {
    uint8_t *mem=mmap(NULL,1048576,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();mtl_pool_add(mem,1048576);
    const uint32_t dimensions[][3]={{1,1,1},{2,2,2},{3,1,2},{0,2,1}};
    for(unsigned phase=0;phase<6;phase++){
        const uint32_t *dim=dimensions[phase<4?phase:phase-3];uint32_t groups=dim[0]*dim[1]*dim[2],*output=(uint32_t*)(mem+65536);
        memset(output,0xa5,8*12288*4);uint32_t *args=(uint32_t*)(mem+0x80000);args[0]=args[1]=args[2]=0;
        mtl_sub_begin();driver_begin(mem);
        if(phase>=4){uint32_t values[4]={dim[0],dim[1],dim[2],0};driver_write_args(mem,values);}
        driver_bind(33);p_bind_buf buffer={.stage=5,.index=0,.addr=(uint64_t)output,.size=8*12288*4};DRIVER_EMIT(OP_BIND_SSBO,buffer);
        p_dispatch dispatch={.x=(int)dim[0],.y=(int)dim[1],.z=(int)dim[2],.ind=phase>=4?(uint64_t)args:0};DRIVER_EMIT(OP_DISPATCH,dispatch);driver_end();
        if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();int ok=1;
        for(uint32_t g=0;g<groups;g++)for(uint32_t i=0;i<12288;i++){uint32_t at=(i+17)%12288,expected=(g*817u)^at;if(at==12287)expected+=64;ok&=output[g*12288+i]==expected;}
        if(!groups)for(unsigned i=0;i<8*12288;i++)ok&=output[i]==0xa5a5a5a5;
        driver_check(ok,"48 KiB shared storage preserves all words, barriers and atomics across workgroups",phase);
    }
    mtl_pool_del(mem);munmap(mem,1048576);
}
static void driver_tests(void) {
    VkPhysicalDeviceFeatures2 features={VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2};vkGetPhysicalDeviceFeatures2(V.pd,&features);printf("driver formatless features read=%u write=%u\n",features.features.shaderStorageImageReadWithoutFormat,features.features.shaderStorageImageWriteWithoutFormat);
    uint8_t *mem=mmap(NULL,1048576,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();memset(mem+65536,0xa5,16*512);uint32_t *args=(uint32_t*)(mem+0x80000);args[0]=args[1]=args[2]=1;*(uint32_t*)(mem+0x91000)=0x44556677;mtl_pool_add(mem,1048576);
    driver_result r[10]={0};unsigned n=0;uint32_t dim[3]={2,3,4};mtl_sub_begin();driver_begin(mem);driver_read(mem,&r[n++],0,12,dim,0);
    dim[0]=1;dim[1]=2;dim[2]=3;driver_read(mem,&r[n++],1,13,dim,0);
    uint32_t block[64];for(unsigned i=0;i<64;i++)block[i]=0x11001100+i;driver_push(1,0,256,block);dim[0]=3;dim[1]=1;dim[2]=2;driver_read(mem,&r[n++],2,12,dim,0);
    uint32_t tail=0xabcdef12;driver_push(1,252,4,&tail);uint8_t patch[5]={21,22,23,24,25};driver_push(1,3,5,patch);dim[0]=7;dim[1]=2;dim[2]=1;driver_read(mem,&r[n++],3,12,dim,0);
    uint32_t one[4]={2,3,4,0},two[4]={5,1,2,0};driver_write_args(mem,one);driver_read(mem,&r[n++],4,12,one,1);driver_write_args(mem,two);driver_read(mem,&r[n++],5,12,two,1);
    struct {uint64_t addr,size;uint32_t data[4];} update={.addr=(uint64_t)args,.size=12,.data={6,2,1}};driver_emit(OP_UPDATE_UB,&update,16+12);driver_read(mem,&r[n++],6,12,update.data,1);driver_read(mem,&r[n++],7,13,update.data,1);
    p_bind_buf output={.stage=5,.index=0,.addr=(uint64_t)(mem+65536+8*512),.size=144};DRIVER_EMIT(OP_BIND_SSBO,output);p_dispatch zero={.x=0,.y=1,.z=1};DRIVER_EMIT(OP_DISPATCH,zero);
    dim[0]=dim[1]=2;dim[2]=1;driver_read(mem,&r[n++],9,12,dim,0);driver_end();driver_check(args[0]==1 && args[1]==1 && args[2]==1,"indirect source stays stale on CPU before submission",0);
    if(!mtl_wait(mtl_sub_commit(),10000000000ull))abort();for(unsigned i=0;i<n;i++)driver_verify(mem,&r[i]);int untouched=1;for(unsigned i=0;i<144;i++)untouched&=mem[65536+8*512+i]==0xa5;driver_check(untouched,"zero group count performs no work",8);
    driver_graphics(mem);for(unsigned mode=0;mode<4;mode++)driver_native(mem,mode);driver_formatless(mem);mtl_pool_del(mem);munmap(mem,1048576);
}
static void driver_reject(unsigned mode) {
    uint8_t *mem=mmap(NULL,1048576,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);if(mem==MAP_FAILED)abort();mtl_pool_add(mem,1048576);mtl_sub_begin();driver_begin(mem);driver_bind(12);
    if(mode==0){struct{uint16_t compute,offset;uint32_t size;uint8_t data[8];} p={1,252,8,{0}};driver_emit(OP_PUSH_CONST,&p,sizeof p);}
    else if(mode==1){uint32_t dummy=0;driver_emit(OP_PUSH_CONST,&dummy,0);}
    else {p_dispatch d={.x=1,.y=1,.z=1};if(mode==2)d.x=(int)V.props.limits.maxComputeWorkGroupCount[0]+1;else d.ind=(uint64_t)(mode==3?mem+1048576:mem+0x80002);DRIVER_EMIT(OP_DISPATCH,d);}
    driver_end();die("[RED] expected invalid driver record was accepted");
}
#undef DRIVER_EMIT
