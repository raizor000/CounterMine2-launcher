import json
import os
from pathlib import Path, PureWindowsPath
from tempfile import NamedTemporaryFile


def atomic_write(path, write):
    """Publish a complete file only after the writer succeeds."""
    path = Path(path)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            write(stream)
            stream.close()
            os.replace(temporary, path)
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)


def write_json(path, value):
    atomic_write(path, lambda stream: stream.write(
        json.dumps(value, ensure_ascii=False, indent=2).encode("utf-8")
    ))


def safe_name(name):
    if not isinstance(name, str) or not name or name in {".", ".."}:
        raise ValueError("Invalid file name")
    if (any(c in name for c in '/\\:<>|?*"') or any(ord(c) < 32 for c in name)
            or name.endswith((" ", ".")) or PureWindowsPath(name).is_reserved()):
        raise ValueError(f"Invalid file name: {name!r}")
    return name


def remove_item(directory, name):
    import shutil

    target = directory / safe_name(name)
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir() and target.resolve() == directory.resolve() / target.name:
        shutil.rmtree(target)
    elif target.exists():
        raise ValueError(f"Refusing to remove redirected directory: {target}")
