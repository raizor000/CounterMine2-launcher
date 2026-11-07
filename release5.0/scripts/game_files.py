import filecmp
import hashlib
import json
import re
import shutil
import zipfile

import requests

from .storage import atomic_write, safe_name, write_json


def sync_mods(root, new_version, old_version):
    """Copy versioned mods into Fabric's mods directory, preserving manual files."""
    source = root / safe_name(new_version)
    source.mkdir(exist_ok=True)
    if source.resolve() != root.resolve() / source.name:
        raise ValueError(f"Redirected mods directory: {source}")
    manifest = root / ".active-mods.json"
    previous = root / safe_name(old_version)
    if manifest.is_file():
        managed = {safe_name(name) for name in json.loads(manifest.read_text(encoding="utf-8"))}
    else:
        managed = {
            path.name for path in previous.glob("*.jar")
            if (root / path.name).is_file() and filecmp.cmp(path, root / path.name, shallow=False)
        }
    desired = {path.name: path for path in source.iterdir() if path.is_file() and path.suffix.lower() == ".jar"}

    for name, path in desired.items():
        target = root / name
        if target.is_symlink() or (target.exists() and not target.is_file()):
            raise ValueError(f"Unexpected active mod path: {target}")
        if target.exists() and name not in managed and not filecmp.cmp(path, target, shallow=False):
            raise ValueError(f"Manually installed mod conflicts with {name}")

    # Record both sets so a retry can clean up after an interrupted sync.
    write_json(manifest, sorted(managed | desired.keys()))
    for name, path in desired.items():
        target = root / name
        if not target.exists() or not filecmp.cmp(path, target, shallow=False):
            with path.open("rb") as source_stream:
                atomic_write(target, lambda stream: shutil.copyfileobj(source_stream, stream))
    for name in managed - desired.keys():
        (root / name).unlink(missing_ok=True)
    write_json(manifest, sorted(desired))


def _catalog_file(directory, key):
    index = directory / ".catalog-mods.json"
    names = json.loads(index.read_text(encoding="utf-8")) if index.is_file() else {}
    name = names.get(key)
    return index, names, directory / safe_name(name) if name else None


def catalog_mod_path(directory, key, slug):
    _, _, recorded = _catalog_file(directory, key)
    if recorded is not None:
        return recorded if recorded.is_file() else None

    # Legacy installations did not record the file name.
    normalized_slug = re.sub(r"[-_]+", "-", slug.lower())
    versioned_name = re.compile(re.escape(normalized_slug) + r"-v?\d+(?:[.\-+].*)?")
    matches = []
    for path in directory.glob("*.jar"):
        normalized_name = re.sub(r"[-_]+", "-", path.stem.lower())
        if normalized_name == normalized_slug or versioned_name.fullmatch(normalized_name):
            matches.append(path)
    return matches[0] if len(matches) == 1 else None


def install_catalog_mod(directory, key, filename, url, checksum=None):
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / safe_name(filename)
    if target.suffix.lower() != ".jar":
        raise ValueError("The selected file is not a mod JAR")
    index, names, previous = _catalog_file(directory, key)
    if target.exists() and previous != target:
        raise FileExistsError(target)

    def download(stream):
        digest = hashlib.new(checksum[0]) if checksum else None
        with requests.get(url, stream=True, timeout=(5, 30)) as response:
            response.raise_for_status()
            for chunk in response.iter_content(64 * 1024):
                stream.write(chunk)
                if digest is not None:
                    digest.update(chunk)
        if digest is not None and digest.hexdigest() != checksum[1].lower():
            raise ValueError(f"Checksum mismatch for {filename}")
        stream.seek(0)
        with zipfile.ZipFile(stream) as archive:
            if "fabric.mod.json" not in archive.namelist():
                raise ValueError(f"{filename} is not a Fabric mod")

    atomic_write(target, download)
    names[key] = target.name
    write_json(index, names)
    if previous and previous != target:
        previous.unlink(missing_ok=True)


def remove_catalog_mod(directory, key, slug):
    path = catalog_mod_path(directory, key, slug)
    if path is None:
        raise FileNotFoundError(f"No unique installed file for {slug}")
    path.unlink()
