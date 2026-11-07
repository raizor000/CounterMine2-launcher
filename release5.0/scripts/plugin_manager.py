import hashlib
import importlib
import importlib.util
import stat
import sys
import threading
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory

import requests
from packaging.version import InvalidVersion, Version
from PyQt6.QtCore import QObject

from .constants import INTERNAL_UPDATES_DIR, PLUGINS_DIR
from .storage import remove_item, safe_name


CORE_MODULES = {
    "ModrinthPlugin": "modrinth_plugin",
    "RankedPlugin": "ranked_plugin",
    "CurseForgePlugin": "curseforge_plugin",
    "CounterStrike2Theme": "counterstrike2theme",
}


def remote_plugin_id(plugin_id):
    return str(plugin_id).removeprefix("main.")


class BasePlugin(QObject):
    """
    by raizor. 26.05.2026
    Базовый класс, который должен наследоваться каждым плагином.
    :var name: имя плагина. Max length = 32
    :type name: str
    :var description: описание плагина. Max length = 90
    :type description: str
    :var version: версия плагина
    :type version: str
    :var author: никнейм автора
    :type author: str

    """
    name = "Безымянный плагин"
    description = "Описание отсутствует"
    version = "0.0.0"
    author = "Неизвестен"
    icon = None
    is_essential = False  # DO NOT OVERWRITE THIS

    def __init__(self, app):
        super().__init__()
        self.app = app

    def on_load(self):
        pass

    def on_ui_ready(self):
        pass

    def on_language_change(self, lang):
        pass

    def get_plugin_path(self, cls_name):
        wanted = str(cls_name).casefold()
        return next(
            (path for path in PLUGINS_DIR.iterdir() if path.is_dir() and path.name.casefold() == wanted),
            None,
        )


