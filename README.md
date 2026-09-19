# Yuki PC (Linux)

A Linux remote-control client for the Yuki ecosystem, with the same feature set as
[`yuki-device-pc`](../yuki-device-pc) (the Windows client): connects to `yuki-core`, reports status
and system metrics, and executes commands the server or other devices send it. Built with Python +
GTK4/libadwaita so it can reuse `yuki-protocol`'s own Python implementation directly instead of
reimplementing the wire format a fourth time.

## Requirements

- Python 3.10+
- GTK4 and libadwaita (>= 1.4) with their GObject-Introspection bindings - install via your distro's
  packages, not pip:
  - Debian/Ubuntu: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1`
  - Fedora: `sudo dnf install python3-gobject gtk4 libadwaita`
  - Arch: `sudo pacman -S python-gobject gtk4 libadwaita`
- `xdg-utils` (for `xdg-open`), `pactl` (PulseAudio/PipeWire) for volume control,
  `systemd`/`logind` (`systemctl`, `loginctl`) for power/lock commands - all standard on mainstream
  desktop distros.

## Running

```bash
git clone --recurse-submodules https://github.com/VLPLAY-Games/yuki-device-pc-linux
cd yuki-device-pc-linux
python3 -m venv --system-site-packages .venv   # --system-site-packages so it can see GTK4/libadwaita
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m yuki_device_pc_linux.main
```

If you already cloned without `--recurse-submodules`, fetch the protocol submodule separately:

```bash
git submodule update --init
```

`libs/yuki-protocol` is a git submodule pointing at
[VLPLAY-Games/yuki-protocol](https://github.com/VLPLAY-Games/yuki-protocol) (same pattern
`yuki-core`, `yuki-webui` and `yuki-device-pc` use) - it does not need the sibling `yuki-protocol`
checkout from this repo's parent folder to run, since the submodule brings its own copy.

## Configuration

Everything is set from the app's UI (Server Connection / Extended Status / Send to Device /
Capabilities sections) and persisted to `~/.config/yuki-device-pc-linux/settings.json` (mode 600):
server address, device id, auth token, enabled capabilities (all 15 on by default except
`shutdown`/`restart`/`sleep`), substatus, and window size. Logs go to
`~/.local/share/yuki-device-pc-linux/logs/`, one file per run.

Type `wss://host:port` in the address field for an encrypted connection if `yuki-core` has TLS
enabled - it works with no other configuration.

## Commands

Same 15 capabilities as the Windows client, mapped to Linux equivalents: `xdg-open` for
browser/URL/folder commands, `systemctl poweroff/reboot/suspend` for shutdown/restart/sleep,
`loginctl lock-session` (falling back to `xdg-screensaver lock`) for lock, `pactl` for volume, and
the first available GUI text editor/calculator on the system for `open_notepad`/`open_calculator`.
`open_browser`/`open_url` only accept `http`/`https` URLs.

## Autostart

Copy `packaging/yuki-device-pc-linux` to `~/.local/bin/`, edit the `REPO_DIR` placeholder inside it
to point at your checkout, and `chmod +x` it. Then either:

- **Desktop launcher**: copy `packaging/yuki-device-pc-linux.desktop` to
  `~/.local/share/applications/`.
- **Autostart at login (systemd user service)**: copy `packaging/yuki-device-pc-linux.service` to
  `~/.config/systemd/user/`, then `systemctl --user enable --now yuki-device-pc-linux.service`.

## Troubleshooting

**`ModuleNotFoundError: No module named 'gi'`** - the venv was created without
`--system-site-packages`, so it can't see the system's PyGObject/GTK4/libadwaita install. Fix:

```bash
rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

(`pip install PyGObject` inside an isolated venv is *not* a fix here - it needs system dev
packages like `libgirepository` to even build, and would give you a second, disconnected copy of
the bindings instead of the one that's actually wired to your installed GTK4/libadwaita.)

## Design notes vs. the Windows client

- Closing the window hides it instead of quitting (the background connection and asyncio loop keep
  running); there's no system tray icon since GTK4 dropped built-in tray support ecosystem-wide -
  reopen the window by launching the app again (it's a single-instance `Gio.Application`, so a
  second launch just re-presents the existing window), or use the autostart methods above.
- Settings live under `~/.config/` (XDG) rather than next to the executable.

## Protocol

Speaks Yuki Protocol `yuki/1.0` - see [`yuki-protocol`](../yuki-protocol). Authenticates with the
legacy handshake (auth token sent directly in `hello`) - `yuki-core` also supports a
challenge-response handshake that never puts the token on the wire (`hello{nonce_c}` →
`challenge{nonce_s}` → `auth{hmac}`), which this client doesn't use yet but is fully forward
compatible with, since `yuki-core` falls back to the legacy method whenever `hello` has no
`nonce_c`. Use `wss://` in the address field if `yuki-core` has TLS enabled - either way, connect
over an untrusted network only with TLS on, since the legacy handshake still exposes the token.

## License

GNU General Public License v3.0 (GPLv3), same as the rest of the Yuki ecosystem - see
[yuki-system](https://github.com/VLPLAY-Games/yuki-system) for details.
