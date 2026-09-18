from __future__ import annotations

import json
import os
import socket

from .command_handler import CAPABILITIES, DEFAULT_DISABLED

CONFIG_DIR = os.path.expanduser("~/.config/yuki-device-pc-linux")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS = {
    "server_address": "ws://localhost:8000",
    "device_id": f"pc-{socket.gethostname().lower()}",
    "auth_token": "",
    "enabled_capabilities": [c for c in CAPABILITIES if c not in DEFAULT_DISABLED],
    "substatus": "idle",
    "window_width": 580,
    "window_height": 720,
}


def load() -> dict:
    if not os.path.exists(SETTINGS_FILE):
        return dict(DEFAULTS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return dict(DEFAULTS)

    merged = dict(DEFAULTS)
    merged.update({k: v for k, v in data.items() if k in DEFAULTS})
    if not merged.get("device_id"):
        merged["device_id"] = DEFAULTS["device_id"]
    return merged


def save(settings: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp_path = SETTINGS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, SETTINGS_FILE)
