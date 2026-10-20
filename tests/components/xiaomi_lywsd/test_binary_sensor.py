"""Real binary sensor and duration platform updates."""

from unittest.mock import patch


async def test_connectivity_and_duration_entities(hass, mock_config_entry):
    from homeassistant.helpers import entity_registry as er

    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=0,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        entities = er.async_entries_for_config_entry(
            er.async_get(hass), mock_config_entry.entry_id
        )
        binary = next(
            entity for entity in entities if entity.unique_id.endswith("connectivity")
        )
        duration = next(
            entity
            for entity in entities
            if entity.unique_id.endswith("connection_duration")
        )
        coord = mock_config_entry.runtime_data
        assert hass.states.get(binary.entity_id).state == "off"
        assert float(hass.states.get(duration.entity_id).state) == 0.0
        coord.begin_connection()
        assert hass.states.get(binary.entity_id).state == "on"
        coord._session_start -= 1.5
        coord.end_connection()
        assert hass.states.get(binary.entity_id).state == "off"
        assert float(hass.states.get(duration.entity_id).state) == 1.5
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
