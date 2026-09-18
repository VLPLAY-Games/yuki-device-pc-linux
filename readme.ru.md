# Yuki PC (Linux)

Linux-клиент удалённого управления для экосистемы Yuki с тем же набором возможностей, что и у
[`yuki-device-pc`](../yuki-device-pc) (клиент для Windows): подключается к `yuki-core`, сообщает
статус и системные метрики и выполняет команды, присылаемые сервером или другими устройствами.
Написан на Python + GTK4/libadwaita, чтобы напрямую переиспользовать собственную Python-реализацию
`yuki-protocol`, а не реализовывать формат сообщений ещё раз, уже в четвёртый.

## Требования

- Python 3.10+
- GTK4 и libadwaita (>= 1.4) вместе с их биндингами GObject-Introspection - устанавливайте из
  пакетов вашего дистрибутива, а не через pip:
  - Debian/Ubuntu: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1`
  - Fedora: `sudo dnf install python3-gobject gtk4 libadwaita`
  - Arch: `sudo pacman -S python-gobject gtk4 libadwaita`
- `xdg-utils` (для `xdg-open`), `pactl` (PulseAudio/PipeWire) для управления громкостью,
  `systemd`/`logind` (`systemctl`, `loginctl`) для команд питания/блокировки - всё это есть по
  умолчанию в основных десктопных дистрибутивах.

## Запуск

```bash
git clone <этот репозиторий, рядом с остальной экосистемой Yuki, чтобы разрешались пути вида ../yuki-protocol>
cd yuki-device-pc-linux
python3 -m venv --system-site-packages .venv   # --system-site-packages, чтобы venv видел GTK4/libadwaita
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m yuki_device_pc_linux.main
```

Папка `libs/yuki-protocol/python/` - это встроенная копия Python-реализации
[`yuki-protocol`](../yuki-protocol) (тот же приём, что используют `yuki-core` и `yuki-webui`) -
для запуска не требуется отдельно выкладывать рядом репозиторий `yuki-protocol`.

## Конфигурация

Всё настраивается через интерфейс приложения (разделы Server Connection / Extended Status / Send
to Device / Capabilities) и сохраняется в `~/.config/yuki-device-pc-linux/settings.json` (права
доступа 600): адрес сервера, идентификатор устройства, токен аутентификации, разрешённые команды
(по умолчанию все 14, кроме `shutdown`/`restart`/`sleep`), substatus и размер окна. Логи пишутся в
`~/.local/share/yuki-device-pc-linux/logs/`, по одному файлу на запуск.

Введите `wss://host:port` в поле адреса для зашифрованного соединения, если на `yuki-core`
включён TLS - никакой дополнительной настройки для этого не требуется.

## Команды

Те же 14 команд, что и у клиента для Windows, сопоставленные с их аналогами в Linux: `xdg-open`
для команд браузера/URL/папки, `systemctl poweroff/reboot/suspend` для shutdown/restart/sleep,
`loginctl lock-session` (с откатом на `xdg-screensaver lock`) для lock, `pactl` для громкости, а
также первый доступный в системе графический текстовый редактор/калькулятор для
`open_notepad`/`open_calculator`. `open_browser`/`open_url` принимают только URL со схемой
`http`/`https`.

## Автозапуск

Скопируйте `packaging/yuki-device-pc-linux` в `~/.local/bin/`, замените внутри него плейсхолдер
`REPO_DIR` на путь к вашей копии репозитория и выполните `chmod +x`. Затем один из двух вариантов:

- **Ярлык в меню приложений**: скопируйте `packaging/yuki-device-pc-linux.desktop` в
  `~/.local/share/applications/`.
- **Автозапуск при входе в систему (пользовательский сервис systemd)**: скопируйте
  `packaging/yuki-device-pc-linux.service` в `~/.config/systemd/user/`, затем выполните
  `systemctl --user enable --now yuki-device-pc-linux.service`.

## Устранение неполадок

**`ModuleNotFoundError: No module named 'gi'`** - venv создан без `--system-site-packages`, из-за
чего он не видит системные PyGObject/GTK4/libadwaita. Решение:

```bash
rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

(`pip install PyGObject` внутри изолированного venv здесь не поможет - для сборки нужны системные
dev-пакеты вроде `libgirepository`, и в итоге получится отдельная, никак не связанная копия
биндингов вместо той, что реально подключена к установленным у вас GTK4/libadwaita.)

## Отличия от клиента для Windows

- Закрытие окна скрывает его, а не завершает работу приложения (фоновое соединение и цикл asyncio
  продолжают работать); значка в системном трее нет, поскольку GTK4 повсеместно убрал встроенную
  поддержку трея - чтобы снова открыть окно, запустите приложение ещё раз (это однопроцессное
  `Gio.Application`, поэтому повторный запуск просто выводит на передний план уже открытое окно)
  либо воспользуйтесь способами автозапуска выше.
- Настройки хранятся в `~/.config/` (по стандарту XDG), а не рядом с исполняемым файлом.

## Протокол

Использует Yuki Protocol `yuki/1.0` - см. [`yuki-protocol`](../yuki-protocol).
