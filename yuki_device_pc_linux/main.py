from __future__ import annotations

import sys

from .app import YukiApplication


def main():
    app = YukiApplication()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
