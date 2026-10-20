"""Actions through the registered Home Assistant button platform."""

from unittest.mock import patch
from types import SimpleNamespace

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


async def test_press_unreachable_device_records_failure(hass, mock_config_entry):
    """A registered button reports BLE failure and publishes diagnostics."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"auto_sync": "0", "retry_count": 1}
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
            "custom_components.xiaomi_lywsd.establish_connection",
            side_effect=RuntimeError("unreachable"),
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        entries = er.async_entries_for_config_entry(
            er.async_get(hass), mock_config_entry.entry_id
        )
        button = next(entity for entity in entries if entity.domain == "button")
        failure_count = next(
            entity for entity in entries if entity.unique_id.endswith("failure_count")
        )
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "button", "press", {"entity_id": button.entity_id}, blocking=True
            )
        assert hass.states.get(failure_count.entity_id).state == "1"
        assert mock_config_entry.runtime_data.data.last_sync is None
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
