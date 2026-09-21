"""Process-level helpers for the crash tests in test_durabilidade.py.

Ignored by `make test`'s discovery (does not match `test_*.py`).
"""

import os
import selectors
import subprocess
import sys


def raiz_repositorio() -> str:
    """Absolute path of the repository root, so a child `python -c` can `import kvstore`."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def iniciar_filho(source: str, args: "list[str]") -> "tuple[subprocess.Popen, int]":
    """Spawn `python -c source *args <write_fd>` with a pipe write-end passed as the
    last positional argument (its integer fd number, inherited via `pass_fds`).

    Returns `(proc, read_fd)`; the caller must eventually close `read_fd` and reap
    `proc` (via `matar_e_esperar` or a normal `wait`).
    """
    read_fd, write_fd = os.pipe()
    proc = subprocess.Popen(
        [sys.executable, "-c", source, *args, str(write_fd)],
        pass_fds=(write_fd,),
    )
    os.close(write_fd)
    return proc, read_fd


def esperar_ack(read_fd: int, timeout: float = 10.0) -> bool:
    """Block until one byte arrives on `read_fd`, or `timeout` elapses."""
    sel = selectors.DefaultSelector()
    sel.register(read_fd, selectors.EVENT_READ)
    try:
        events = sel.select(timeout=timeout)
        if not events:
            return False
        return os.read(read_fd, 1) != b""
    finally:
        sel.close()


def matar_e_esperar(proc: subprocess.Popen, timeout: float = 5.0) -> None:
    os.kill(proc.pid, 9)
    proc.wait(timeout=timeout)


def matar_apos_ack(source: str, args: "list[str]", timeout: float = 10.0) -> None:
    """Spawn a child, wait for its one-byte ack, then SIGKILL it.

    Raises `TimeoutError` if the child never acks — a test built on this proves
    nothing if the kill can land before the operation it is checking even ran.
    """
    proc, read_fd = iniciar_filho(source, args)
    try:
        if not esperar_ack(read_fd, timeout):
            proc.kill()
            proc.wait(timeout=5.0)
            raise TimeoutError("filho nunca confirmou (ack) antes do timeout")
        matar_e_esperar(proc)
    finally:
        os.close(read_fd)
