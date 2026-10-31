# The env every port and Prepare child gets (stub, RED).
import os

from porter import hosttools, paths


def dotnet(dotnet, jobs, base=None):
    return dict(os.environ if base is None else base)
