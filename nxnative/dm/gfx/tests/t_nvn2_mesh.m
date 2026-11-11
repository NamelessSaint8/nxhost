// GPU half of test_dmsh_nvn2_mesh.py: real translated stage buffers and replay.
#define main geometry_fixture_main
#include "t_geometry.m"
#undef main
static NvShader *mesh_fixture(NSString *root, NSString *name, int kind) {
    NSError *error=nil;id<MTLLibrary> lib=[g_dev newLibraryWithURL:[NSURL fileURLWithPath:[root stringByAppendingPathComponent:[name stringByAppendingString:@".metallib"]]] error:&error];
    if(!lib){fprintf(stderr,"%s\n",error.description.UTF8String);abort();}
    NvShader *s=shader(lib,kind==6?@"dm_task":@"dm_mesh",kind,NULL,0);s->nvn2_kind=kind;s->nvn2_threads=32;
    NSDictionary *reflection=@{@"route":@"B",@"bindings":@[
        @{@"kind":@"cbuf",@"reg":@0,@"arg_id":@0,@"msl_name":@"cb",@"msl_type":@"constant uint*"},
        @{@"kind":@"sbuf",@"reg":@0,@"arg_id":@1,@"msl_name":@"sb",@"msl_type":@"device uint*",@"rw":@NO},
        @{@"kind":@"drvcb",@"bank":@0,@"arg_id":@2,@"msl_name":@"driver",@"msl_type":@"constant uint*"}]};
    char message[160];EXPECT("mesh resource reflection",0,nvn_refl_from_json(reflection,&s->rf,message,sizeof message));
    s->ae=[s->fn newArgumentEncoderWithBufferIndex:0];s->arg_len=s->ae.encodedLength;return s;
}
static void mesh_case(NSString *root,int mode) {
    NvProg *pr=[NvProg new];pr->sh[7]=mesh_fixture(root,mode==0?@"direct":@"mesh",7);
    if(mode)pr->sh[6]=mesh_fixture(root,mode==2?@"empty":@"task",6);
    NSString *pixelSource=[NSString stringWithFormat:@"#include <metal_stdlib>\nusing namespace metal;\nstruct I{float4 value[[user(locn0)]];};fragment float4 pixel(I i[[stage_in]]){return i.value.x==1.0f&&i.value.y==%u.0f?float4(0,1,0,1):float4(1,0,0,1);}",mode==0?1:0];
    pr->sh[1]=shader(library(pixelSource),@"pixel",1,NULL,0);
    static prog_t native[3];native[mode].serial=29000+mode;serial_put(native[mode].serial,pr);
    tex_t target={.magic=MAGIC('T','E','X',0),.serial=29100+mode};target.d.width=target.d.height=32;target.d.depth=target.d.samples=target.d.levels=1;target.d.target=NVN_TEXTURE_TARGET_2D;target.d.format=NVN_FORMAT_RGBA8;
    uint8_t *commands;posix_memalign((void**)&commands,getpagesize(),16384);memset(commands,0,16384);mtl_pool_add(commands,16384);size_t used=0;
    #define EMIT(OP,X) do{size_t n=(8+sizeof(X)+7)&~7ull;op_hdr h={OP,(uint32_t)n};memcpy(commands+used,&h,8);memcpy(commands+used+8,&(X),sizeof(X));used+=n;}while(0)
    p_set_rt rt={.n=1};rt.color[0]=&target;EMIT(OP_SET_RT,rt);
    p_viewports vp={.n=1};vp.v[0][2]=vp.v[0][3]=32;EMIT(OP_VIEWPORTS,vp);p_scissor sc={0,0,32,32};EMIT(OP_SCISSOR,sc);
    p_clear_color clear={.index=0,.mask=15,.rgba={0,0,1,1}};EMIT(OP_CLEAR_COLOR,clear);
    p_bind_program bind={&native[mode],0xc2};EMIT(OP_BIND_PROGRAM,bind);
    for(unsigned stage=6;stage<=7;stage++){
        uint32_t *cb=(uint32_t*)(commands+4096+stage*256),*sb=cb+32;cb[0]=stage;sb[0]=stage+10;
        p_bind_buf uniform={.stage=stage,.index=0,.addr=(uint64_t)cb,.size=64};EMIT(OP_BIND_UBO,uniform);
        p_bind_buf storage={.stage=stage,.index=0,.addr=(uint64_t)sb,.size=64};EMIT(OP_BIND_SSBO,storage);
    }
    // A nonzero native first group is carried independently of Metal's group ID.
    p_draw_mesh mesh={.first=0x3f800000,.count=1};EMIT(OP_DRAW_MESH,mesh);
    op_hdr end={OP_END,8};memcpy(commands+used,&end,8);
    #undef EMIT
    state_reset();memset(&R,0,sizeof R);mtl_sub_begin();uint64_t h=(uint64_t)commands;mtl_sub_index(&h,1);mtl_exec(commands);
    id<MTLBuffer> out=[g_dev newBufferWithLength:4096 options:MTLResourceStorageModeShared];res_add(out);
    [blit() copyFromTexture:tex_mtl(&target) sourceSlice:0 sourceLevel:0 sourceOrigin:MTLOriginMake(0,0,0) sourceSize:MTLSizeMake(32,32,1) toBuffer:out destinationOffset:0 destinationBytesPerRow:128 destinationBytesPerImage:4096];finish();
    uint8_t *pixel=(uint8_t*)out.contents+(16*32+16)*4;
    EXPECT("mesh payload/group marker red",0,pixel[0]);EXPECT("mesh center green",mode==2?0:255,pixel[1]);EXPECT("empty task preserves clear",mode==2?255:0,pixel[2]);
    res_remove(out);mtl_tex_release(&target);mtl_pool_del(commands);mtl_drain();free(commands);
}
static void empty_dispatches(void) {
    id<MTLLibrary> lib=library(@"#include <metal_stdlib>\nusing namespace metal;struct A{device uint*p[[id(0)]];};kernel void increment(constant A&a[[buffer(0)]]){a.p[0]++;}");
    NvShader *cs=shader(lib,@"increment",5,NULL,0);char message[160];
    NSDictionary *reflection=@{@"route":@"B",@"bindings":@[@{@"kind":@"sbuf",@"reg":@0,@"arg_id":@0,@"msl_name":@"p",@"msl_type":@"device uint*",@"rw":@YES}]};
    EXPECT("empty dispatch resource reflection",0,nvn_refl_from_json(reflection,&cs->rf,message,sizeof message));
    cs->rf.tg[0]=cs->rf.tg[1]=cs->rf.tg[2]=1;cs->ae=[cs->fn newArgumentEncoderWithBufferIndex:0];cs->arg_len=cs->ae.encodedLength;
    NvProg *pr=[NvProg new];pr->sh[5]=cs;static prog_t native={.serial=29200};serial_put(native.serial,pr);
    uint32_t *out;posix_memalign((void**)&out,getpagesize(),16384);memset(out,0,16384);mtl_pool_add(out,16384);
    state_reset();S.cprog=&native;S.ssbo[5][0]=(p_bind_buf){.stage=5,.index=0,.addr=(uint64_t)out,.size=64};mtl_sub_begin();
    for(int axis=0;axis<3;axis++){p_dispatch d={.x=1,.y=1,.z=1};if(axis==0)d.x=0;else if(axis==1)d.y=0;else d.z=0;dispatch(&d);}
    p_dispatch live={.x=1,.y=1,.z=1};dispatch(&live);finish();EXPECT("only nonempty dispatch executes",1,out[0]);
    mtl_pool_del(out);mtl_drain();free(out);
}
int main(int argc,char **argv){@autoreleasepool{if(argc!=2)return 2;mtl_init();for(int mode=0;mode<3;mode++)mesh_case(@(argv[1]),mode);empty_dispatches();printf("NVN2 mesh: %d checks, %d failed\n",checks,failed);return failed!=0;}}
