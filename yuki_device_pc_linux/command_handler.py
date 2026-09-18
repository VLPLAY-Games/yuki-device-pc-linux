from __future__ import annotations

import asyncio
import os
import shutil
from urllib.parse import urlparse

# capability name -> Linux implementation. Every function returns (success, result, error).

TEXT_EDITORS = ["gnome-text-editor", "gedit", "kate", "xed", "leafpad", "mousepad"]
CALCULATORS = ["gnome-calculator", "kcalc", "qalculate-gtk", "galculator", "xcalc"]


async def _run(*args) -> tuple:
    try:
        proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, stderr = await proc.communicate()
        if proc.returncode == 0:
            return True, None, None
        return False, None, stderr.decode(errors="replace").strip() or f"{args[0]} exited with code {proc.returncode}"
    except FileNotFoundError:
        return False, None, f"{args[0]} not found"
    except Exception as e:
        return False, None, str(e)


async def _launch(*args) -> tuple:
    try:
        await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL)
        return True, None, None
    except FileNotFoundError:
        return False, None, f"{args[0]} not found"
    except Exception as e:
        return False, None, str(e)


def _valid_http_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def _first_available(candidates: list) -> str | None:
    for name in candidates:
        path = shutil.which(name)
        if path:
            return path
    return None


async def open_browser(params: dict) -> tuple:
    url = params.get("url") or "https://www.google.com"
    if not _valid_http_url(url):
        return False, None, "Invalid or unsupported URL scheme"
    return await _launch("xdg-open", url)


async def shutdown(params: dict) -> tuple:
    return await _run("systemctl", "poweroff")


async def restart(params: dict) -> tuple:
    return await _run("systemctl", "reboot")


async def sleep_cmd(params: dict) -> tuple:
    return await _run("systemctl", "suspend")


async def lock(params: dict) -> tuple:
    ok, result, error = await _run("loginctl", "lock-session")
    if ok:
        return ok, result, error
    return await _run("xdg-screensaver", "lock")


async def set_volume(params: dict) -> tuple:
    try:
        level = int(params.get("level", 50))
    except (TypeError, ValueError):
        return False, None, "Invalid volume level"
    level = max(0, min(100, level))
    return await _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%")


async def volume_up(params: dict) -> tuple:
    return await _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", "+2%")


async def volume_down(params: dict) -> tuple:
    return await _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", "-2%")


async def volume_mute(params: dict) -> tuple:
    return await _run("pactl", "set-sink-mute", "@DEFAULT_SINK@", "1")


async def volume_unmute(params: dict) -> tuple:
    return await _run("pactl", "set-sink-mute", "@DEFAULT_SINK@", "0")


async def open_folder(params: dict) -> tuple:
    path = params.get("path") or os.path.expanduser("~")
    if not os.path.isdir(path):
        return False, None, f"Directory not found: {path}"
    return await _launch("xdg-open", path)


async def open_explorer(params: dict) -> tuple:
    path = params.get("path") or os.path.expanduser("~")
    if not os.path.isdir(path):
        return False, None, f"Directory not found: {path}"
    return await _launch("xdg-open", path)


async def open_notepad(params: dict) -> tuple:
    editor = _first_available(TEXT_EDITORS)
    if not editor:
        return False, None, "No text editor found"
    return await _launch(editor)


async def open_calculator(params: dict) -> tuple:
    calculator = _first_available(CALCULATORS)
    if not calculator:
        return False, None, "No calculator found"
    return await _launch(calculator)


HANDLERS = {
    "open_browser": open_browser,
    "open_url": open_browser,
    "shutdown": shutdown,
    "restart": restart,
    "sleep": sleep_cmd,
    "volume_up": volume_up,
    "volume_down": volume_down,
    "volume_mute": volume_mute,
    "volume_unmute": volume_unmute,
    "lock": lock,
    "set_volume": set_volume,
    "open_folder": open_folder,
    "open_explorer": open_explorer,
    "open_notepad": open_notepad,
    "open_calculator": open_calculator,
}

CAPABILITIES = list(HANDLERS.keys())
DEFAULT_DISABLED = {"shutdown", "restart", "sleep"}


async def execute(command: str, params: dict) -> tuple:
    handler = HANDLERS.get(command)
    if handler is None:
        return False, None, "unknown_command"
    return await handler(params or {})
