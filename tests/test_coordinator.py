"""Coordinator poll-cycle tests."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.xiaomi_lywsd.coordinator import LywsdCoordinator, LywsdData
from custom_components.xiaomi_lywsd.device import Lywsd02mmc
from custom_components.xiaomi_lywsd.device.base import ClimateReading
from custom_components.xiaomi_lywsd.device.lywsd02mmc import UUID_BATTERY, UUID_DATA
from tests.fake_client import FakeBleakClient


def _coord(hass=None, entry=None):
    hass = hass or MagicMock()
    hass.data = {"xiaomi_lywsd": {"lock": asyncio.Lock()}}
    entry = entry or MagicMock()
    entry.entry_id = "e1"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    entry.options = {"scan_interval": 600, "retry_count": 2}
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    entry.runtime_data = None
    coord = LywsdCoordinator(
        hass,
        entry,
        "AA:BB:CC:DD:EE:FF",
        hass.data["xiaomi_lywsd"]["lock"],
        Lywsd02mmc(),
    )
    entry.runtime_data = coord
    return hass, entry, coord


@pytest.mark.asyncio
async def test_poll_cycle_order_notify_battery_disconnect():
    hass, entry, coord = _coord()
    client = FakeBleakClient(
        {UUID_BATTERY: b"\x64"},
        notify={UUID_DATA: b"\x1a\x09\x37"},
    )
    client.disconnect = AsyncMock(wraps=client.disconnect)
    ble = MagicMock()
    ble.address = "AA:BB:CC:DD:EE:FF"

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=ble,
        ),
        patch(
            "custom_components.xiaomi_lywsd.close_stale_connections_by_address",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.xiaomi_lywsd.establish_connection",
            new_callable=AsyncMock,
            return_value=client,
        ),
    ):
        data = await coord._async_update_data()

    assert data.temperature == pytest.approx(23.30)
    assert data.humidity == 55
    assert data.battery == 100
    assert UUID_DATA in client.notify_starts
    assert UUID_DATA in client.notify_stops
    client.disconnect.assert_awaited()


@pytest.mark.asyncio
async def test_poll_timeout_raises_update_failed_and_disconnects():
    hass, entry, coord = _coord()
    client = FakeBleakClient({}, notify_timeout=True)
    client.disconnect = AsyncMock(wraps=client.disconnect)
    ble = MagicMock()
    ble.address = "AA:BB:CC:DD:EE:FF"

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=ble,
        ),
        patch(
            "custom_components.xiaomi_lywsd.close_stale_connections_by_address",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.xiaomi_lywsd.establish_connection",
            new_callable=AsyncMock,
            return_value=client,
        ),
        patch("custom_components.xiaomi_lywsd.asyncio.sleep", new_callable=AsyncMock),
        patch(
            "custom_components.xiaomi_lywsd.coordinator.DEFAULT_CLIMATE_TIMEOUT",
            0.05,
        ),
    ):
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    client.disconnect.assert_awaited()
    assert coord.data.failure_count == 1


@pytest.mark.asyncio
async def test_poll_failure_increments_failure_count_once():
    hass, entry, coord = _coord()
    assert coord.data.failure_count == 0

    async def boom(*args, **kwargs):
        raise RuntimeError("fail")

    with patch(
        "custom_components.xiaomi_lywsd.async_execute",
        new=boom,
    ):
        with pytest.raises(UpdateFailed):
            await coord._async_update_data()

    assert coord.data.failure_count == 1


@pytest.mark.asyncio
async def test_partial_failure_preserves_previous_battery():
    hass, entry, coord = _coord()
    coord.data = LywsdData(battery=77, temperature=20.0, humidity=40)

    async def _op(client, device):
        return ClimateReading(21.5, 41), None, None

    with patch(
        "custom_components.xiaomi_lywsd.async_execute",
        new_callable=AsyncMock,
        side_effect=lambda *a, **k: _op(None, None),
    ):
        # Bypass real execute — feed partial battery None
        async def fake_execute(hass, entry, op, wrap_errors=False):
            return ClimateReading(21.5, 41), None, "celsius"

        with patch(
            "custom_components.xiaomi_lywsd.async_execute",
            new=fake_execute,
        ):
            data = await coord._async_update_data()

    assert data.temperature == 21.5
    assert data.battery == 77  # preserved
    assert data.units == "celsius"


def test_climate_sensors_off_disables_polling():
    hass = MagicMock()
    hass.data = {"xiaomi_lywsd": {"lock": asyncio.Lock()}}
    entry = MagicMock()
    entry.entry_id = "e1"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    entry.options = {"climate_sensors": False, "scan_interval": 600}
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    coord = LywsdCoordinator(
        hass,
        entry,
        "AA:BB:CC:DD:EE:FF",
        hass.data["xiaomi_lywsd"]["lock"],
        Lywsd02mmc(),
    )
    assert coord.update_interval is None


def test_default_scan_interval_is_30_minutes():
    from custom_components.xiaomi_lywsd.const import (
        DEFAULT_AUTO_SYNC_HOURS,
        DEFAULT_CLIMATE_SENSORS,
        DEFAULT_SCAN_INTERVAL,
        scan_interval_seconds,
    )

    hass, entry, _coord_unused = _coord()
    entry.options = {"climate_sensors": True}
    coord2 = LywsdCoordinator(
        hass,
        entry,
        "AA:BB:CC:DD:EE:FF",
        hass.data["xiaomi_lywsd"]["lock"],
        Lywsd02mmc(),
    )
    assert DEFAULT_AUTO_SYNC_HOURS == 0
    assert DEFAULT_CLIMATE_SENSORS is False
    assert DEFAULT_SCAN_INTERVAL == 30
    assert scan_interval_seconds(30) == 1800
    assert scan_interval_seconds(1800) == 1800  # legacy seconds
    assert coord2.update_interval.total_seconds() == 1800


def test_default_options_disable_climate_polling():
    hass, entry, coord = _coord()
    entry.options = {}
    coord_default = LywsdCoordinator(
        hass,
        entry,
        "AA:BB:CC:DD:EE:FF",
        hass.data["xiaomi_lywsd"]["lock"],
        Lywsd02mmc(),
    )
    assert coord_default.update_interval is None


@pytest.mark.asyncio
async def test_unknown_units_warns_once_with_hex(caplog):
    import logging

    from custom_components.xiaomi_lywsd.device.base import ClimateReading

    hass, entry, coord = _coord()
    caplog.set_level(logging.WARNING)

    async def fake_execute(hass, entry, op, wrap_errors=False):
        # Invoke op with a client whose get_units path fails via device
        client = MagicMock()
        device = MagicMock()
        device.read_climate = AsyncMock(
            return_value=ClimateReading(20.0, 40)
        )
        device.get_battery = AsyncMock(return_value=80)
        device.get_units = AsyncMock(
            side_effect=Exception("unknown units payload hex=00 raw=b'\\x00'")
        )
        return await op(client, device)

    with patch(
        "custom_components.xiaomi_lywsd.async_execute",
        new=fake_execute,
    ):
        data1 = await coord._async_update_data()
        data2 = await coord._async_update_data()

    assert data1.units is None
    assert data2.units is None
    warnings = [r for r in caplog.records if "units read skipped" in r.message]
    assert len(warnings) == 1
    assert "hex=00" in warnings[0].message
