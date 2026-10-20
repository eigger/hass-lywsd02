"""Regression tests for actual HA service target extraction APIs."""

from homeassistant.core import ServiceCall
from homeassistant.helpers import device_registry as dr

from custom_components.xiaomi_lywsd import _extract_referenced_entities
from custom_components.xiaomi_lywsd.const import DOMAIN


def test_extract_entity_and_device_targets(hass, mock_config_entry):
    """Use the installed HA API and registered device on old and current HA."""
    mock_config_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, "target")}
    )
    call = ServiceCall(
        hass,
        DOMAIN,
        "sync_time",
        {"entity_id": "button.lywsd_sync", "device_id": [device.id]},
    )
    selected = _extract_referenced_entities(hass, call)
    assert "button.lywsd_sync" in selected.referenced
    assert device.id in selected.referenced_devices
