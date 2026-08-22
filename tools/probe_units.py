#!/usr/bin/env python3
"""Probe display-units characteristic.

Always: read original → write opposite → wait for operator confirmation → restore.

Usage:
  python tools/probe_units.py AA:BB:CC:DD:EE:FF

Standalone — imports bleak only. Do NOT skip the restore step.
"""

from __future__ import annotations

import asyncio
import sys

from bleak import BleakClient

UUID_UNITS = "ebe0ccbe-7a0a-4b0c-8a1a-6ff2997da3a6"

# Community candidates — probe both families. Operator confirms on E-Ink.
# Measured stock read on LYWSD02MMC: 0x00 = °C. °F write still needs screen check.
CANDIDATES = {
    "celsius_00": b"\x00",
    "fahrenheit_01": b"\x01",
    "celsius_ff_legacy": b"\xff",
}


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        original = await client.read_gatt_char(UUID_UNITS)
        print(f"ORIGINAL hex={original.hex()} raw={original!r}")
        print("Mappings:")
        print("  measured: 0x00=C (LYWSD02MMC stock read)")
        print("  write candidate °F: 0x01 (unverified on screen)")
        print("  legacy h4 write °C: 0xFF (decode-compatible only)")
        print()

        try:
            opposite = b"\x01" if original[:1] != b"\x01" else b"\x00"
            print(f"Writing opposite candidate {opposite.hex()} (response=True)…")
            await client.write_gatt_char(UUID_UNITS, opposite, response=True)
            after = await client.read_gatt_char(UUID_UNITS)
            print(f"read-back hex={after.hex()}")
            print(
                "Look at the E-Ink screen. Did °C / °F change? "
                "Record which unit is shown now, then press Enter to restore."
            )
            await asyncio.get_event_loop().run_in_executor(None, input)
        finally:
            print(f"Restoring original {original.hex()}…")
            await client.write_gatt_char(UUID_UNITS, original, response=True)
            restored = await client.read_gatt_char(UUID_UNITS)
            print(f"restored hex={restored.hex()}")
            if restored[:1] != original[:1]:
                print("WARNING: restore read-back mismatch — check device manually.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} AA:BB:CC:DD:EE:FF", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1].upper()))
