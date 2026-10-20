"""Exercise actual Home Assistant entry and platform lifecycles."""

from unittest.mock import patch
from types import SimpleNamespace

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr, entity_registry as er

from custom_components.xiaomi_lywsd.const import DOMAIN


async def test_setup_platform_states_and_unload(hass, mock_config_entry):
    """Load every real platform and remove its services and entities on unload."""
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
        assert mock_config_entry.state is ConfigEntryState.LOADED
        entities = er.async_entries_for_config_entry(
            er.async_get(hass), mock_config_entry.entry_id
        )
        assert {entity.domain for entity in entities} == {
            "button",
            "select",
            "sensor",
            "binary_sensor",
        }
        assert dr.async_entries_for_config_entry(
            dr.async_get(hass), mock_config_entry.entry_id
        )
        connectivity = next(
            entity for entity in entities if entity.unique_id.endswith("connectivity")
        )
        assert hass.states.get(connectivity.entity_id).state == "off"
        assert hass.services.has_service(DOMAIN, "sync_time")
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
        assert not hass.services.has_service(DOMAIN, "sync_time")
        assert hass.states.get(connectivity.entity_id).state == "unavailable"


async def test_setup_failure_cleans_auto_sync_callback(hass, mock_config_entry):
    """HA executes registered cleanup when forwarding platforms fails."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"auto_sync": "30"}
    )
    # Inject the forwarding failure; leave HA's entry failure/cleanup path real.
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=RuntimeError("platform setup failed"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.runtime_data.reschedule_auto_sync is None
    assert not hass.services.has_service(DOMAIN, "sync_time")


async def test_options_flow_reloads_entry(hass, mock_config_entry):
    """Changing options reloads loaded platforms on minimum and current HA."""
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
        old_coordinator = mock_config_entry.runtime_data
        flow = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
        assert flow["type"] == "form"
        result = await hass.config_entries.options.async_configure(
            flow["flow_id"],
            {
                "scan_interval": 30,
                "climate_sensors": False,
                "retry_count": 2,
                "auto_sync": "0",
                "auto_sync_tolerance": 60,
            },
        )
        assert result["type"] == "create_entry"
        await hass.async_block_till_done()
        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert mock_config_entry.runtime_data is not old_coordinator
        assert mock_config_entry.options["retry_count"] == 2
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_registered_service_device_target_and_missing_target(
    hass, mock_config_entry, mock_client
):
    """Run the real service router and BLE operation for a registered device."""
    import pytest
    from homeassistant.exceptions import ServiceValidationError

    mock_config_entry.add_to_hass(hass)
    mock_client.services = []
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
            return_value=mock_client,
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        device = dr.async_entries_for_config_entry(
            dr.async_get(hass), mock_config_entry.entry_id
        )[0]
        result = await hass.services.async_call(
            DOMAIN,
            "dump_gatt",
            {"device_id": device.id},
            blocking=True,
            return_response=True,
        )
        assert result == {"AA:BB:CC:DD:EE:FF": {"services": []}}
        mock_client.disconnect.assert_awaited_once()
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, "dump_gatt", {}, blocking=True, return_response=True
            )
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_setup_cancellation_cleans_auto_sync_callback(hass, mock_config_entry):
    """Cancelled platform setup cancels the timer before HA records failure."""
    import asyncio

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, options={"auto_sync": "30"}
    )
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=asyncio.CancelledError,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.reschedule_auto_sync is None
    assert not hass.services.has_service(DOMAIN, "sync_time")
