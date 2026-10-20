"""Actions through the registered Home Assistant select platform."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


async def test_select_failed_connection_retains_option(hass, mock_config_entry):
    """A transport failure leaves a previously confirmed display unit intact."""
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
        coordinator = mock_config_entry.runtime_data
        coordinator.data.units = "celsius"
        coordinator.async_update_listeners()
        entries = er.async_entries_for_config_entry(
            er.async_get(hass), mock_config_entry.entry_id
        )
        select = next(
            entity for entity in entries if entity.unique_id.endswith("display_units")
        )
        assert hass.states.get(select.entity_id).state == "celsius"
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": select.entity_id, "option": "fahrenheit"},
                blocking=True,
            )
        assert hass.states.get(select.entity_id).state == "celsius"
        assert coordinator.data.failure_count == 1
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
