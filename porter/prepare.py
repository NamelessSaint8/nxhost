# Prepare .NET tools (`porter tools --prepare`, the tools page's button, D-24): the NuGet restore and pin check (pins.NUGET) for the shader translator and nx_extract,
# the translator built once into the folder every port reuses (through the pipeline's own Port.translator, so the key is the port's), and nx_extract built once in a
# temporary folder: its binary is per game (RESEARCH Pitfall 8), so this proves the SDK builds it and warms the NuGet cache and the engine's obj/.
# A failure is a note on the tools page, never a blocker: a port still restores and builds both itself.
import os, tempfile, types
from pathlib import Path

from porter import childenv, paths, toolchain

STAGES = ('shader translator', 'nx_extract')


def run():
    from porter import nuget, pipeline   # they need lz4 (through porter.upstream)
    from porter.upstream import BuildError, PROG, nsp
    dotnet = toolchain.find_dotnet()
    if not dotnet or not any(int(s.split('.')[0]) >= toolchain.DOTNET_MAJOR for s in toolchain.dotnet_sdks(dotnet)):
        raise BuildError(f'.NET SDK {toolchain.DOTNET_MAJOR} not found: Download missing tools first, or set its path with Use my own…')
    env = childenv.dotnet(dotnet, os.cpu_count() or 8)   # D-18: the env a port's dotnet children get
    logs = paths.user_dir() / 'logs/prepare'; logs.mkdir(parents=True, exist_ok=True)
    PROG.plan(len(STAGES))
    PROG.stage(f'Prepare .NET tools: {STAGES[0]}', step='NuGet restore and build')
    _, key = pipeline.Port.translator(types.SimpleNamespace(tools={'dotnet': dotnet}, env=env, logs=logs))   # it reads only tools, env and logs
    PROG.end(key[:12])
    PROG.stage(f'Prepare .NET tools: {STAGES[1]}', step='NuGet restore and build')
    with nuget.restored(paths.NXNATIVE / 'dm/tools/nx_extract', dotnet, env, logs / 'nuget_restore.log'), tempfile.TemporaryDirectory(prefix='nx_extract_prepare_') as tmp:
        nsp.build_nx_extract(paths.NXNATIVE, Path(tmp), logs, env)
    PROG.end('builds'); PROG.close()
