#!/usr/bin/env python3
"""Decode a Xiaomi MiBeacon (service data 0xFE95) frame header.

Mirrors the bit layout used by xiaomi-ble's parser so the output can be compared
against what Home Assistant core actually does with the same bytes.

    python tools/decode_mibeacon.py 305a422500c4c51638c1a408

The question this answers: does this advertisement carry a sensor payload
(``object_include``)? If it never does, the core ``xiaomi_ble`` integration can
never produce temperature/humidity entities for the device, no matter what.
"""

from __future__ import annotations

import sys

DEVICE_TYPES = {
    0x01AA: "LYWSDCGQ",
    0x045B: "LYWSD02",
    0x055B: "LYWSD03MMC",
    0x16E4: "LYWSD02MMC",
    0x2542: "LYWSD02MMC",
    0x2832: "MJWSD05MMC",
    0x55B5: "MJWSD06MMC",
}


def decode(data: bytes) -> dict[str, object]:
    if len(data) < 5:
        raise ValueError(f"frame too short: {len(data)} bytes")

    frctrl = data[0] + (data[1] << 8)
    out: dict[str, object] = {
        "raw": data.hex(),
        "frctrl": f"0x{frctrl:04X}",
        "version": frctrl >> 12,
        "mesh": (frctrl >> 7) & 1,
        "auth_mode": (frctrl >> 10) & 3,
        "solicited": (frctrl >> 9) & 1,
        "registered": (frctrl >> 8) & 1,
        "object_include": (frctrl >> 6) & 1,
        "capability_include": (frctrl >> 5) & 1,
        "mac_include": (frctrl >> 4) & 1,
        "is_encrypted": (frctrl >> 3) & 1,
        "request_timing": frctrl & 1,
    }

    device_id = data[2] + (data[3] << 8)
    out["device_id"] = f"0x{device_id:04X}"
    out["model"] = DEVICE_TYPES.get(device_id, "UNKNOWN")
    out["frame_counter"] = data[4]

    i = 5
    if out["mac_include"]:
        mac = data[5:11][::-1]
        out["mac"] = ":".join(f"{b:02X}" for b in mac)
        i = 11
    if out["capability_include"] and len(data) > i:
        out["capability"] = f"0x{data[i]:02X}"
        i += 1
    out["remaining"] = data[i:].hex() or "(none)"
    return out


def verdict(f: dict[str, object]) -> str:
    if f["mesh"]:
        return "MESH — xiaomi_ble rejects mesh devices outright."
    if f["version"] < 2:
        return "LEGACY — MiBeacon v0/v1 is not supported by xiaomi_ble."
    if not f["object_include"]:
        return (
            "NO SENSOR PAYLOAD — xiaomi_ble logs 'Advertisement doesn't contain "
            "payload' and returns False. No entity can ever be produced from this "
            "frame. Values must be read over GATT."
        )
    if f["is_encrypted"]:
        return "ENCRYPTED PAYLOAD — a bindkey is required to decrypt it."
    return "PLAINTEXT SENSOR PAYLOAD — xiaomi_ble can parse this frame."


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    fields = decode(bytes.fromhex(sys.argv[1].replace(" ", "")))
    width = max(len(k) for k in fields)
    for key, value in fields.items():
        print(f"{key:>{width}} : {value}")
    print()
    print(f"verdict: {verdict(fields)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
