# One port or install of a game at a time (D-06, D-07): an OS lock on <build folder>/.porter.lock, which the OS releases when the holder dies (killed or crashed).
# The file is never deleted: deleting it races a porter that already opened it, which would then hold a lock on a file no one else opens.
# It holds the holder's command, PID and start time, for the message a second porter gives.
# The same lock with wait=True on <user dir>/tools/.porter.lock makes builds of the tools every game shares (porter/nuget.py restored()) take turns.
import errno, os, time
from pathlib import Path

NAME = '.porter.lock'
AT = 4096   # Windows byte-range locks are mandatory and block reads: the locked byte sits past the text, so a second porter can still read who holds it
UNLOCKABLE = {errno.ENOLCK, errno.EOPNOTSUPP, getattr(errno, 'ENOTSUP', errno.EOPNOTSUPP)}   # a drive without file locks (some network shares)


def take(work, cmd, wait=False):
    """Lock the build folder work (created when missing) for this process and return the open lock file. Keep a reference for the whole run: closing it
    or losing the last reference lets the lock go. Raises BuildError naming the holder when another porter has it; with wait, says once whom it waits for
    and tries again every second until it has it (non-blocking calls on both OSes: Windows' blocking mode gives up after 10 s)"""
    work = Path(work); work.mkdir(parents=True, exist_ok=True)
    f = open(work / NAME, 'a+b')   # created if missing, never truncated before the lock is held
    told = False
    while True:
        try:
            if os.name == 'nt':
                import msvcrt; f.seek(AT); msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl; fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except OSError as e:
            if e.errno in UNLOCKABLE:
                from porter.upstream import say
                say(f'[RED] {work} is on a drive that does not lock files: nothing stops a second port of this game at the same time'); return f
            f.seek(0); who = f.read(AT).decode('utf-8', errors='replace').strip() or 'another porter'
            if not wait:
                f.close()
                from porter.upstream import BuildError
                raise BuildError(f'already running: {who} is using {work}: wait for it to finish, or stop it first') from None
            if not told:
                from porter.upstream import say
                say(f'waiting for {who} to finish with {work}'); told = True
            time.sleep(1)
    f.seek(0); f.truncate(); f.write(f'porter {cmd}, PID {os.getpid()}, started {time.strftime("%Y-%m-%d %H:%M:%S")}\n'.encode('utf-8')); f.flush()
    return f
