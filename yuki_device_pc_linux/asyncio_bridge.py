from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future


class AsyncioBridge:
    """Runs an asyncio event loop on a background thread so GTK's own main loop stays free."""

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run, name="yuki-asyncio", daemon=True)
        self._thread.start()
        self._ready.wait()

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def run_coroutine(self, coro) -> Future:
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    def stop(self):
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(timeout=2)
