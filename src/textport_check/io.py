"""Bounded regular-file reads; symlinks/reparse points are outside the contract."""
from __future__ import annotations
import os
from pathlib import Path, PureWindowsPath
import stat


class InputError(Exception):
    pass


def safe_read(root: Path, relative: str, limit: int) -> bytes:
    path = Path(relative)
    if path.is_absolute() or PureWindowsPath(relative).drive or PureWindowsPath(relative).root or ":" in relative or not path.parts or ".." in path.parts or ".." in PureWindowsPath(relative).parts or "\x00" in relative:
        raise InputError("Only relative file paths without '..' are allowed.")
    root = Path(os.path.abspath(root))
    # Reject links in root and its ancestors too. POSIX traversal below uses nofollow
    # at every component; Windows checks are point-in-time, not a hostile-race sandbox.
    for ancestor in reversed((root, *root.parents)):
        info = ancestor.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InputError("Symlinks and reparse points are not supported.")
    if os.name == "posix" and os.open in os.supports_dir_fd:
        fd = os.open(root.anchor, os.O_RDONLY | os.O_DIRECTORY)
        try:
            components = list(root.parts[1:]) + list(path.parts)
            for index, part in enumerate(components):
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                if index < len(components) - 1:
                    flags |= os.O_DIRECTORY
                next_fd = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            return _read_fd(fd, limit)
        finally:
            os.close(fd)
    target = root
    for part in path.parts:
        target = target / part
        info = target.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InputError("Symlinks and reparse points are not supported.")
    fd = os.open(target, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        return _read_fd(fd, limit)
    finally:
        os.close(fd)


def _read_fd(fd: int, limit: int) -> bytes:
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        raise InputError("Only regular files are supported.")
    if info.st_size > limit:
        raise InputError("File exceeds the configured byte limit.")
    chunks = []
    remaining = limit + 1
    while remaining:
        chunk = os.read(fd, min(remaining, 65536))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    data = b"".join(chunks)
    if len(data) > limit:
        raise InputError("File exceeds the configured byte limit.")
    return data
