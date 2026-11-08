# Looking up an Ampere field when our emitted MSL looks wrong

The translator decodes Ampere SASS and emits Metal MSL (`nxnative/dm/gfx/tools/dmsh_build.py`). When a program
builds, links and runs but draws the wrong thing, the fault is usually a **field read at the wrong offset or
width** — an operand, a component size, a source format — not an unsupported instruction. This is the procedure for
that case.

Scope: **not** the 26 programs that fail to build. Those are `ISBERD`/`ISBEWR` (`0x923`/`0x927`), task and mesh
programs, a pipeline gap rather than a decode gap, and their refusal is loud. This is for the silent case.

## Where the words come from

1. `nxnative/dm/tools/shader_view.py <chain> <key>` first: the reflection says what the program is (`pc_paired` is
   the game's own shader name), what it is bound and what the translator already noted about it. A note such as
   `Attribute offset 0x5C is not valid` or `not in the answer table, queries use defaults` is often the answer
   before any disassembly.
2. The instruction words themselves come from the program's code section as `dmsh_build.py` decodes it. To hold one
   in hand, add a temporary print in the decode loop for the key of interest and the instruction index you suspect
   (the note's own message, or a wrong-looking emitted line, usually names it), or use the profile's shader package
   (`shader_split.py` output) and the program's offset.

Keep four 32-bit words per instruction; Ampere instructions are 128 bits.

## Where the field layout is documented

Mesa's NAK is the readable public description of the encoding, per opcode:

```bash
curl -sL "https://gitlab.freedesktop.org/api/v4/projects/176/repository/files/src%2Fnouveau%2Fcompiler%2Fnak%2Fsm70_encode.rs/raw?ref=main"
curl -sL "https://gitlab.freedesktop.org/api/v4/projects/176/repository/files/src%2Fnouveau%2Fcompiler%2Fnak_nir_lower_tex.c/raw?ref=main"
```

`sm70_encode.rs` carries one `impl SM70Op for Op<Name>` per instruction, listing every field as
`insn.bits(offset, count)`. `nak_nir_lower_tex.c` covers how a texture's sources are split across Ra/Rb.

**Read those for the bit fields only.** NAK is MIT, Eglantine's own lowering is GPLv3 — its notes and switch names
are reusable, its code is not, and neither belongs in this tree.

## The procedure

1. **Identify the opcode**: the low 12 bits of word 0. Compare with the `case` labels in `dmsh_build.py`'s decode.
2. **Find the op in NAK** by that name, and list its fields with their offsets and widths.
3. **Compare field by field with our handler**: source index, width/flags, immediate packing. The usual faults are
   a width that excludes a mode bit, an operand taken from the wrong sub-word, and an immediate assumed signless.
4. **Fix narrowly, then prove no regression**: rebuild the chain, and check that the programs which already built
   still compile and hash identically. A field change touches many programs at once.
5. **Confirm on the picture**, not on the build: `DM_VDRAW_SKIP` the program in and out, or `DM_VDRAW_PASSSHOT`
   its target, and compare with `tools/pngstat.py`. A chain that builds 11,577 of 11,603 says nothing about whether
   the ones it built are right.

## The lesson worth keeping from Eglantine's own triage skill

*Start from the log, finish from a dump* — loop until the dump is clean, not until the log is quiet. One fix
exposes the next rejection, so a clean log is a snapshot of the first failure only. The same holds here in reverse:
a chain that compiles is a snapshot of the first success only.
