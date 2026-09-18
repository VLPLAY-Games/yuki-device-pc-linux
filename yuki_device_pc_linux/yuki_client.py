from __future__ import annotations

import asyncio
import json
import time
from enum import Enum
from typing import Awaitable, Callable, Optional

from . import protocol_path  # noqa: F401
import websockets
from yuki_protocol import (
    YukiMessage,
    hello_message,
    status_message,
    extended_status_message,
    command_result_message,
    metrics_message,
    device_to_device_message,
    device_broadcast_message,
    device_response_message,
)

WS_CONNECT_TIMEOUT = 10
WELCOME_TIMEOUT = 65  # yuki-core can hold a new device pending admin approval for up to AUTH_TIMEOUT=60s before sending welcome
RECONNECT_BACKOFF_BASE = 3
RECONNECT_BACKOFF_MAX = 60
METRICS_INTERVAL = 60
STATUS_INTERVAL = 30


class ConnectionStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKING = "handshaking"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


# CommandHandler-style callable: (command, params) -> (success, result, error)
CommandExecutor = Callable[[str, dict], Awaitable[tuple]]


class YukiClient:
    def __init__(self):
        self.device_id = ""
        self.auth_token = ""
        self.enabled_capabilities: set[str] = set()

        self.command_handler: Optional[CommandExecutor] = None
        self.metrics_provider: Optional[Callable[[], dict]] = None

        self.on_status_change: Optional[Callable[[ConnectionStatus], None]] = None
        self.on_log: Optional[Callable[[str, str], None]] = None
        self.on_token_updated: Optional[Callable[[str], None]] = None
        self.on_device_command: Optional[Callable[[str, dict], Awaitable[object]]] = None
        self.on_device_broadcast: Optional[Callable[[str, dict], None]] = None

        self.status = ConnectionStatus.DISCONNECTED
        self._ws = None
        self._server_address = ""
        self._session_id = None
        self._heartbeat_interval = 30
        self._substatus = "idle"
        self._current_metrics: dict = {}

        self._reconnect_attempt = 0
        self._user_initiated_disconnect = False
        self._was_connected_once = False
        self._closing = False
        self._tasks: set[asyncio.Task] = set()

    # ==================== logging / status ====================
    def _log(self, level: str, message: str):
        if self.on_log:
            self.on_log(level, message)

    def _set_status(self, status: ConnectionStatus):
        if self.status != status:
            self.status = status
            if self.on_status_change:
                self.on_status_change(status)

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(lambda t: self._tasks.discard(t))
        return task

    async def _cancel_all_tasks(self):
        tasks = list(self._tasks)
        for t in tasks:
            t.cancel()
        for t in tasks:
            try:
                await t
            except (Exception, asyncio.CancelledError):
                # CancelledError is a BaseException (not Exception) since Python 3.8 - awaiting
                # a task we just cancelled always raises it here, so it must be caught explicitly
                # or disconnect()/force_disconnect() silently fail with no error surfaced anywhere.
                pass
        self._tasks.clear()

    # ==================== connection lifecycle ====================
    async def connect(self, server_address: str):
        if self.status not in (ConnectionStatus.DISCONNECTED, ConnectionStatus.RECONNECTING):
            await self.disconnect(user_initiated=True)

        self._server_address = server_address
        self._user_initiated_disconnect = False
        self._was_connected_once = False
        self._reconnect_attempt = 0
        self._closing = False

        await self._connect_once()

    async def _connect_once(self):
        self._set_status(ConnectionStatus.CONNECTING)
        self._log("INFO", f"Connecting to {self._server_address}...")
        uri = self._server_address.rstrip("/") + "/device"
        try:
            self._ws = await websockets.connect(uri, open_timeout=WS_CONNECT_TIMEOUT)
        except Exception as e:
            self._log("ERROR", f"Connection failed: {e}")
            self._set_status(ConnectionStatus.DISCONNECTED)
            return

        self._log("SUCCESS", "WebSocket connected, sending hello...")
        self._set_status(ConnectionStatus.HANDSHAKING)
        self._spawn(self._receive_loop())
        await self._send_hello()
        self._spawn(self._handshake_timeout_watch())

    async def _handshake_timeout_watch(self):
        try:
            await asyncio.sleep(WELCOME_TIMEOUT)
            if self.status == ConnectionStatus.HANDSHAKING:
                self._log("WARN", "Handshake timeout, forcing disconnect")
                await self.force_disconnect()
        except asyncio.CancelledError:
            pass

    async def disconnect(self, user_initiated: bool = True):
        self._user_initiated_disconnect = user_initiated
        self._closing = True
        await self._cancel_all_tasks()
        await self._close_ws()
        self._closing = False
        self._set_status(ConnectionStatus.DISCONNECTED)
        self._log("INFO", "Disconnected from server")

    async def force_disconnect(self):
        self._log("INFO", "Force disconnecting...")
        self._user_initiated_disconnect = True
        self._closing = True
        await self._cancel_all_tasks()
        await self._close_ws()
        self._closing = False
        self._set_status(ConnectionStatus.DISCONNECTED)

    async def _close_ws(self):
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _handle_connection_lost(self):
        if self._user_initiated_disconnect or self._closing:
            return
        if not self._was_connected_once:
            self._set_status(ConnectionStatus.DISCONNECTED)
            return
        self._log("WARN", "Connection lost, starting reconnection process...")
        self._set_status(ConnectionStatus.RECONNECTING)
        self._spawn(self._reconnect_loop())

    async def _reconnect_loop(self):
        try:
            while not self._user_initiated_disconnect and not self._closing:
                delay = min(RECONNECT_BACKOFF_BASE * (2 ** self._reconnect_attempt), RECONNECT_BACKOFF_MAX)
                self._log("INFO", f"Reconnection attempt {self._reconnect_attempt + 1} in {delay} seconds...")
                await asyncio.sleep(delay)
                if self._user_initiated_disconnect or self._closing:
                    break

                self._log("INFO", f"Attempting to reconnect to {self._server_address}...")
                if await self._try_reconnect():
                    self._reconnect_attempt = 0
                    self._log("SUCCESS", "Reconnection successful")
                    break
                self._reconnect_attempt += 1
                self._log("WARN", f"Reconnection attempt {self._reconnect_attempt} failed")
        except asyncio.CancelledError:
            pass

    async def _try_reconnect(self) -> bool:
        uri = self._server_address.rstrip("/") + "/device"
        try:
            self._ws = await websockets.connect(uri, open_timeout=WS_CONNECT_TIMEOUT)
        except Exception as e:
            self._log("ERROR", f"Reconnection error: {e}")
            return False

        self._log("SUCCESS", "WebSocket reconnected, sending hello...")
        self._set_status(ConnectionStatus.HANDSHAKING)
        self._spawn(self._receive_loop())
        await self._send_hello()
        self._spawn(self._handshake_timeout_watch())
        return True

    # ==================== sending ====================
    async def _send(self, msg: YukiMessage):
        if self._ws is None:
            return
        try:
            await self._ws.send(msg.to_json())
        except Exception as e:
            self._log("ERROR", f"Send failed: {e}")

    async def _send_raw(self, msg_type: str, payload: dict, msg_id: Optional[str] = None):
        await self._send(YukiMessage(msg_type, payload, msg_id))

    async def _send_hello(self):
        msg = hello_message(
            self.device_id, "yuki-device-pc-linux",
            sorted(self.enabled_capabilities), None, self.auth_token or None,
        )
        await self._send(msg)
        self._log("INFO", f"Sent hello for device '{self.device_id}' with {len(self.enabled_capabilities)} capabilities")

    async def set_extended_status(self, substatus: str, details: Optional[dict] = None):
        self._substatus = substatus
        if self.status == ConnectionStatus.CONNECTED:
            await self._send(extended_status_message(self.device_id, None, substatus, details))

    def update_metrics(self, metrics: dict):
        self._current_metrics.update(metrics)

    async def send_to_device(self, target_device_id: str, command: str, payload: Optional[dict] = None, require_response: bool = False):
        if self.status != ConnectionStatus.CONNECTED:
            self._log("WARN", "Cannot send to device: not connected")
            return
        await self._send(device_to_device_message(self.device_id, target_device_id, command, payload, require_response))
        self._log("INFO", f"Sent command to {target_device_id}: {command}")

    async def broadcast_to_devices(self, command: str, payload: Optional[dict] = None, device_filter: Optional[list] = None):
        if self.status != ConnectionStatus.CONNECTED:
            self._log("WARN", "Cannot broadcast: not connected")
            return
        await self._send(device_broadcast_message(self.device_id, command, payload, device_filter))
        self._log("INFO", f"Broadcast '{command}' to {len(device_filter) if device_filter else 0} devices")

    # ==================== periodic loops ====================
    async def _heartbeat_loop(self):
        try:
            while self.status == ConnectionStatus.CONNECTED:
                await asyncio.sleep(self._heartbeat_interval)
                if self.status != ConnectionStatus.CONNECTED:
                    break
                await self._send_raw("ping", {})
        except asyncio.CancelledError:
            pass

    async def _status_loop(self):
        try:
            while self.status == ConnectionStatus.CONNECTED:
                await asyncio.sleep(STATUS_INTERVAL)
                if self.status != ConnectionStatus.CONNECTED:
                    break
                await self._send(status_message(self.device_id, "online"))
        except asyncio.CancelledError:
            pass

    async def _metrics_loop(self):
        try:
            while self.status == ConnectionStatus.CONNECTED:
                await asyncio.sleep(METRICS_INTERVAL)
                if self.status != ConnectionStatus.CONNECTED:
                    break
                if self.metrics_provider:
                    try:
                        self._current_metrics.update(self.metrics_provider())
                    except Exception as e:
                        self._log("ERROR", f"Failed to collect metrics: {e}")
                self._current_metrics["timestamp"] = int(time.time())
                await self._send(metrics_message(self.device_id, dict(self._current_metrics)))
                self._log("DEBUG", f"Metrics sent: {len(self._current_metrics)} values")
        except asyncio.CancelledError:
            pass

    # ==================== receiving ====================
    async def _receive_loop(self):
        try:
            async for raw in self._ws:
                await self._process_message(raw)
        except websockets.exceptions.ConnectionClosed:
            self._log("INFO", "Connection closed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._log("ERROR", f"Receive error: {e}")
        finally:
            await self._handle_connection_lost()

    async def _process_message(self, raw: str):
        try:
            data = json.loads(raw)
        except ValueError:
            self._log("ERROR", "Invalid JSON message")
            return

        msg_type = data.get("type")
        payload = data.get("payload") or {}
        msg_id = data.get("id")
        self._log("DEBUG", f"Received: type={msg_type}, id={msg_id or 'n/a'}")

        if msg_type == "welcome":
            self._session_id = payload.get("session_id")
            self._heartbeat_interval = payload.get("heartbeat_interval", 30)
            self._was_connected_once = True
            self._set_status(ConnectionStatus.CONNECTED)
            await self._send(status_message(self.device_id, "online"))
            await self._send(extended_status_message(self.device_id, None, self._substatus, None))
            self._spawn(self._heartbeat_loop())
            self._spawn(self._status_loop())
            self._spawn(self._metrics_loop())
        elif msg_type == "command":
            await self._handle_command(payload, msg_id)
        elif msg_type == "device_command":
            await self._handle_device_command(payload, msg_id)
        elif msg_type == "device_broadcast":
            from_device_id = payload.get("from_device_id")
            command = payload.get("command")
            self._log("INFO", f"Device broadcast from {from_device_id}: {command}")
            if self.on_device_broadcast:
                self.on_device_broadcast(command, payload.get("payload") or {})
        elif msg_type == "device_response":
            self._log("INFO", f"Device response received: success={payload.get('success')}, error={payload.get('error')}")
        elif msg_type == "ping":
            await self._send_raw("pong", {}, msg_id)
        elif msg_type == "token_update":
            new_token = payload.get("new_token")
            if new_token:
                self.auth_token = new_token
                self._log("SUCCESS", "Token updated by server")
                if self.on_token_updated:
                    self.on_token_updated(new_token)
        elif msg_type == "disconnect":
            self._log("INFO", "Server requested disconnect")
            self._user_initiated_disconnect = True
            self._was_connected_once = False
            self._set_status(ConnectionStatus.DISCONNECTED)
            await self._close_ws()
        else:
            self._log("WARN", f"Unhandled message type: {msg_type}")

    async def _handle_command(self, payload: dict, msg_id: str):
        command = payload.get("command")
        params = payload.get("params") or {}
        self._log("INFO", f"Command received: {command}")

        if not command:
            await self._send(command_result_message(msg_id, False, None, "Missing command name"))
            return

        enabled_lower = {c.lower() for c in self.enabled_capabilities}
        if command.lower() not in enabled_lower:
            self._log("WARN", f"Command '{command}' is disabled")
            await self._send(command_result_message(msg_id, False, None, "Command disabled by user"))
            return

        if self.command_handler is None:
            await self._send(command_result_message(msg_id, False, None, "No command handler registered"))
            return

        success, result, error = await self.command_handler(command, params)
        await self._send(command_result_message(msg_id, success, result, error))

    async def _handle_device_command(self, payload: dict, msg_id: str):
        from_device_id = payload.get("from_device_id")
        command = payload.get("command")
        params = payload.get("payload") or {}
        require_response = bool(payload.get("require_response"))
        self._log("INFO", f"Device command from {from_device_id}: {command}")

        success, result, error = True, None, None
        if self.on_device_command:
            try:
                result = await self.on_device_command(command, params)
            except Exception as e:
                success, error = False, str(e)
        else:
            success, error = False, "No command handler registered"

        if require_response:
            await self._send(device_response_message(msg_id, self.device_id, from_device_id, success, result, error))
