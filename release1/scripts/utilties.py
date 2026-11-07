import datetime
import random
import re
import string

import minecraft_launcher_lib
import psutil
import requests
import win32gui
from .constants import *

max_value = 0

def get_server_url():
    return backend

def set_max(total):
    global max_value
    max_value = total


def set_status(*args):
    pass

def get_banned_ips():
    try:
        response = requests.get(f'{get_server_url()}/banned_ips')
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Ошибка при получении списка IP: {e}")
        return []

def get_external_ip():
    try:
        response = requests.get(external_ip_url)
        response.raise_for_status()
        ip_data = response.json()
        return ip_data['ip']
    except requests.RequestException as e:
        return f"Ошибка при получении IP: {e}"

def set_progress(progress, progress_callback):
    if max_value:
        percent = int((progress / max_value) * 100)
        progress_callback(min(percent, 100))


def is_mod_installed(MC_DIR, slug):
    mods_dir = os.path.join(MC_DIR, "mods")
    if os.path.exists(mods_dir):
        for file in os.listdir(mods_dir):
            if file.endswith('.jar') and slug in file:  # Более мягкая проверка
                return True
    return False

def download_with_progress(version, mc_path, progress_callback):
    global max_value
    max_value = 0

    def set_progress(progress):
        if isinstance(progress, dict):
            progress = progress.get("current", 0)
        try:
            if max_value:
                percent = (progress / max_value) * 100
                progress_callback(f"{int(percent)}%")
        except Exception as e:
            print("Ошибка в set_progress:", e)

    callback = {
        "setStatus": set_status,
        "setProgress": set_progress,
        "setMax": set_max
    }
    try:
        minecraft_launcher_lib.install.install_minecraft_version(
            version, mc_path, callback
        )
    except Exception as e:
        print(e)

    try:
        minecraft_launcher_lib.fabric.install_fabric(version, mc_path, callback=callback)
    except Exception as e:
        print(e)


def get_new_logfile(base_dir, prefix="launcher"):
    files = [f for f in os.listdir(base_dir) if f.startswith(prefix) and f.endswith(".log")]
    nums = []
    for f in files:
        m = re.match(rf"{prefix}_(\d+)\.log", f)
        if m:
            nums.append(int(m.group(1)))
    new_num = max(nums) + 1 if nums else 1
    if new_num >= 20:
        for f in files:
            os.remove(os.path.join(base_dir, f))
        new_num = 1

    return os.path.join(base_dir, f"{prefix}_{new_num}.log")


def send_log_line(msg: str, SERVER_URL):
    payload = {
        "log": f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg} \n"
    }
    try:
        requests.post(SERVER_URL, json=payload, timeout=3)
    except Exception as e:
        print("Ошибка отправки:", e)


def random_username(length=8):
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


def is_mc_running():
    def enum_titles(hwnd, titles):
        text = win32gui.GetWindowText(hwnd)
        if text:
            titles.append(text.lower())
        return True

    window_titles = []
    win32gui.EnumWindows(enum_titles, window_titles)
    for proc in psutil.process_iter(['name', 'cmdline']):
        try:
            name = proc.info.get('name') or ""
            if 'java' in name.lower():
                cmd = proc.info.get('cmdline') or []
                if any('minecraft' in str(s).lower() for s in cmd):
                    if any("1.21.8" in title for title in window_titles):
                        return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def get_window_titles():
    titles = []

    def enum_cb(hwnd, results):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title and ("minecraft" in title.lower() or "minecraft*" in title.lower() or "1.21.8"  in title.lower()):
                results.append(title)

    win32gui.EnumWindows(enum_cb, titles)
    return titles
