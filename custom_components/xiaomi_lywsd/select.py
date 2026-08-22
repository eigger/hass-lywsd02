"""Select entity for display units."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import async_execute
from .const import MANUFACTURER, MODEL
from .device import LywsdVerifyError
from .types import LywsdConfigEntry

_LOGGER = logging.getLogger(__name__)

OPTIONS = ["celsius", "fahrenheit"]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LywsdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([LywsdDisplayUnitsSelect(hass, entry)])


class LywsdDisplayUnitsSelect(CoordinatorEntity, RestoreEntity, SelectEntity):
    """°C / °F select — single source of truth: coordinator.data.units."""

    _attr_has_entity_name = True
    _attr_translation_key = "display_units"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = OPTIONS

    def __init__(self, hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        coordinator = entry.runtime_data
        super().__init__(coordinator)
        self._address = coordinator.address
        self._identifier = coordinator.identifier
        self._attr_unique_id = f"xiaomi_lywsd_{self._identifier}_display_units"
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, self._address)},
            name=f"LYWSD02 {self._identifier}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        return (
            bluetooth.async_ble_device_from_address(
                self.hass, self._address, connectable=True
            )
            is not None
        )

    @property
    def current_option(self) -> str | None:
        return self._entry.runtime_data.data.units

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._entry.runtime_data.data.units in OPTIONS:
            return
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in OPTIONS:
            self._entry.runtime_data.data.units = last_state.state

    async def async_select_option(self, option: str) -> None:
        previous = self._entry.runtime_data.data.units
        coordinator = self._entry.runtime_data

        async def _op(client, device):
            await device.set_units(client, option)
            coordinator.data.units = option
            return option

        try:
            await async_execute(self.hass, self._entry, _op)
            coordinator.record_action_success()
        except Exception as err:
            coordinator.data.units = previous
            coordinator.record_failure()
            if isinstance(err, LywsdVerifyError):
                raise HomeAssistantError(
                    "기기가 표시 단위 쓰기를 확인하지 못했습니다"
                ) from err
            if isinstance(err, HomeAssistantError):
                raise
            raise HomeAssistantError(f"Failed to set units: {err}") from err
