"""12h / 24h clock mode: payload, clock repair, and unsupported firmware."""

from __future__ import annotations

import asyncio
import datetime as dt
import struct
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.xiaomi_lywsd.coordinator import LywsdCoordinator
from custom_components.xiaomi_lywsd.device import (
    Lywsd02mmc,
    LywsdClockRepairError,
    LywsdUnsupportedError,
)
from custom_components.xiaomi_lywsd.device.lywsd02mmc import (
    UUID_TIME,
    encode_time,
    encode_time_format,
)
from custom_components.xiaomi_lywsd.select import LywsdTimeFormatSelect
from homeassistant.exceptions import HomeAssistantError
from tests.fake_client import FakeBleakClient

UTC = dt.timezone.utc
WHEN = dt.datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


def test_mode_payloads_are_seven_bytes():
    """Length is what tells the device a mode command from a time write."""
    assert encode_time_format("24h") == struct.pack("<IHB", 0, 0, 0x00)
    assert encode_time_format("12h") == struct.pack("<IHB", 0, 0, 0xAA)
    assert len(encode_time_format("12h")) == 7
    assert len(encode_time(0, 0)) == 5


def test_unknown_format_rejected():
    with pytest.raises(ValueError):
        encode_time_format("13h")


@pytest.mark.asyncio
async def test_mode_write_is_followed_by_a_clock_write():
    """A firmware that reads the mode command as a time write must not be
    left showing 1970 — the clock is rewritten on the same connection."""
    device = Lywsd02mmc()
    epoch = int(WHEN.timestamp())
    client = FakeBleakClient({UUID_TIME: encode_time(epoch, 9)})

    result = await device.set_time_format(client, "12h", WHEN, 9)

    writes = [w for w in client.writes if w[0] == UUID_TIME.lower()]
    assert len(writes) == 2
    assert writes[0][1] == encode_time_format("12h")
    assert len(writes[1][1]) == 5  # the repair write
    assert result.written_epoch == epoch


@pytest.mark.asyncio
async def test_rejected_mode_write_raises_unsupported():
    device = Lywsd02mmc()
    client = FakeBleakClient({UUID_TIME: encode_time(0, 0)})

    async def refuse(uuid, data, response=False):
        raise RuntimeError("write not permitted")

    client.write_gatt_char = refuse

    with pytest.raises(LywsdUnsupportedError):
        await device.set_time_format(client, "24h", WHEN, 9)


def _entry():
    address = "AA:BB:CC:DD:EE:FF"
    entry = MagicMock()
    entry.entry_id = "entry-fmt"
    entry.data = {"address": address}
    entry.options = {"retry_count": 3, "scan_interval": 30}
    hass = MagicMock()
    lock = asyncio.Lock()
    hass.data = {"xiaomi_lywsd": {"lock": lock}}
    coordinator = LywsdCoordinator(hass, entry, address, lock, Lywsd02mmc())
    entry.runtime_data = coordinator
    return hass, entry


@pytest.mark.asyncio
async def test_select_reverts_and_explains_on_unsupported_device():
    hass, entry = _entry()
    coordinator = entry.runtime_data
    coordinator.data.time_format = "24h"
    select = LywsdTimeFormatSelect(hass, entry)

    with patch(
        "custom_components.xiaomi_lywsd.select.async_execute",
        new_callable=AsyncMock,
        side_effect=LywsdUnsupportedError("nope"),
    ):
        with pytest.raises(HomeAssistantError, match="거부했습니다"):
            await select.async_select_option("12h")

    assert coordinator.data.time_format == "24h"


