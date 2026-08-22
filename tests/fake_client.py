"""Fake BleakClient that records writes and can emit notifies."""

from __future__ import annotations

import asyncio
from collections.abc import Callable


class FakeBleakClient:
    """write된 (uuid, bytes, response) 를 기록하고, 미리 세팅된 read/notify 값을 돌려준다."""

    def __init__(
        self,
        initial: dict[str, bytes],
        *,
        reject: set[str] | None = None,
        notify: dict[str, bytes] | None = None,
        notify_delay: float = 0.0,
        notify_timeout: bool = False,
    ) -> None:
        self._store = {k.lower(): bytes(v) for k, v in initial.items()}
        self.reject = {u.lower() for u in (reject or set())}
        self._notify_payloads = {
            k.lower(): bytes(v) for k, v in (notify or {}).items()
        }
        self.notify_delay = notify_delay
        self.notify_timeout = notify_timeout
        self.writes: list[tuple[str, bytes, bool]] = []
        self.notify_starts: list[str] = []
        self.notify_stops: list[str] = []
        self.is_connected = True
        self._handlers: dict[str, Callable] = {}

    async def read_gatt_char(self, uuid) -> bytes:
        key = str(uuid).lower()
        if key not in self._store:
            raise KeyError(f"no value for {uuid}")
        return self._store[key]

    async def write_gatt_char(self, uuid, data, response: bool = False) -> None:
        key = str(uuid).lower()
        payload = bytes(data)
        self.writes.append((key, payload, response))
        if key not in self.reject:
            self._store[key] = payload

    async def start_notify(self, uuid, callback) -> None:
        key = str(uuid).lower()
        self.notify_starts.append(key)
        self._handlers[key] = callback
        if self.notify_timeout:
            return
        if key in self._notify_payloads:

            async def _emit() -> None:
                if self.notify_delay:
                    await asyncio.sleep(self.notify_delay)
                handler = self._handlers.get(key)
                if handler is not None:
                    handler(key, bytearray(self._notify_payloads[key]))

            asyncio.create_task(_emit())

    async def stop_notify(self, uuid) -> None:
        key = str(uuid).lower()
        self.notify_stops.append(key)
        self._handlers.pop(key, None)

    async def disconnect(self) -> None:
        self.is_connected = False
