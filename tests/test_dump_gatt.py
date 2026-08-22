"""GATT dump helper tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.xiaomi_lywsd import collect_gatt_dump
from custom_components.xiaomi_lywsd.device.lywsd02mmc import decode_units
from custom_components.xiaomi_lywsd.device.base import LywsdDeviceError


def test_decode_units_unknown_includes_hex():
    with pytest.raises(LywsdDeviceError, match="hex=00"):
        decode_units(b"\x00")


@pytest.mark.asyncio
async def test_collect_gatt_dump_reads_hex():
    char_read = SimpleNamespace(
        uuid="ebe0ccbe-7a0a-4b0c-8a1a-6ff2997da3a6",
        handle=42,
        properties=["read", "write"],
    )
    char_notify = SimpleNamespace(
        uuid="ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6",
        handle=43,
        properties=["notify"],
    )
    service = SimpleNamespace(
        uuid="ebe0ccb0-7a0a-4b0c-8a1a-6ff2997da3a6",
        handle=40,
        characteristics=[char_read, char_notify],
    )

    class _Client:
        services = [service]

        async def read_gatt_char(self, uuid):
            return b"\xff"

    dump = await collect_gatt_dump(_Client())
    assert dump["services"][0]["characteristics"][0]["value_hex"] == "ff"
    assert "value_hex" not in dump["services"][0]["characteristics"][1]
