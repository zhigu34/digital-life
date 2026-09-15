"""Preserve an offline damaged SQLite database byte-for-byte before recovery."""
import os
from pathlib import Path
import shutil
import sys


def preserve(source: Path, target: Path):
    database = source / 'digital-life.db'
    if not database.is_file() or database.is_symlink():
        raise ValueError('Current database is missing or is a symbolic link')
    target.mkdir(mode=0o700, parents=False, exist_ok=False)
    for name in ('digital-life.db', 'digital-life.db-wal', 'digital-life.db-shm'):
        original = source / name
        if original.is_symlink():
            raise ValueError('Refusing to preserve a symbolic link')
        if original.exists():
            destination = target / name
            shutil.copyfile(original, destination)
            destination.chmod(0o600)
            with destination.open('rb') as handle:
                os.fsync(handle.fileno())
    descriptor = os.open(target, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('Usage: preserve-database.py DATA_DIRECTORY NEW_BACKUP_DIRECTORY')
    preserve(Path(sys.argv[1]), Path(sys.argv[2]))
