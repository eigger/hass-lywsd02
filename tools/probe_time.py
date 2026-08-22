#!/usr/bin/env python3
"""Probe time characteristic read → write(now) → re-read.

Usage:
  python tools/probe_time.py AA:BB:CC:DD:EE:FF [tz_offset_hours]

Records write-before / written / write-after payloads, response=True/False
success, and read-back drift. Use a negative tz (e.g. -5) to classify int8 vs uint8.

Standalone — imports bleak only.
"""

from __future__ import annotations

import asyncio
import struct
import sys
import time
from datetime import datetime, timezone

from bleak import BleakClient

UUID_TIME = "ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6"


def encode(epoch: int, tz: int) -> bytes:
    return struct.pack("<Ib", epoch, tz)


def decode(payload: bytes) -> tuple[int, int]:
    if len(payload) >= 5:
        return struct.unpack_from("<Ib", payload)
    if len(payload) >= 4:
        (epoch,) = struct.unpack_from("<I", payload)
        return epoch, 0
    raise ValueError(f"short payload: {payload!r}")


async def try_write(client: BleakClient, payload: bytes, response: bool) -> bool:
    try:
        await client.write_gatt_char(UUID_TIME, payload, response=response)
        return True
    except Exception as err:
        print(f"  write response={response} FAILED: {err}")
        return False


async def main(address: str, tz_offset: int) -> None:
    async with BleakClient(address) as client:
        before = await client.read_gatt_char(UUID_TIME)
        print(f"before_hex={before.hex()} decoded={decode(before)}")

        now = datetime.now(timezone.utc)
        epoch = int(now.timestamp())
        payload = encode(epoch, tz_offset)
        print(f"writing epoch={epoch} tz={tz_offset} payload={payload.hex()}")

        ok_true = await try_write(client, payload, True)
        print(f"response=True success={ok_true}")
        if not ok_true:
            ok_false = await try_write(client, payload, False)
            print(f"response=False success={ok_false}")

        time.sleep(0.5)
        after = await client.read_gatt_char(UUID_TIME)
        after_epoch, after_tz = decode(after)
        print(f"after_hex={after.hex()} decoded=({after_epoch}, {after_tz})")
        print(f"delta_seconds={after_epoch - epoch}")
        print(f"tz_read_back={after_tz} (wrote {tz_offset})")
        if tz_offset < 0 and after_tz != tz_offset:
            print(
                "NOTE: negative tz did not round-trip as signed; "
                "check uint8 wrap (e.g. 251 for -5)."
            )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            f"Usage: {sys.argv[0]} AA:BB:CC:DD:EE:FF [tz_offset]",
            file=sys.stderr,
        )
        sys.exit(2)
    tz = int(sys.argv[2]) if len(sys.argv) > 2 else 9
    asyncio.run(main(sys.argv[1].upper(), tz))