class PluginManager:
    def __init__(self, app):
        self.app = app
        self.plugins = []
        self.discovered_plugins = []
        self._active_ids = set()
        self._initialized = set()
        self._file_lock = threading.Lock()

    def _metadata(self, plugin_id, cls, path=None):
        icon = cls.icon
        if icon and path and not Path(icon).is_absolute() and not icon.startswith("assets"):
            icon = str(path.parent / icon)
        return {
            "id": plugin_id, "name": cls.name, "description": cls.description,
            "version": cls.version, "author": cls.author, "icon": icon, "class": cls,
            "internal": path is None,
            **({"path": path.parent if path.name == "main.py" else path} if path else {}),
        }

    def _register(self, meta, activate):
        plugin_id = meta["id"]
        if any(item["id"] == plugin_id for item in self.discovered_plugins):
            raise ValueError(f"Duplicate plugin ID: {plugin_id}")
        self.discovered_plugins.append(meta)
        if activate and plugin_id not in self._active_ids and self.app.plugin_states.get(plugin_id, True):
            instance = meta["class"](self.app)
            instance.on_load()
            self.plugins.append(instance)
            self._active_ids.add(plugin_id)

    def load_internal_plugins(self):
        for class_name, file_name in CORE_MODULES.items():
            try:
                cls = None
                update = INTERNAL_UPDATES_DIR / f"{file_name}.py"
                if update.is_file():
                    try:
                        cls = getattr(self._load_module(update, f"scripts.internal._updated_{file_name}"), class_name)
                        if not isinstance(cls, type) or not issubclass(cls, BasePlugin):
                            raise TypeError(f"{class_name} is not a plugin")
                    except Exception as exc:
                        cls = None
                        self.app.write_warn(f"[Plugins] Could not load update {class_name}: {exc}")
                if cls is None:
                    module = importlib.import_module(f"scripts.internal.{file_name}")
                    cls = getattr(module, class_name)
                self._register(self._metadata(class_name, cls), activate=True)
            except Exception as exc:
                self.app.write_error(f"[Plugins] Could not load {class_name}: {exc}")

    def load_plugins(self, *, activate=True):
        self.discovered_plugins = [plugin for plugin in self.discovered_plugins if plugin["internal"]]
        PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
        if str(PLUGINS_DIR) not in sys.path:
            sys.path.append(str(PLUGINS_DIR))

        for entry in sorted(PLUGINS_DIR.iterdir()):
            path = entry / "main.py" if entry.is_dir() else entry
            if entry.name.startswith(".") or path.suffix != ".py" or not path.is_file() or path == PLUGINS_DIR / "main.py":
                continue
            try:
                identity = hashlib.sha256(str(path).encode()).hexdigest()[:16]
                module = self._load_module(path, f"_countermine_plugin_{identity}")
                for cls in vars(module).values():
                    if (isinstance(cls, type) and cls is not BasePlugin and issubclass(cls, BasePlugin)
                            and cls.__module__ == module.__name__):
                        self._register(self._metadata(f"{path.stem}.{cls.__name__}", cls, path), activate)
            except Exception as exc:
                self.app.write_error(f"[Plugins] Could not load {path.name}: {exc}")

    @staticmethod
    def _load_module(path, name):
        locations = [str(path.parent)] if path.name == "main.py" else None
        spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=locations)
        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(name)
        sys.modules[name] = module
        try:
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
        except Exception:
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous
            raise
        return module

    def initialize_ui(self):
        for plugin in self.plugins[:]:
            if plugin in self._initialized:
                continue
            self._initialized.add(plugin)
            try:
                plugin.on_ui_ready()
            except Exception as exc:
                self.app.write_error(f"[Plugins] Could not initialize {plugin.name}: {exc}")

    def stop(self):
        for plugin in reversed(self.plugins):
            try:
                stop = getattr(plugin, "on_unload", None)
                if stop:
                    stop()
            except Exception as exc:
                self.app.write_warn(f"[Plugins] Could not stop {plugin.name}: {exc}")

    @staticmethod
    def _unpack(archive, destination, plugin_id, replacement=None):
        with zipfile.ZipFile(archive) as bundle:
            seen = set()
            for member in bundle.infolist():
                name = member.filename.rstrip("/")
                parts = name.split("/")
                for part in parts:
                    safe_name(part)
                folded = name.casefold()
                if folded in seen or stat.S_ISLNK(member.external_attr >> 16):
                    raise ValueError(f"Unsafe archive entry: {name}")
                seen.add(folded)
            bundle.extractall(destination)

        if (destination / "main.py").is_file():
            entry = destination / "main.py"
            if replacement and replacement.is_dir():
                target_name = replacement.name
            else:
                target_name = plugin_id
            wrapped = destination.parent / target_name
            destination.rename(wrapped)
            compile((wrapped / entry.name).read_bytes(), str(entry), "exec")
            return wrapped
        entries = list(destination.iterdir())
        if len(entries) != 1:
            raise ValueError("Expected a single plugin in the archive")
        package = entries[0]
        entry = package / "main.py" if package.is_dir() else package
        if not entry.is_file() or entry.suffix != ".py":
            raise ValueError("No plugin entry point in the archive")
        compile(entry.read_bytes(), str(entry), "exec")
        return package

    def install_from_url(self, plugin_data, reload_plugins=True, *, replacement=None):
        try:
            plugin_id = safe_name(plugin_data.get("id"))
            url = plugin_data.get("download_url")
            if not url:
                raise ValueError("Missing download URL")
            with self._file_lock:
                PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
                with TemporaryDirectory(prefix=".plugin-", dir=PLUGINS_DIR) as directory:
                    staging = Path(directory)
                    archive = staging / "download.zip"
                    with requests.get(url, stream=True, timeout=(5, 30)) as response:
                        response.raise_for_status()
                        with archive.open("wb") as stream:
                            for chunk in response.iter_content(64 * 1024):
                                stream.write(chunk)
                    unpacked = staging / "unpacked"
                    unpacked.mkdir()
                    package = self._unpack(archive, unpacked, plugin_id, replacement)
                    target = replacement or PLUGINS_DIR / package.name
                    if target.parent != PLUGINS_DIR or target.is_symlink():
                        raise ValueError("Invalid plugin destination")
                    if replacement and package.is_dir() != replacement.is_dir():
                        raise ValueError("The update has a different package type")
                    if target.exists():
                        if replacement is None:
                            raise FileExistsError(target)
                        backup = PLUGINS_DIR / f".backup-{staging.name}-{target.name}"
                        target.rename(backup)
                        try:
                            package.rename(target)
                        except OSError:
                            try:
                                backup.rename(target)
                            except OSError:
                                self.app.write_error(f"[Plugins] Previous plugin saved at {backup}")
                            raise
                        try:
                            remove_item(PLUGINS_DIR, backup.name)
                        except OSError as exc:
                            self.app.write_warn(f"[Plugins] Could not clean up {backup}: {exc}")
                    else:
                        package.rename(target)
            if reload_plugins:
                self.load_plugins()
                self.initialize_ui()
            return True
        except Exception as exc:
            self.app.write_error(f"[Plugins] Installation failed: {exc}")
            return False

    def delete_plugin(self, plugin_id):
        meta = next((p for p in self.discovered_plugins if p["id"] == plugin_id), None)
        if not meta or meta["internal"]:
            return False
        try:
            with self._file_lock:
                remove_item(PLUGINS_DIR, meta["path"].name)
            self.discovered_plugins = [p for p in self.discovered_plugins if p.get("path") != meta["path"]]
            return True
        except (OSError, ValueError) as exc:
            self.app.write_error(f"[Plugins] Could not delete {plugin_id}: {exc}")
            return False

    def check_for_updates(self):
        remote = {p["id"]: p for p in self.app.remote_plugins}
        for local in self.discovered_plugins:
            local.pop("update_available", None)
            local.pop("latest_version", None)
            match = remote.get(remote_plugin_id(local["id"]))
            if not match or local["internal"]:
                continue
            try:
                latest = match.get("version")
                if Version(latest) > Version(local["version"]):
                    local.update(update_available=True, latest_version=latest)
            except (InvalidVersion, TypeError):
                self.app.write_warn(f"[Plugins] Invalid version for {local['id']}")

    def update_plugin(self, plugin_id):
        local = next((p for p in self.discovered_plugins if p["id"] == plugin_id), None)
        remote = next((p for p in self.app.remote_plugins if p["id"] == remote_plugin_id(plugin_id)), None)
        if not local or local["internal"] or not remote:
            return False
        return self.install_from_url(remote, reload_plugins=False, replacement=local["path"])
