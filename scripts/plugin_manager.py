import importlib.util
import os
import sys
import requests
import zipfile
import shutil
from pathlib import Path
from PyQt6.QtCore import QObject
import packaging.version
from .constants import PLUGINS_DIR, INTERNAL_UPDATES_DIR, LAUNCHER_DIR


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
        """

        :param cls_name: Название папки вашего плагина
        :return:

        DO NOT OVERRIDE THIS METHOD
        """
        CURRENT_PLUGIN_DIR = None
        APPDATA = os.getenv("APPDATA") or os.path.expanduser("~")
        LAUNCHER_DIR = Path(APPDATA) / ".countermine-launcher"
        PLUGINS_DIR = LAUNCHER_DIR / "plugins"
        for item in os.listdir(PLUGINS_DIR):
            plugin_path = PLUGINS_DIR / item
            if str(cls_name) in str(plugin_path).lower():
                CURRENT_PLUGIN_DIR = plugin_path

        return CURRENT_PLUGIN_DIR


class PluginManager:
    def __init__(self, app):
        self.app = app
        self.plugins = []
        self.discovered_plugins = []

    def load_internal_plugins(self):
        try:
            core_modules = {
                "ModrinthPlugin": "modrinth_plugin",
                "RankedPlugin": "ranked_plugin",
                "CurseForgePlugin": "curseforge_plugin",
                "UI_Modifier": "counterstrike2theme",
            }

            internal_list = []

            for class_name, file_name in core_modules.items():
                update_file = INTERNAL_UPDATES_DIR / f"{file_name}.py"
                plugin_cls = None
                if update_file.exists():
                    try:
                        spec = importlib.util.spec_from_file_location(f"core.{file_name}", str(update_file))
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        plugin_cls = getattr(module, class_name)
                        print(f"[Plugins] Loaded UPDATED core plugin: {class_name}")
                    except Exception as e:
                        print(f"[Plugins] Failed to load update for {class_name}, falling back: {e}")

                if not plugin_cls:
                    module = importlib.import_module(f".internal.{file_name}", package="scripts")
                    plugin_cls = getattr(module, class_name)

                internal_list.append(plugin_cls)

            for plugin_cls in internal_list:
                plugin_id = plugin_cls.__name__
                meta = {
                    "id": plugin_id,
                    "name": plugin_cls.name,
                    "description": plugin_cls.description,
                    "version": plugin_cls.version,
                    "author": plugin_cls.author,
                    "icon": plugin_cls.icon,
                    "class": plugin_cls
                }
                self.discovered_plugins.append(meta)

                if self.app.plugin_states.get(plugin_id, True):
                    self._instantiate_plugin(plugin_cls)
                    print(f"[Plugins] Internal loaded: {plugin_cls.name}")
        except Exception as e:
            print(f"[Plugins] Error loading internal plugins: {e}")

    def load_plugins(self):
        self.discovered_plugins = [
            p for p in self.discovered_plugins
            if p.get('class') and p['class'].__module__.startswith('scripts.internal')
        ]

        if not PLUGINS_DIR.exists():
            PLUGINS_DIR.mkdir(parents=True, exist_ok=True)

        root_dir = str(Path(__file__).parent.parent)
        if root_dir not in sys.path:
            sys.path.insert(0, root_dir)

        if str(PLUGINS_DIR) not in sys.path:
            sys.path.append(str(PLUGINS_DIR))

        try:
            for item in os.listdir(PLUGINS_DIR):
                plugin_path = PLUGINS_DIR / item
                if plugin_path.is_dir() and (plugin_path / "main.py").exists():
                    self._load_module(plugin_path / "main.py")
                elif item.endswith(".py") and item != "main.py":
                    self._load_module(plugin_path)
        except Exception as e:
            print(f"[Plugins] Error scanning directory: {e}")

    def _load_module(self, path):
        try:
            module_name = path.stem
            spec = importlib.util.spec_from_file_location(module_name, str(path))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, BasePlugin) and attr is not BasePlugin:
                    plugin_id = f"{module_name}.{attr.__name__}"
                    is_dir_plugin = path.name == 'main.py' and path.parent.parent == PLUGINS_DIR

                    icon_path = getattr(attr, 'icon', None)
                    if icon_path and not os.path.isabs(icon_path) and not icon_path.startswith("assets"):
                        icon_path = str(path.parent / icon_path)

                    meta = {
                        "id": plugin_id,
                        "name": attr.name,
                        "description": attr.description,
                        "version": attr.version,
                        "author": attr.author,
                        "icon": icon_path,
                        "class": attr,
                        "path": path.parent if is_dir_plugin else path
                    }
                    self.discovered_plugins.append(meta)

                    if self.app.plugin_states.get(plugin_id, True):
                        self._instantiate_plugin(attr)
                        print(f"[Plugins] Loaded: {module_name}")
        except Exception as e:
            print(f"[Plugins] Failed to load {path}: {e}")

    def install_from_url(self, plugin_data, reload_plugins=True):
        try:
            url = plugin_data.get('download_url')
            plugin_id = plugin_data.get('id')
            self.app.write_log(f"[Install] Starting installation for plugin: {plugin_id}")

            if not url:
                self.app.write_log(f"[Install] Error: No download_url found for {plugin_id}")
                return False

            PLUGINS_DIR.mkdir(exist_ok=True)
            temp_zip = PLUGINS_DIR / f"{plugin_id}_temp.zip"

            with requests.get(url, stream=True) as r:
                r.raise_for_status()
                with open(temp_zip, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)

            with zipfile.ZipFile(temp_zip, 'r') as zip_ref:
                zip_ref.extractall(PLUGINS_DIR)

            if temp_zip.exists():
                temp_zip.unlink()

            self.app.write_log(f"[Install] Plugin {plugin_id} installed successfully.")
            if reload_plugins:
                self.load_plugins()
            return True
        except Exception as e:
            self.app.write_log(f"[Install] Critical failure: {e}")
            return False

    def delete_plugin(self, plugin_id):
        try:
            plugin_meta = next((p for p in self.discovered_plugins if p['id'] == plugin_id), None)
            if plugin_meta and 'path' in plugin_meta:
                path_to_delete = plugin_meta['path']
                if path_to_delete.is_dir():
                    shutil.rmtree(path_to_delete)
                else:
                    path_to_delete.unlink()
                self.app.write_log(f"[Plugins] Deleted plugin: {plugin_id}")
                self.load_plugins()
                return True
            return False
        except Exception as e:
            self.app.write_log(f"[Plugins] Error deleting plugin {plugin_id}: {e}")
            return False

    def check_for_updates(self):
        if not self.app.remote_plugins:
            self.app.write_log("[Update] No remote plugins fetched, skipping check.")
            return

        remote_plugin_map = {p['id']: p for p in self.app.remote_plugins}

        for local_plugin in self.discovered_plugins:
            local_id = local_plugin.get('id')
            local_id = str(local_id).replace("main.", "")
            if local_id in remote_plugin_map:
                remote_plugin = remote_plugin_map[local_id]
                local_version_str = local_plugin.get('version', '0.0.0')
                remote_version_str = remote_plugin.get('version', '0.0.0')
                try:
                    if not local_version_str or not remote_version_str:
                        continue

                    local_version = packaging.version.parse(local_version_str)
                    remote_version = packaging.version.parse(remote_version_str)
                    if remote_version > local_version:
                        self.app.write_log(
                            f"[Update] New version available for {local_id}: {remote_version} (current: {local_version})")
                        local_plugin['update_available'] = True
                        local_plugin['latest_version'] = remote_version_str
                except packaging.version.InvalidVersion:
                    self.app.write_warn(
                        f"[Update] Could not compare versions for {local_id} ('{local_version_str}' vs '{remote_version_str}')")

    def update_plugin(self, plugin_id):
        self.app.write_log(f"[Update] Starting update for plugin: {plugin_id}")

        remote_plugin_data = next(
            (p for p in self.app.remote_plugins if p['id'] == str(plugin_id).replace("main.", "")), None)
        if not remote_plugin_data:
            self.app.write_error(f"[Update] Could not find remote data for {plugin_id}")
            return False

        local_plugin_meta = next((p for p in self.discovered_plugins if p['id'] == plugin_id), None)
        if not local_plugin_meta or 'path' not in local_plugin_meta:
            self.app.write_error(f"[Update] Could not find local installation for {plugin_id}. Aborting.")
            return False

        try:
            path_to_delete = local_plugin_meta['path']
            if path_to_delete.is_dir():
                shutil.rmtree(path_to_delete)
            else:
                path_to_delete.unlink()
            self.app.write_log(f"[Update] Removed old version of {plugin_id} from {path_to_delete}")
        except Exception as e:
            self.app.write_error(f"[Update] Failed to delete old version of {plugin_id}: {e}")
            return False

        if not self.install_from_url(remote_plugin_data, reload_plugins=False):
            self.app.write_error(
                f"[Update] Failed to install new version of {plugin_id}. The plugin has been uninstalled.")
            return False

        self.app.write_log(f"[Update] Plugin {plugin_id} updated successfully.")
        return True

    def _instantiate_plugin(self, plugin_cls):
        instance = plugin_cls(self.app)
        instance.on_load()
        self.plugins.append(instance)
