#!/usr/bin/env python3
"""Dump full GATT service/characteristic tree for a LYWSD02(MMC).

Usage:
  python tools/dump_gatt.py AA:BB:CC:DD:EE:FF

Standalone — imports bleak only. Does not import custom_components/.
Requires a local BLE adapter that can reach the device. If the device is only
reachable via an ESPHome Bluetooth proxy, use the Home Assistant service
``xiaomi_lywsd.dump_gatt`` instead (Developer Tools → Services).
"""

from __future__ import annotations

import asyncio
import sys

from bleak import BleakClient


async def main(address: str) -> None:
    async with BleakClient(address) as client:
        print(f"# GATT dump for {address}")
        print(f"# connected={client.is_connected}")
        for service in client.services:
            print(f"\nService {service.uuid} handle={service.handle}")
            if service.description:
                print(f"  description: {service.description}")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(
                    f"  Characteristic {char.uuid} handle={char.handle} "
                    f"properties=[{props}]"
                )
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        print(f"    value_hex={value.hex()} raw={value!r}")
                    except Exception as err:
                        print(f"    read_error={err}")
                for desc in char.descriptors:
                    print(f"    Descriptor {desc.uuid} handle={desc.handle}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} AA:BB:CC:DD:EE:FF", file=sys.stderr)
        sys.exit(2)
    asyncio.run(main(sys.argv[1].upper()))
