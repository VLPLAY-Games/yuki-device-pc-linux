from __future__ import annotations

import json
import subprocess

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import settings as settings_module  # noqa: E402
from .asyncio_bridge import AsyncioBridge  # noqa: E402
from .command_handler import CAPABILITIES, DEFAULT_DISABLED  # noqa: E402
from .command_handler import execute as execute_command  # noqa: E402
from .logger import Logger  # noqa: E402
from .metrics import collect_metrics  # noqa: E402
from .yuki_client import ConnectionStatus, YukiClient  # noqa: E402

SUBSTATUS_OPTIONS = ["idle", "working", "sleeping", "charging", "error", "updating", "maintenance"]

STATUS_LABELS = {
    ConnectionStatus.DISCONNECTED: ("Offline", "error"),
    ConnectionStatus.CONNECTING: ("Connecting…", "warning"),
    ConnectionStatus.HANDSHAKING: ("Handshaking…", "warning"),
    ConnectionStatus.CONNECTED: ("Connected", "success"),
    ConnectionStatus.RECONNECTING: ("Reconnecting…", "warning"),
}

LOG_COLORS = {
    "INFO": "#3584e4",
    "WARN": "#e5a50a",
    "ERROR": "#e01b24",
    "DEBUG": "#9a9996",
    "SUCCESS": "#2ec27e",
}


class YukiWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_default_size(580, 780)
        self.set_title("Yuki PC (Linux)")

        self.settings = settings_module.load()
        self.logger = Logger()
        self.bridge = AsyncioBridge()

        self.client = YukiClient()
        self.client.command_handler = execute_command
        self.client.metrics_provider = collect_metrics
        self.client.on_log = self._on_client_log
        self.client.on_status_change = self._on_client_status
        self.client.on_token_updated = self._on_token_updated

        self.switch_rows: dict[str, Adw.SwitchRow] = {}
        self._quitting = False

        self._build_ui()
        self._apply_settings_to_ui()

        self.connect("close-request", self._on_close_request)

    # ==================== UI construction ====================
    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        self.set_content(toolbar_view)

        header = Adw.HeaderBar()
        header.set_title_widget(Adw.WindowTitle(title="Yuki PC (Linux)", subtitle="Offline"))
        self.window_title = header.get_title_widget()

        self.logs_toggle = Gtk.ToggleButton(icon_name="utilities-terminal-symbolic", tooltip_text="Show logs")
        self.logs_toggle.connect("toggled", self._on_logs_toggled)
        header.pack_end(self.logs_toggle)

        theme_button = Gtk.Button(icon_name="weather-clear-night-symbolic", tooltip_text="Toggle dark/light theme")
        theme_button.connect("clicked", self._on_theme_toggle)
        header.pack_end(theme_button)

        menu = Gio.Menu()
        menu.append("Open Logs Folder", "win.open-logs")
        menu.append("Quit", "app.quit")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu)
        header.pack_end(menu_button)

        open_logs_action = Gio.SimpleAction.new("open-logs", None)
        open_logs_action.connect("activate", lambda *_: self._open_path(self.logger.get_log_folder()))
        self.add_action(open_logs_action)

        toolbar_view.add_top_bar(header)

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        scrolled = Gtk.ScrolledWindow(vexpand=True)
        clamp = Adw.Clamp(maximum_size=560, margin_top=16, margin_bottom=16, margin_start=12, margin_end=12)
        page_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        clamp.set_child(page_box)
        scrolled.set_child(clamp)
        outer_box.append(scrolled)

        page_box.append(self._build_server_group())
        page_box.append(self._build_extended_status_group())
        page_box.append(self._build_send_to_device_group())
        page_box.append(self._build_capabilities_group())

        self.log_revealer = Gtk.Revealer(reveal_child=False)
        self.log_revealer.set_child(self._build_log_view())
        outer_box.append(self.log_revealer)

        toolbar_view.set_content(outer_box)

    def _build_server_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Server Connection")

        self.address_row = Adw.EntryRow(title="Address")
        group.add(self.address_row)

        self.device_id_row = Adw.EntryRow(title="Device ID")
        group.add(self.device_id_row)

        self.token_row = Adw.PasswordEntryRow(title="Auth Token")
        group.add(self.token_row)

        self.status_row = Adw.ActionRow(title="Status")
        self.status_label = Gtk.Label(label="Offline")
        self.status_label.add_css_class("error")
        self.status_row.add_suffix(self.status_label)
        group.add(self.status_row)

        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, margin_top=6, margin_bottom=6)
        self.connect_button = Gtk.Button(label="Connect")
        self.connect_button.add_css_class("suggested-action")
        self.connect_button.connect("clicked", self._on_connect_clicked)
        button_box.append(self.connect_button)

        self.open_panel_button = Gtk.Button(label="Open Control Panel", sensitive=False)
        self.open_panel_button.connect("clicked", self._on_open_panel_clicked)
        button_box.append(self.open_panel_button)

        group.add(button_box)

        return group

    def _build_extended_status_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Extended Status")

        self.substatus_model = Gtk.StringList.new(SUBSTATUS_OPTIONS)
        self.substatus_row = Adw.ComboRow(title="Substatus", model=self.substatus_model)
        self.substatus_row.set_expression(Gtk.PropertyExpression.new(Gtk.StringObject, None, "string"))
        group.add(self.substatus_row)

        update_button = Gtk.Button(label="Update", halign=Gtk.Align.START, margin_top=6, margin_start=6, margin_bottom=6)
        update_button.connect("clicked", self._on_update_status_clicked)
        group.add(update_button)

        return group

    def _build_send_to_device_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Send to Device")

        self.target_device_row = Adw.EntryRow(title="Target Device")
        group.add(self.target_device_row)

        self.command_row = Adw.EntryRow(title="Command")
        group.add(self.command_row)

        self.payload_row = Adw.EntryRow(title="Payload (JSON)")
        self.payload_row.set_text("{}")
        group.add(self.payload_row)

        send_button = Gtk.Button(label="Send to Device", halign=Gtk.Align.START, margin_top=6, margin_start=6, margin_bottom=6)
        send_button.connect("clicked", self._on_send_to_device_clicked)
        group.add(send_button)

        return group

    def _build_capabilities_group(self) -> Adw.PreferencesGroup:
        group = Adw.PreferencesGroup(title="Enabled Capabilities")
        expander = Adw.ExpanderRow(title="Capabilities", subtitle=f"{len(CAPABILITIES)} available")
        for capability in CAPABILITIES:
            row = Adw.SwitchRow(title=capability)
            row.set_active(capability not in DEFAULT_DISABLED)
            row.connect("notify::active", self._on_capability_toggled, capability)
            expander.add_row(row)
            self.switch_rows[capability] = row
        group.add(expander)
        return group

    def _build_log_view(self) -> Gtk.Widget:
        scrolled = Gtk.ScrolledWindow(height_request=220, vexpand=False)
        self.log_buffer = Gtk.TextBuffer()
        for level, color in LOG_COLORS.items():
            self.log_buffer.create_tag(level, foreground=color)
        self.log_view = Gtk.TextView(buffer=self.log_buffer, editable=False, cursor_visible=False)
        self.log_view.add_css_class("monospace")
        scrolled.set_child(self.log_view)
        return scrolled

    # ==================== settings <-> UI ====================
    def _apply_settings_to_ui(self):
        self.address_row.set_text(self.settings["server_address"])
        self.device_id_row.set_text(self.settings["device_id"])
        self.token_row.set_text(self.settings["auth_token"])

        try:
            index = SUBSTATUS_OPTIONS.index(self.settings.get("substatus", "idle"))
        except ValueError:
            index = 0
        self.substatus_row.set_selected(index)

        enabled = set(self.settings.get("enabled_capabilities", []))
        for capability, row in self.switch_rows.items():
            row.set_active(capability in enabled)
        self.client.enabled_capabilities = enabled

        self.client.device_id = self.settings["device_id"]
        self.client.auth_token = self.settings["auth_token"]

        self.address_row.connect("changed", self._on_address_changed)
        self.device_id_row.connect("changed", self._on_device_id_changed)
        self.token_row.connect("changed", self._on_token_changed)

    def _save_settings(self):
        self.settings["enabled_capabilities"] = [c for c, row in self.switch_rows.items() if row.get_active()]
        settings_module.save(self.settings)

    # ==================== event handlers ====================
    def _on_address_changed(self, row):
        self.settings["server_address"] = row.get_text()
        self._save_settings()

    def _on_device_id_changed(self, row):
        self.settings["device_id"] = row.get_text()
        self.client.device_id = row.get_text()
        self._save_settings()

    def _on_token_changed(self, row):
        self.settings["auth_token"] = row.get_text()
        self.client.auth_token = row.get_text()
        self._save_settings()

    def _on_capability_toggled(self, row, _pspec, capability):
        if row.get_active():
            self.client.enabled_capabilities.add(capability)
        else:
            self.client.enabled_capabilities.discard(capability)
        self._save_settings()

    def _on_connect_clicked(self, _button):
        if self.client.status in (ConnectionStatus.DISCONNECTED,):
            self.bridge.run_coroutine(self.client.connect(self.address_row.get_text()))
        else:
            self.bridge.run_coroutine(self.client.disconnect(user_initiated=True))

    def _on_open_panel_clicked(self, _button):
        address = self.address_row.get_text()
        http_url = address.replace("wss://", "https://").replace("ws://", "http://").replace(":8000", ":5000")
        self._open_path(http_url)

    def _on_update_status_clicked(self, _button):
        item = self.substatus_row.get_selected_item()
        substatus = item.get_string() if item else "idle"
        self.settings["substatus"] = substatus
        self._save_settings()
        self.bridge.run_coroutine(self.client.set_extended_status(substatus))

    def _on_send_to_device_clicked(self, _button):
        target = self.target_device_row.get_text().strip()
        command = self.command_row.get_text().strip()
        payload_text = self.payload_row.get_text().strip() or "{}"

        if not target or not command:
            self._show_toast("Target device and command are required")
            return

        try:
            payload = json.loads(payload_text)
        except ValueError as e:
            self._show_toast(f"Invalid JSON payload: {e}")
            return

        self.bridge.run_coroutine(self.client.send_to_device(target, command, payload))

    def _on_logs_toggled(self, button):
        self.log_revealer.set_reveal_child(button.get_active())

    def _on_theme_toggle(self, _button):
        style_manager = Adw.StyleManager.get_default()
        if style_manager.get_color_scheme() == Adw.ColorScheme.FORCE_DARK:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        else:
            style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)

    def _on_close_request(self, *_args):
        self.hide()
        return True

    # ==================== client callbacks (background thread -> GTK thread) ====================
    def _on_client_log(self, level, message):
        GLib.idle_add(self._append_log, level, message)

    def _append_log(self, level, message):
        end_iter = self.log_buffer.get_end_iter()
        tag = self.log_buffer.get_tag_table().lookup(level) or self.log_buffer.get_tag_table().lookup("INFO")
        self.log_buffer.insert_with_tags(end_iter, f"[{level}] {message}\n", tag)
        mark = self.log_buffer.get_insert()
        self.log_view.scroll_mark_onscreen(mark)
        return False

    def _on_client_status(self, status):
        GLib.idle_add(self._update_status_ui, status)

    def _update_status_ui(self, status):
        text, css_class = STATUS_LABELS.get(status, ("Unknown", "dim-label"))
        self.status_label.set_label(text)
        for cls in ("error", "warning", "success", "dim-label"):
            self.status_label.remove_css_class(cls)
        self.status_label.add_css_class(css_class)
        self.window_title.set_subtitle(text)

        connecting = status in (ConnectionStatus.CONNECTING, ConnectionStatus.HANDSHAKING)
        self.connect_button.set_sensitive(not connecting)
        self.connect_button.set_label("Disconnect" if status != ConnectionStatus.DISCONNECTED else "Connect")
        self.open_panel_button.set_sensitive(status == ConnectionStatus.CONNECTED)
        return False

    def _on_token_updated(self, new_token):
        GLib.idle_add(self._set_token_entry, new_token)

    def _set_token_entry(self, new_token):
        self.token_row.set_text(new_token)
        self.settings["auth_token"] = new_token
        self._save_settings()
        return False

    # ==================== helpers ====================
    def _open_path(self, path_or_url: str):
        try:
            subprocess.Popen(["xdg-open", path_or_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            self._show_toast("xdg-open not found")

    def _show_toast(self, message: str):
        # Best-effort inline feedback; falls back to a log line if no toast overlay is present.
        self._on_client_log("WARN", message)

    def shutdown(self):
        self._quitting = True
        try:
            self.bridge.run_coroutine(self.client.disconnect(user_initiated=True)).result(timeout=3)
        except Exception:
            pass
        self.bridge.stop()
