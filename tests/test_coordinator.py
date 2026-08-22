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
