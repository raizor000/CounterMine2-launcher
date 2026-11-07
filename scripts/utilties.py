import datetime
import hashlib
import random
import re
import string
import subprocess
import uuid
import winreg
import wmi
import minecraft_launcher_lib
import psutil
import requests
import win32gui
import win32process

from .constants import *


def get_server_url() -> str:
    return f"{backend}"

def get_banned_ips() -> list:
    try:
        response = requests.get(f'{get_server_url()}/banned_ips')
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при получении списка IP: {e}")
        return []

def get_external_ip() -> str:
    try:
        response = requests.get(external_ip_url)
        response.raise_for_status()
        ip_data = response.json()
        return ip_data['ip']
    except requests.RequestException as e:
        return f"Ошибка при получении IP: {e}"

def is_mod_installed(mc_dir: str, slug: str) -> bool:

    mods_dir = os.path.join(mc_dir, "mods")
    if os.path.exists(mods_dir):
        for file in os.listdir(mods_dir):
            if file.endswith('.jar') and file.startswith(slug):
                return True
    return False

def download_with_progress(version: str, mc_path: str, progress_callback):
    def set_max(max):
        global total
        total = max

    def set_progress(current):
        percent = int((current / total) * 100)
        progress_callback(f"{min(percent, 100)}%")

    callback = {
        "setStatus": lambda *args: None,
        "setProgress": set_progress,
        "setMax": set_max,  # Не нужен, используем из progress
    }
    try:
        minecraft_launcher_lib.install.install_minecraft_version(version, mc_path, callback)
        minecraft_launcher_lib.fabric.install_fabric(version, mc_path, callback=callback)
    except Exception as e:
        print(e)

def get_new_logfile(base_dir: str, prefix: str = "launcher") -> str:
    files = [f for f in os.listdir(base_dir) if f.startswith(prefix) and f.endswith(".log")]
    nums = [int(re.match(rf"{prefix}_(\d+)\.log", f).group(1)) for f in files if re.match(rf"{prefix}_(\d+)\.log", f)]
    new_num = max(nums or [0]) + 1
    if new_num >= 20:
        for f in files:
            os.remove(os.path.join(base_dir, f))
        new_num = 1
    return os.path.join(base_dir, f"{prefix}_{new_num}.log")

def send_log_line(msg: str, server_url: str):
    payload = {"log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg} \n"}
    try:
        requests.post(server_url, json=payload, timeout=3)
    except Exception as e:
        print("Ошибка отправки:", e)

def random_username(length: int = 8) -> str:
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def is_fabric_installed(mc_path: str, vanilla_version: str) -> bool:
    try:
        installed = minecraft_launcher_lib.utils.get_installed_versions(mc_path) or []
        for v in installed:
            vid = v.get("id", "")
            if vid.startswith("fabric-loader") and vanilla_version in vid:
                version_dir = os.path.join(mc_path, "versions", vid)
                json_file = os.path.join(version_dir, f"{vid}.json")
                jar_file = os.path.join(version_dir, f"{vid}.jar")
                if os.path.isdir(version_dir) and os.path.isfile(json_file) and os.path.isfile(jar_file):
                    return True
        return False
    except Exception as e:
        print(f"[is_fabric_installed] Ошибка: {e}")
        return False

def is_mc_running() -> bool:
    window_titles = get_window_titles()
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = proc.info.get('name') or ""
            if 'java' in name.lower():
                cmd = proc.info.get('cmdline') or []
                if any('minecraft' in str(s).lower() for s in cmd) and any("1.21.8" in title for title in window_titles):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False

def get_window_titles() -> list:
    titles = []
    def enum_cb(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd).lower()
            if title and ("minecraft" in title or "1.21.8" in title):
                results.append(title)
    win32gui.EnumWindows(enum_cb, titles)
    return titles

def find_minecraft_hwnd():
    def callback(hwnd, hwnds):
        if win32gui.IsWindowVisible(hwnd):
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                p = psutil.Process(pid)
                if "javaw.exe" in p.name().lower():
                    title = win32gui.GetWindowText(hwnd)
                    if "Minecraft" in title:
                        hwnds.append(hwnd)
            except psutil.NoSuchProcess:
                pass
        return True

    result = []
    win32gui.EnumWindows(callback, result)
    return result[0] if result else None

import platform
def generate_software_machine_id():
    os_info = platform.platform()
    processor_info = platform.processor()
    unique_string = os_info + processor_info
    machine_id = hashlib.sha256(unique_string.encode()).hexdigest()
    return machine_id



def read_hwid_from_registry():
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        val, _ = winreg.QueryValueEx(key, REG_VALUE_DISK)  # Переиспользуем REG_VALUE_DISK для HWID
        winreg.CloseKey(key)
        return str(val)
    except FileNotFoundError:
        return None
    except Exception:
        return None

def write_hwid_to_registry(hwid_str):
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        winreg.SetValueEx(key, REG_VALUE_DISK, 0, winreg.REG_SZ, hwid_str)  # Переиспользуем REG_VALUE_DISK
        winreg.CloseKey(key)
        return True
    except Exception:
        return False

def get_banned_hwids():
    try:
        response = requests.get(f'{get_server_url()}/banned_hwids', timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при получении списка HWID: {e}")
        return []

def add_banned_hwid(hwid):
    try:
        response = requests.post(f'{get_server_url()}/banned_hwids/add', json={'hwid': hwid}, timeout=5)
        response.raise_for_status()
        return True
    except requests.RequestException as e:
        print(f"Ошибка при добавлении HWID: {e}")
        return False