"""Real sensor platform state and availability regression tests."""

from unittest.mock import patch
from types import SimpleNamespace
from homeassistant.helpers import entity_registry as er
from .fake_client import FakeBleakClient
from custom_components.xiaomi_lywsd.device.lywsd02mmc import UUID_BATTERY, UUID_DATA


async def test_climate_poll_state_and_recovery(hass, mock_config_entry):
    """BLE failures affect loaded climate states and a new poll recovers them."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"auto_sync": "0", "climate_sensors": True}
    )
    client = FakeBleakClient(
        {UUID_BATTERY: b"\x64"}, notify={UUID_DATA: b"\x1a\x09\x37"}
    )
    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=SimpleNamespace(address="AA:BB:CC:DD:EE:FF"),
        ),
        patch("custom_components.xiaomi_lywsd.close_stale_connections_by_address"),
        patch(
            "custom_components.xiaomi_lywsd.establish_connection", return_value=client
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        entries = er.async_entries_for_config_entry(
            er.async_get(hass), mock_config_entry.entry_id
        )
        temperature = next(
            entity for entity in entries if entity.unique_id.endswith("temperature")
        )
        assert float(hass.states.get(temperature.entity_id).state) == 23.3
        coordinator = mock_config_entry.runtime_data
        with patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=None,
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()
            assert hass.states.get(temperature.entity_id).state == "unavailable"
        await coordinator.async_refresh()
        await hass.async_block_till_done()
        assert float(hass.states.get(temperature.entity_id).state) == 23.3
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
