"""
Yuki Protocol v1.0 – унифицированная версия для Python, C#, JavaScript и C++
Поддерживает все сообщения: управление подключением, статусы, команды,
авторизацию, токены, метрики, связь устройств.
"""
import json
import time
import uuid
from typing import Optional, Dict, Any, List

PROTOCOL_VERSION = "yuki/1.0"
MAX_MESSAGE_SIZE = 1_048_576  # 1 MiB

class YukiMessage:
    def __init__(self, msg_type: str, payload: Dict[str, Any], msg_id: Optional[str] = None):
        self.protocol = PROTOCOL_VERSION
        self.type = msg_type
        self.id = msg_id or str(uuid.uuid4())
        self.timestamp = int(time.time())
        self.payload = payload

    def to_json(self) -> str:
        return json.dumps({
            "protocol": self.protocol,
            "type": self.type,
            "id": self.id,
            "timestamp": self.timestamp,
            "payload": self.payload
        }, separators=(',', ':'))

    @classmethod
    def from_json(cls, data: str) -> "YukiMessage":
        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError(f"Message too large: {len(data)} bytes")
        obj = json.loads(data)
        if obj.get("protocol") != "yuki/1.0":
            raise ValueError(f"Unsupported protocol version: {obj.get('protocol')}")
        msg = cls(obj["type"], obj.get("payload", {}), obj.get("id"))
        msg.timestamp = obj.get("timestamp", msg.timestamp)
        return msg


# ============ УПРАВЛЕНИЕ ПОДКЛЮЧЕНИЕМ ============

def hello_message(device_id: str, device_type: str,
                  capabilities: List[str] = None,
                  metadata: Dict = None,
                  auth_token: str = None) -> YukiMessage:
    payload = {
        "device_id": device_id,
        "device_type": device_type,
        "capabilities": capabilities or []
    }
    if metadata:
        payload["metadata"] = metadata
    if auth_token:
        payload["auth_token"] = auth_token
    return YukiMessage("hello", payload)


def welcome_message(session_id: str, server_time: int,
                    heartbeat_interval: int = 30) -> YukiMessage:
    return YukiMessage("welcome", {
        "session_id": session_id,
        "server_time": server_time,
        "heartbeat_interval": heartbeat_interval
    })


# ============ СТАТУСЫ ============

def status_message(device_id: str, status: str,
                   details: Dict = None) -> YukiMessage:
    payload = {"device_id": device_id, "status": status}
    if details:
        payload["details"] = details
    return YukiMessage("status", payload)


def extended_status_message(device_id: str,
                            status: Optional[str] = None,
                            substatus: Optional[str] = None,
                            details: Dict = None) -> YukiMessage:
    """
    Расширенный статус устройства.
    status – основной статус (online/offline/pending) – опционально.
    substatus – дополнительный (idle, working, sleeping, ...).
    details – любые дополнительные данные.
    """
    payload = {"device_id": device_id}
    if status is not None:
        payload["status"] = status
    if substatus:
        payload["substatus"] = substatus
    if details:
        payload["details"] = details
    return YukiMessage("extended_status", payload)


# ============ КОМАНДЫ ============

def command_message(device_id: str, command: str,
                    params: Dict = None) -> YukiMessage:
    return YukiMessage("command", {
        "device_id": device_id,
        "command": command,
        "params": params or {}
    })


def command_result_message(original_id: str, success: bool,
                           result: Any = None, error: str = None) -> YukiMessage:
    msg = YukiMessage("command_result", {
        "success": success,
        "result": result,
        "error": error
    })
    msg.id = original_id
    return msg


def confirm_command_message(device_id: str, command: str,
                            params: Dict = None) -> YukiMessage:
    return YukiMessage("confirm_command", {
        "device_id": device_id,
        "command": command,
        "params": params or {}
    })


def confirm_response_message(original_id: str, approved: bool) -> YukiMessage:
    msg = YukiMessage("confirm_response", {"approved": approved})
    msg.id = original_id
    return msg


# ============ УПРАВЛЕНИЕ УСТРОЙСТВАМИ ============

def devices_update_message(devices: Dict[str, Dict],
                           removed: List[str] = None) -> YukiMessage:
    payload = {"devices": devices}
    if removed:
        payload["removed"] = removed
    return YukiMessage("devices_update", payload)


def device_auth_request_message(device_id: str, device_type: str,
                                capabilities: List[str]) -> YukiMessage:
    return YukiMessage("device_auth_request", {
        "device_id": device_id,
        "device_type": device_type,
        "capabilities": capabilities
    })


def device_auth_response_message(request_id: str, approved: bool) -> YukiMessage:
    msg = YukiMessage("device_auth_response", {"approved": approved})
    msg.id = request_id
    return msg


# ============ ТОКЕНЫ ============

def token_update_message(new_token: str, reason: str = "admin") -> YukiMessage:
    return YukiMessage("token_update", {
        "new_token": new_token,
        "reason": reason
    })


def token_info_message(created_at: Optional[float],
                       rotation_interval_hours: int,
                       expires_in: Optional[float] = None) -> YukiMessage:
    payload = {
        "created_at": created_at,
        "rotation_interval_hours": rotation_interval_hours
    }
    if expires_in is not None:
        payload["expires_in"] = expires_in
    return YukiMessage("token_info", payload)


def token_rotated_message(success: bool,
                          new_token: Optional[str] = None) -> YukiMessage:
    payload = {"success": success}
    if new_token:
        payload["new_token"] = new_token
    return YukiMessage("token_rotated", payload)


def rotate_token_request_message() -> YukiMessage:
    return YukiMessage("rotate_token", {})


def get_token_info_request_message() -> YukiMessage:
    return YukiMessage("get_token_info", {})


# ============ МЕТРИКИ ============

def metrics_message(device_id: str, metrics: Dict) -> YukiMessage:
    return YukiMessage("metrics", {
        "device_id": device_id,
        "metrics": metrics,
        "timestamp": int(time.time())
    })


def metrics_request_message(device_id: str,
                            metric_types: List[str] = None) -> YukiMessage:
    return YukiMessage("metrics_request", {
        "device_id": device_id,
        "metric_types": metric_types or []
    })


# ============ СВЯЗЬ УСТРОЙСТВО–УСТРОЙСТВО ============

def device_to_device_message(from_device_id: str, to_device_id: str,
                             command: str, payload: Dict = None,
                             require_response: bool = False) -> YukiMessage:
    return YukiMessage("device_to_device", {
        "from_device_id": from_device_id,
        "to_device_id": to_device_id,
        "command": command,
        "payload": payload or {},
        "require_response": require_response,
        "sent_at": int(time.time())
    })


def device_response_message(original_id: str, from_device_id: str,
                            to_device_id: str, success: bool,
                            result: Any = None, error: str = None) -> YukiMessage:
    msg = YukiMessage("device_response", {
        "from_device_id": from_device_id,
        "to_device_id": to_device_id,
        "success": success,
        "result": result,
        "error": error
    })
    msg.id = original_id
    return msg


def device_broadcast_message(from_device_id: str, command: str,
                             payload: Dict = None,
                             device_filter: List[str] = None) -> YukiMessage:
    return YukiMessage("device_broadcast", {
        "from_device_id": from_device_id,
        "command": command,
        "payload": payload or {},
        "device_filter": device_filter,
        "sent_at": int(time.time())
    })