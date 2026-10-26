"""Small helpers for replacing text files without exposing partial writes."""

import os
import secrets
import stat
import time


def _open_temporary(directory):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    for _ in range(10):
        temporary = os.path.join(directory, f".aiset-{secrets.token_hex(16)}.tmp")
        try:
            return os.open(temporary, flags, 0o666), temporary
        except FileExistsError:
            continue
    raise FileExistsError(f"could not create a unique temporary file in {directory!r}")


def _replace_with_retry(temporary, target):
    for attempt in range(4):
        try:
            os.replace(temporary, target)
            return
        except PermissionError:
            if os.name != "nt" or attempt == 3:
                raise
            time.sleep(0.05)


def write_text_atomic(path, text, *, encoding="utf-8", errors="strict", newline=None):
    """Write text beside its destination, then atomically replace the destination.

    The temporary file is removed if writing or replacement fails. Existing POSIX
    permission bits are retained; new files use mode 0666 filtered by the active umask.
    """
    target = os.path.realpath(os.fspath(path))
    directory = os.path.dirname(target)
    try:
        existing_mode = stat.S_IMODE(os.stat(target).st_mode)
    except FileNotFoundError:
        existing_mode = None

    fd, temporary = _open_temporary(directory)
    try:
        stream = os.fdopen(fd, "w", encoding=encoding, errors=errors, newline=newline)
        fd = None
        with stream as f:
            f.write(text)
        if existing_mode is not None and os.name != "nt":
            os.chmod(temporary, existing_mode)
        _replace_with_retry(temporary, target)
        temporary = None
    finally:
        if fd is not None:
            os.close(fd)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
