#!/usr/bin/env python3
"""Probe climate notify on EBE0CCC1.

Usage:
  python tools/probe_climate.py AA:BB:CC:DD:EE:FF [timeout_seconds]

Records first-notify latency, optional plain read, and decodes ``<hB``.
Standalone — imports bleak only.
"""

from __future__ import annotations

import asyncio
import struct
import sys
import time

from bleak import BleakClient

UUID_DATA = "ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6"


def decode(payload: bytes) -> tuple[float, int]:
    raw_temp, humidity = struct.unpack_from("<hB", payload)
    return raw_temp / 100.0, int(humidity)


async def main(address: str, timeout: float) -> None:
    async with BleakClient(address) as client:
        print(f"# climate probe {address}")
        try:
            plain = await client.read_gatt_char(UUID_DATA)
            print(f"plain_read hex={plain.hex()} decoded={decode(plain)}")
        except Exception as err:
            print(f"plain_read failed: {err}")

        event = asyncio.Event()
        holder: dict[str, bytes] = {}
        t0 = time.monotonic()

        def _handler(_sender, data: bytearray) -> None:
            if "payload" not in holder:
                holder["payload"] = bytes(data)
                event.set()

        await client.start_notify(UUID_DATA, _handler)
        try:
            await asyncio.wait_for(event.wait(), timeout)
            latency = time.monotonic() - t0
            payload = holder["payload"]
            print(f"first_notify_s={latency:.3f} hex={payload.hex()} "
                  f"decoded={decode(payload)}")
        except TimeoutError:
            print(f"TIMEOUT after {timeout}s — no notify")
        finally:
            await client.stop_notify(UUID_DATA)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} AA:BB:CC:DD:EE:FF [timeout]",
            file=sys.stderr,
        )
        sys.exit(2)
    to = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    asyncio.run(main(sys.argv[1].upper(), to))
