# The env every port and Prepare child gets; the process environment is never written (HARD-06).
# D-18: DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 and a UTF-8 LANG make libicu irrelevant (a minimal Linux has none, and .NET aborts without it).
# DOTNET_ROOT is dotnet's real root (hosttools.dotnet_root) and leads PATH, because upstream's build_nx_extract finds dotnet through this env's PATH.
import os

from porter import hosttools, paths


def dotnet(dotnet, jobs, base=None):
    e = dict(os.environ if base is None else base)
    root = str(hosttools.dotnet_root(dotnet))
    e.update(PATH=os.pathsep.join([root, e.get('PATH', '')]), DOTNET_ROOT=root, J=str(jobs), PYTHONIOENCODING='utf-8', PYTHONUTF8='1', DOTNET_CLI_TELEMETRY_OPTOUT='1',
             NUGET_PACKAGES=str(paths.user_dir() / 'nuget'), DOTNET_SYSTEM_GLOBALIZATION_INVARIANT='1')
    e.setdefault('LANG', 'C.UTF-8')
    return e
