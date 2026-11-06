# An lldb driver for a dm host run: read the guest module bases at run time, then break on guest code.
# The host maps the guest modules itself, so their bases differ on every launch (measured 2026-11-06 on Mario Kart World: sdk 0x113174000, 0x115174000,
# 0x115974000, main 0x10f800000, 0x111800000, 0x112000000), and a breakpoint at "module+offset" computed from one run is wrong in the next. lldb's
# target.disable-aslr does not help: the host chooses these mappings. So stop at the host's own guest_main, where the modules are loaded and g_mod is
# filled in, and arm the guest addresses from what it holds.
# Usage:
#   lldb -b ./dmhost \
#     -o "settings set target.run-args <patched dir>" \
#     -o "command script import nxnative/dm/tools/lldb_guest.py" \
#     -o "br s -n guest_main" -o run \
#     -o guest-bases \
#     -o "guest-bp main=0x8497c sdk=0x16ba50" \
#     -o "process continue"
#   guest-bases             print each module's name and base (the run must be stopped at guest_main or later)
#   guest-bp mod=off ...    a breakpoint at module+offset for each pair, printing x0..x3 and x8 then continuing (offsets 0x-prefixed)
# The breakpoints are armed through the command interpreter rather than SBBreakpoint.SetCallback, which this lldb does not have.
import lldb

NAME_OFF, BASE_OFF = 0, 16   # module_t: char name[16]; uint8_t *base (dm.h)


def _modules(target):
    gm = target.FindFirstGlobalVariable('g_mod')
    n = target.FindFirstGlobalVariable('g_nmod').GetValueAsUnsigned()
    mt = target.FindFirstType('module_t')
    if not gm.IsValid() or not n or not mt.IsValid():
        raise RuntimeError('g_mod / g_nmod / module_t not visible: stop the run at guest_main first')
    stride, p = mt.GetByteSize(), gm.GetValueAsUnsigned()
    proc = target.GetProcess()
    out = {}
    for i in range(n):
        e1, e2 = lldb.SBError(), lldb.SBError()
        raw = proc.ReadMemory(p + i * stride + NAME_OFF, 16, e1)
        rab = proc.ReadMemory(p + i * stride + BASE_OFF, 8, e2)
        if not (e1.Success() and e2.Success()):
            raise RuntimeError(f'cannot read module {i} of g_mod at {p:#x}')
        out[raw.split(b'\0')[0].decode('ascii', 'replace')] = int.from_bytes(rab, 'little')
    return out


def guest_bases(debugger, command, exe_ctx, result, _):
    result.AppendMessage(' '.join(f'{k}={v:#x}' for k, v in _modules(exe_ctx.GetTarget()).items()))


def guest_bp(debugger, command, exe_ctx, result, _):
    target = exe_ctx.GetTarget()
    mods = _modules(target)
    for pair in command.split():
        name, _, off = pair.partition('=')
        if name not in mods:
            result.AppendMessage(f'{name}: not a loaded module ({", ".join(mods)})')
            continue
        addr = mods[name] + int(off, 0)
        bp = target.BreakpointCreateByAddress(addr)
        debugger.HandleCommand('breakpoint command add -s command '
                               '-o "register read x0 x1 x2 x3 x8" -o "process continue" '
                               f'{bp.GetID()}')
        result.AppendMessage(f'{pair} -> {addr:#x} (breakpoint {bp.GetID()})')


def __lldb_init_module(debugger, internal_dict):
    debugger.HandleCommand('command script add -o -f lldb_guest.guest_bases guest-bases')
    debugger.HandleCommand('command script add -o -f lldb_guest.guest_bp guest-bp')
