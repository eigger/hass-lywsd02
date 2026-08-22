"""Entity / async_execute behaviour tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.xiaomi_lywsd import async_execute
from custom_components.xiaomi_lywsd.button import LywsdSyncTimeButton
from custom_components.xiaomi_lywsd.coordinator import LywsdCoordinator
from custom_components.xiaomi_lywsd.device.base import LywsdVerifyError
from custom_components.xiaomi_lywsd.select import LywsdDisplayUnitsSelect
from custom_components.xiaomi_lywsd.sensor import (
    CLIMATE_SENSORS,
    DIAGNOSTIC_SENSORS,
    LywsdSensor,
)
from homeassistant.exceptions import HomeAssistantError


def _entry(address="AA:BB:CC:DD:EE:FF"):
    entry = MagicMock()
    entry.entry_id = "entry1"
    entry.data = {"address": address}
    entry.options = {"retry_count": 3, "scan_interval": 600}
    entry.unique_id = address
    lock = asyncio.Lock()
    hass = MagicMock()
    hass.data = {"xiaomi_lywsd": {"lock": lock}}
    from custom_components.xiaomi_lywsd.device import Lywsd02mmc

    coordinator = LywsdCoordinator(hass, entry, address, lock, Lywsd02mmc())
    entry.runtime_data = coordinator
    return hass, entry


@pytest.mark.asyncio
async def test_async_execute_raises_when_device_missing():
    hass, entry = _entry()
    with patch(
        "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
        return_value=None,
    ):
        with pytest.raises(HomeAssistantError, match="찾을 수 없습니다"):
            await async_execute(hass, entry, AsyncMock())


@pytest.mark.asyncio
async def test_async_execute_does_not_touch_failure_count():
    """async_execute must not mutate coordinator bookkeeping."""
    hass, entry = _entry()
    ble = MagicMock()
    ble.address = entry.runtime_data.address
    before = entry.runtime_data.data.failure_count

    async def boom(client, device):
        raise RuntimeError("fail")

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
            side_effect=RuntimeError("connect fail"),
        ),
        patch("custom_components.xiaomi_lywsd.asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(HomeAssistantError):
            await async_execute(hass, entry, boom)

    assert entry.runtime_data.data.failure_count == before


@pytest.mark.asyncio
async def test_lock_serializes_calls():
    hass, entry = _entry()
    order: list[str] = []
    ble = MagicMock()
    ble.address = entry.runtime_data.address
    client = MagicMock()
    client.is_connected = True
    client.disconnect = AsyncMock()

    async def slow(client, device):
        order.append("start")
        await asyncio.sleep(0.05)
        order.append("end")
        return True

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
        await asyncio.gather(
            async_execute(hass, entry, slow),
            async_execute(hass, entry, slow),
        )
    assert order == ["start", "end", "start", "end"]


@pytest.mark.asyncio
async def test_verify_error_is_not_retried():
    """LywsdVerifyError must not burn retry budget (no repeated GATT writes)."""
    hass, entry = _entry()
    ble = MagicMock()
    ble.address = entry.runtime_data.address
    client = MagicMock()
    client.is_connected = True
    client.disconnect = AsyncMock()
    calls = {"n": 0}

    async def boom(client, device):
        calls["n"] += 1
        raise LywsdVerifyError("mismatch")

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
        patch("custom_components.xiaomi_lywsd.asyncio.sleep", new_callable=AsyncMock) as sleep,
    ):
        with pytest.raises(LywsdVerifyError):
            await async_execute(hass, entry, boom)

    assert calls["n"] == 1
    sleep.assert_not_called()


@pytest.mark.asyncio
async def test_button_press_maps_verify_error():
    hass, entry = _entry()
    button = LywsdSyncTimeButton(hass, entry)

    with patch(
        "custom_components.xiaomi_lywsd.button.async_execute",
        new_callable=AsyncMock,
        side_effect=LywsdVerifyError("nope"),
    ), patch(
        "custom_components.xiaomi_lywsd.button.dt_util.now",
        return_value=datetime.now(timezone.utc),
    ):
        with pytest.raises(HomeAssistantError, match="확인하지 못했습니다"):
            await button.async_press()


@pytest.mark.asyncio
async def test_button_failure_does_not_mark_update_success():
    """Failed press must not call async_set_updated_data (would revive sensors)."""
    hass, entry = _entry()
    button = LywsdSyncTimeButton(hass, entry)
    coord = entry.runtime_data
    coord.last_update_success = False
    before_sets = coord._set_updated_calls

    with patch(
        "custom_components.xiaomi_lywsd.button.async_execute",
        new_callable=AsyncMock,
        side_effect=LywsdVerifyError("nope"),
    ), patch(
        "custom_components.xiaomi_lywsd.button.dt_util.now",
        return_value=datetime.now(timezone.utc),
    ):
        with pytest.raises(HomeAssistantError):
            await button.async_press()

    assert coord.last_update_success is False
    assert coord._set_updated_calls == before_sets
    assert coord._listener_calls == 1
    assert coord.data.failure_count == 1


@pytest.mark.asyncio
async def test_button_success_does_not_mark_update_success():
    """Successful sync must notify listeners without pretending climate polled."""
    hass, entry = _entry()
    button = LywsdSyncTimeButton(hass, entry)
    coord = entry.runtime_data
    coord.last_update_success = False
    coord.data.temperature = 21.5
    before_sets = coord._set_updated_calls

    async def fake_execute(hass, entry, op, **kwargs):
        entry.runtime_data.data.last_sync = datetime.now(timezone.utc)
        entry.runtime_data.data.last_drift_seconds = 0.0
        return MagicMock(drift_seconds=0.0)

    with patch(
        "custom_components.xiaomi_lywsd.button.async_execute",
        new=fake_execute,
    ), patch(
        "custom_components.xiaomi_lywsd.button.dt_util.now",
        return_value=datetime.now(timezone.utc),
    ):
        await button.async_press()

    assert coord.last_update_success is False
    assert coord._set_updated_calls == before_sets
    assert coord._listener_calls == 1
    assert coord.data.last_sync is not None
    assert coord.data.temperature == 21.5


@pytest.mark.asyncio
async def test_select_keeps_previous_on_failure():
    hass, entry = _entry()
    entry.runtime_data.data.units = "celsius"
    select = LywsdDisplayUnitsSelect(hass, entry)
    select.async_write_ha_state = MagicMock()
    coord = entry.runtime_data
    coord.last_update_success = False
    before_sets = coord._set_updated_calls

    with patch(
        "custom_components.xiaomi_lywsd.select.async_execute",
        new_callable=AsyncMock,
        side_effect=LywsdVerifyError("nope"),
    ):
        with pytest.raises(HomeAssistantError):
            await select.async_select_option("fahrenheit")

    assert entry.runtime_data.data.units == "celsius"
    assert coord.last_update_success is False
    assert coord._set_updated_calls == before_sets
    assert coord._listener_calls == 1


def test_diagnostic_sensors_available_when_poll_failed():
    """Action diagnostics must stay available after a climate poll failure."""
    hass, entry = _entry()
    coord = entry.runtime_data
    coord.last_update_success = False
    coord.data.temperature = 21.5
    coord.data.last_sync = datetime.now(timezone.utc)
    coord.data.failure_count = 2
    coord.data.last_failure = datetime.now(timezone.utc)

    temp = LywsdSensor(coord, CLIMATE_SENSORS[0])
    last_sync = LywsdSensor(coord, DIAGNOSTIC_SENSORS[0])
    failure_count = LywsdSensor(
        coord, next(d for d in DIAGNOSTIC_SENSORS if d.key == "failure_count")
    )
    last_failure = LywsdSensor(
        coord, next(d for d in DIAGNOSTIC_SENSORS if d.key == "last_failure")
    )

    assert temp.available is False
    assert last_sync.available is True
    assert last_sync.native_value == coord.data.last_sync
    assert failure_count.available is True
    assert failure_count.native_value == 2
    assert last_failure.available is True
    assert last_failure.native_value == coord.data.last_failure