@pytest.mark.asyncio
async def test_select_persists_choice_on_success():
    hass, entry = _entry()
    coordinator = entry.runtime_data

    async def fake_execute(hass_, entry_, op, **kwargs):
        coordinator.data.time_format = "12h"
        coordinator.note_sync(0.0, dt.datetime.now(UTC))
        return "12h"

    select = LywsdTimeFormatSelect(hass, entry)
    with patch(
        "custom_components.xiaomi_lywsd.select.async_execute", new=fake_execute
    ):
        await select.async_select_option("12h")

    assert select.current_option == "12h"
    reloaded = await coordinator.store.async_load()
    assert reloaded["time_format"] == "12h"


@pytest.mark.asyncio
async def test_dropped_link_is_not_reported_as_unsupported():
    """A disconnect mid-write says nothing about what the firmware implements."""
    device = Lywsd02mmc()
    client = FakeBleakClient({UUID_TIME: encode_time(0, 0)})

    async def drop(uuid, data, response=False):
        client.is_connected = False
        raise RuntimeError("connection lost")

    client.write_gatt_char = drop

    with pytest.raises(RuntimeError, match="connection lost"):
        await device.set_time_format(client, "24h", WHEN, 9)


@pytest.mark.asyncio
async def test_failed_clock_repair_is_its_own_error():
    """Mode landed, clock write did not — the display may read 1970."""
    device = Lywsd02mmc()
    epoch = int(WHEN.timestamp())
    client = FakeBleakClient({UUID_TIME: encode_time(epoch, 9)})
    calls = {"n": 0}
    real_write = client.write_gatt_char

    async def fail_second(uuid, data, response=False):
        calls["n"] += 1
        if calls["n"] == 1:
            return await real_write(uuid, data, response=response)
        raise RuntimeError("write failed")

    client.write_gatt_char = fail_second

    with pytest.raises(LywsdClockRepairError):
        await device.set_time_format(client, "12h", WHEN, 9)


@pytest.mark.asyncio
async def test_select_keeps_option_when_only_the_clock_repair_failed():
    hass, entry = _entry()
    coordinator = entry.runtime_data
    coordinator.data.time_format = "24h"
    select = LywsdTimeFormatSelect(hass, entry)

    async def fake_execute(hass_, entry_, op, **kwargs):
        coordinator.data.time_format = "12h"
        raise LywsdClockRepairError("boom")

    with patch(
        "custom_components.xiaomi_lywsd.select.async_execute", new=fake_execute
    ):
        with pytest.raises(HomeAssistantError, match="시계 복구에 실패"):
            await select.async_select_option("12h")

    # Not rolled back: the mode almost certainly did change.
    assert coordinator.data.time_format == "12h"


@pytest.mark.asyncio
async def test_timeout_is_not_reported_as_unsupported():
    """A slow link is not a firmware verdict either."""
    device = Lywsd02mmc()
    client = FakeBleakClient({UUID_TIME: encode_time(0, 0)})

    async def stall(uuid, data, response=False):
        raise TimeoutError("no response")

    client.write_gatt_char = stall

    with pytest.raises(TimeoutError):
        await device.set_time_format(client, "24h", WHEN, 9)


@pytest.mark.asyncio
async def test_battery_is_read_on_a_sync_connection():
    """Clock-only installs never poll, so the sync is the only chance."""
    from custom_components.xiaomi_lywsd import async_read_battery_into
    from custom_components.xiaomi_lywsd.device.lywsd02mmc import UUID_BATTERY

    _hass, entry = _entry()
    coordinator = entry.runtime_data
    client = FakeBleakClient({UUID_BATTERY: bytes([77])})

    await async_read_battery_into(client, Lywsd02mmc(), coordinator)
    assert coordinator.data.battery == 77


@pytest.mark.asyncio
async def test_unreadable_battery_never_breaks_a_sync():
    from custom_components.xiaomi_lywsd import async_read_battery_into

    _hass, entry = _entry()
    coordinator = entry.runtime_data
    coordinator.data.battery = 55
    client = FakeBleakClient({})  # no battery characteristic at all

    await async_read_battery_into(client, Lywsd02mmc(), coordinator)
    assert coordinator.data.battery == 55  # previous value kept
