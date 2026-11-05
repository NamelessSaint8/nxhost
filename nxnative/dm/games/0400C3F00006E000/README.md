# Mario Kart World (Switch 2)

Split and shader-built from a loose dump of update 917504. **No host, no port**: this profile exists so the engine's shader tools read the game, and it
has no `android.tsv`, no `build` rows and no memory keys — nothing has been packed or run.

- Dump: `exefs/` (main 33.6 MB, sdk, subsdk0/1) + `romfs/` (22 GB), loose.
- Engine: Nintendo EPD's Nin_Ounce (sead / agl / gsys, Phive), SDK with NVN2; Ampere shaders.
- Shaders: 11,603 in [`shader_map.tsv`](shader_map.tsv), from `Shader/*.Nin_Ounce_NVN2.bfsha.zs` (BNSH), one `.sarc.zs` with agl `sharcb` packs,
  `Lib/agl/agl_resource.Nin_Ounce_NVN2.release.sarc` (BAHS packs, 3,924 of them), the effect set (`Effect/static.…esetb.byml.zs`, 1,017 compute
  programs) and the UI layouts.

## Shaders

`shader_split.py` over the whole RomFS: 11,603 shaders (7,301 pixel, 3,560 vertex, 729 compute, 13 domain), 5,180 variation pairs.

`shader_vk.py` (the Android chain, SPIR-V): **11,577 of 11,603 build**, 495 MB bundle. The 26 that do not are **task and mesh programs** (`ISBERD`/
`ISBEWR`), which this host cannot dispatch: NVN2 draws some geometry with a task program in the vertex slot and a mesh program in the tessellation
slot, writing each vertex into a stage buffer (Eglantine's `NX2_NOTES` rows 89 and 97 — the same reason high-detail LODs pop in and out there). The
translator refuses them by name.

On a device (`probes/vksh.c`, Lenovo Legion Y700, Adreno 840): 729 of 729 compute pipelines compile and **5,180 of 5,180** vertex/pixel pairs compile.
The pairs first came out 5,124: the 56 that did not were stage-link failures, which is what the Mac chain's `vs_pad` fixes — `dmsv_pad.py` now pads the
vertex modules the same way (40 shaders, 40 outputs). The device reports `VK_EXT_mesh_shader`, so the task/mesh gap is this host's, not the GPU's.
`docs/SWITCH2.md` has the table.

Reproduce (the profile is the game, so `DM_GAME` is its program id):

```
DM_GAME=0400C3F00006E000 J=8 python dm/gfx/tools/shader_split.py <dump>/romfs <dump>/exefs/main \
    /tmp/mkw/pkg . shader_facts.tsv shader_pairs.tsv pso_pairs.tsv      # shader_map.tsv, the facts, the pairs
DM_GAME=0400C3F00006E000 python dm/android/tools/shader_vk.py /tmp/mkw/pkg /tmp/mkw/shaders.dmsv --jobs 8
```

`docs/SWITCH2.md` says what a port would still need (the NVN2 command stream, the services, a task/mesh pipeline, memory); `devtools/nvn2_shader_census.py`
measures a dump without a profile.
