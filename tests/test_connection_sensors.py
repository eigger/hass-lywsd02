"""BLE connectivity / connection duration sensors (gicisky pattern)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.xiaomi_lywsd.binary_sensor import LywsdConnectivityBinarySensor
from custom_components.xiaomi_lywsd.coordinator import LywsdCoordinator
from custom_components.xiaomi_lywsd.device import Lywsd02mmc
from custom_components.xiaomi_lywsd.sensor import LywsdConnectionDurationSensor


def _coord():
    hass = MagicMock()
    hass.data = {"xiaomi_lywsd": {"lock": asyncio.Lock()}}
    entry = MagicMock()
    entry.entry_id = "e1"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    entry.options = {"scan_interval": 1800, "retry_count": 1}
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    coord = LywsdCoordinator(
        hass,
        entry,
        "AA:BB:CC:DD:EE:FF",
        hass.data["xiaomi_lywsd"]["lock"],
        Lywsd02mmc(),
    )
    entry.runtime_data = coord
    return hass, entry, coord


def test_begin_end_connection_updates_coordinators():
    hass, entry, coord = _coord()
    assert coord.connectivity.data is False
    assert coord.connection_duration.data == 0.0

    coord.begin_connection()
    assert coord.connectivity.data is True
    assert coord.connection_duration.data == 0.0

    coord._session_start = coord._session_start - 1.5  # type: ignore[operator]
    coord.end_connection()
    assert coord.connectivity.data is False
    assert coord.connection_duration.data == 1.5


def test_connectivity_and_duration_entities():
    hass, entry, coord = _coord()
    binary = LywsdConnectivityBinarySensor(coord)
    duration = LywsdConnectionDurationSensor(coord)
    assert binary.available is True
    assert duration.available is True
    assert binary.is_on is False
    assert duration.native_value == 0.0

    coord.begin_connection()
    # Simulate HA listener dispatch from connectivity / duration coordinators.
    binary._handle_coordinator_update()
    duration._handle_coordinator_update()
    assert binary.coordinator is coord.connectivity
    assert binary.is_on is True
    assert duration.native_value == 0.0


@pytest.mark.asyncio
async def test_async_execute_toggles_connectivity():
    from custom_components.xiaomi_lywsd import async_execute

    hass, entry, coord = _coord()
    ble = MagicMock()
    ble.address = coord.address
    client = MagicMock()
    client.is_connected = True
    client.disconnect = AsyncMock()

    async def op(client, device):
        assert coord.connectivity.data is True
        return "ok"

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
        result = await async_execute(hass, entry, op)

    assert result == "ok"
    assert coord.connectivity.data is False
    assert coord.connection_duration.data >= 0.0
