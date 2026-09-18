from __future__ import annotations

import os
from datetime import datetime
from typing import Callable, Optional

LOG_DIR = os.path.expanduser("~/.local/share/yuki-device-pc-linux/logs")


class Logger:
    def __init__(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S.log")
        self.path = os.path.join(LOG_DIR, filename)
        self.on_log: Optional[Callable[[str, str], None]] = None

    def _write(self, level: str, message: str):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {message}"
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        if self.on_log:
            self.on_log(level, message)

    def info(self, message: str):
        self._write("INFO", message)

    def warn(self, message: str):
        self._write("WARN", message)

    def error(self, message: str):
        self._write("ERROR", message)

    def debug(self, message: str):
        self._write("DEBUG", message)

    def success(self, message: str):
        self._write("SUCCESS", message)

    def log(self, level: str, message: str):
        self._write(level.upper(), message)

    def get_log_folder(self) -> str:
        return LOG_DIR
