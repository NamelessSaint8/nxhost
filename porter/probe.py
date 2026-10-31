# stub: the compile probe (D-11), filled in by plan 03-04 task 1
import subprocess, sys
from pathlib import Path

ARM_HOSTS = ('linux-arm64', 'linux-aarch64')
SOURCE = 'int main(void) { return 0; }'
TIMEOUT = 60


def host_folder(ndk): return ''


def clang(ndk): return Path(ndk) / 'clang'


def probe(ndk): return {'ok': False, 'detail': '', 'version': '', 'fix': ''}


def note(ndk, version): return ''
