import getpass
import platform
import socket
import time

import psutil

_start_time = time.time()


def collect_metrics() -> dict:
    metrics = {}

    try:
        metrics["cpu"] = round(psutil.cpu_percent(interval=0.1), 1)
    except Exception:
        metrics["cpu"] = 0

    try:
        vm = psutil.virtual_memory()
        metrics["memory_percent"] = round(vm.percent, 1)
        metrics["memory_used_gb"] = round((vm.total - vm.available) / (1024 ** 3), 1)
        metrics["memory_total_gb"] = round(vm.total / (1024 ** 3), 1)
    except Exception:
        pass

    try:
        du = psutil.disk_usage("/")
        metrics["disk_percent"] = round(du.percent, 1)
        metrics["disk_used_gb"] = round(du.used / (1024 ** 3), 1)
        metrics["disk_total_gb"] = round(du.total / (1024 ** 3), 1)
    except Exception:
        pass

    metrics["uptime_seconds"] = int(time.time() - _start_time)
    metrics["os"] = platform.platform()
    metrics["hostname"] = socket.gethostname()
    metrics["username"] = getpass.getuser()

    return metrics
