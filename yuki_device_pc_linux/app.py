from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio  # noqa: E402

from .window import YukiWindow  # noqa: E402

APPLICATION_ID = "games.vlplay.YukiDevicePCLinux"


class YukiApplication(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APPLICATION_ID, flags=Gio.ApplicationFlags.FLAGS_NONE)
        self.window: YukiWindow | None = None

        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_a: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<primary>q"])

    def do_activate(self):
        if self.window is None:
            self.window = YukiWindow(application=self)
        self.window.present()

    def do_shutdown(self):
        if self.window is not None:
            self.window.shutdown()
        Adw.Application.do_shutdown(self)
