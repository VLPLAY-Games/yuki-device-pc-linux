# Yuki PC (Linux)

Yuki エコシステム向けの Linux リモート制御クライアントで、[`yuki-device-pc`](../yuki-device-pc)（Windows クライアント）と同じ機能セットを持ちます。`yuki-core` に接続し、ステータスとシステムメトリクスを報告し、サーバーや他のデバイスから送られてきたコマンドを実行します。Python + GTK4/libadwaita で構築されており、通信フォーマットを4つ目の言語で再実装する代わりに、`yuki-protocol` 自身の Python 実装をそのまま再利用できます。

## 必要要件

- Python 3.10 以上
- GTK4 と libadwaita（1.4 以上）、およびそれらの GObject-Introspection バインディング - pip ではなくディストリビューションのパッケージからインストールしてください。
  - Debian/Ubuntu: `sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1`
  - Fedora: `sudo dnf install python3-gobject gtk4 libadwaita`
  - Arch: `sudo pacman -S python-gobject gtk4 libadwaita`
- `xdg-utils`（`xdg-open` 用）、音量制御用の `pactl`（PulseAudio/PipeWire）、電源/ロックコマンド用の `systemd`/`logind`（`systemctl`、`loginctl`）- いずれも主要なデスクトップディストリビューションでは標準です。

## 実行

```bash
git clone <このリポジトリを、../yuki-protocol のようなパスが解決できるよう Yuki エコシステムの他のリポジトリと同じ階層に>
cd yuki-device-pc-linux
python3 -m venv --system-site-packages .venv   # GTK4/libadwaita を参照できるよう --system-site-packages を指定
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m yuki_device_pc_linux.main
```

`libs/yuki-protocol/python/` フォルダは、[`yuki-protocol`](../yuki-protocol) の Python 実装を同梱したコピーです（`yuki-core` や `yuki-webui` と同じパターン）- 実行するために隣接する `yuki-protocol` リポジトリをチェックアウトしておく必要はありません。

## 設定

すべてアプリの UI（サーバー接続／拡張ステータス／デバイスへ送信／許可コマンドの各セクション）から設定され、`~/.config/yuki-device-pc-linux/settings.json`（パーミッション600）に保存されます。サーバーアドレス、デバイス ID、認証トークン、有効な許可コマンド（デフォルトでは `shutdown`/`restart`/`sleep` を除く14個すべて）、サブステータス、ウィンドウサイズ。ログは `~/.local/share/yuki-device-pc-linux/logs/` に、実行ごとに1ファイルずつ出力されます。

`yuki-core` 側で TLS が有効になっている場合は、アドレス欄に `wss://host:port` を入力すれば暗号化接続になります - 他に設定は必要ありません。

## コマンド

Windows クライアントと同じ14個の許可コマンドを、Linux の等価な仕組みにマッピングしています。ブラウザ/URL/フォルダ関連のコマンドには `xdg-open`、shutdown/restart/sleep には `systemctl poweroff/reboot/suspend`、ロックには `loginctl lock-session`（失敗時は `xdg-screensaver lock` にフォールバック）、音量には `pactl`、`open_notepad`/`open_calculator` にはシステム上で最初に見つかった GUI テキストエディタ/電卓を使用します。`open_browser`/`open_url` は `http`/`https` の URL のみ受け付けます。

## 自動起動

`packaging/yuki-device-pc-linux` を `~/.local/bin/` にコピーし、中の `REPO_DIR` プレースホルダをあなたのチェックアウト先を指すように編集した上で、`chmod +x` してください。その後、以下のいずれかを行います。

- **デスクトップランチャー**: `packaging/yuki-device-pc-linux.desktop` を `~/.local/share/applications/` にコピーします。
- **ログイン時の自動起動（systemd ユーザーサービス）**: `packaging/yuki-device-pc-linux.service` を `~/.config/systemd/user/` にコピーし、`systemctl --user enable --now yuki-device-pc-linux.service` を実行します。

## トラブルシューティング

**`ModuleNotFoundError: No module named 'gi'`** - venv が `--system-site-packages` なしで作成され、
システムの PyGObject/GTK4/libadwaita を参照できていません。対処法:

```bash
rm -rf .venv
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

（隔離された venv 内で `pip install PyGObject` を実行しても解決しません - ビルドには
`libgirepository` などシステムの開発用パッケージが必要な上、実際にインストール済みの
GTK4/libadwaita とは無関係な、別のバインディングのコピーができてしまうだけです。）

## Windows クライアントとの設計上の違い

- ウィンドウを閉じると終了ではなく非表示になります（バックグラウンドの接続と asyncio ループは動作し続けます）。GTK4 がエコシステム全体でトレイのビルトインサポートを廃止したため、システムトレイアイコンはありません - アプリを再度起動してウィンドウを再表示させる（シングルインスタンスの `Gio.Application` なので、2回目の起動は既存のウィンドウを再表示するだけです）か、上記の自動起動の方法を使用してください。
- 設定は実行ファイルの隣ではなく `~/.config/`（XDG）配下に保存されます。

## プロトコル

Yuki Protocol `yuki/1.0` を使用します - 詳しくは [`yuki-protocol`](../yuki-protocol) を参照してください。
