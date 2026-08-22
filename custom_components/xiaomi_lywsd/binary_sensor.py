"""Binary sensors for Xiaomi LYWSD — BLE connectivity."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import MANUFACTURER, MODEL
from .types import LywsdConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LywsdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities([LywsdConnectivityBinarySensor(coordinator)])


class LywsdConnectivityBinarySensor(
    CoordinatorEntity[DataUpdateCoordinator[bool]],
    BinarySensorEntity,
):
    """True while a BLE GATT session is open (gicisky/niimbot pattern)."""

    _attr_has_entity_name = True
    _attr_translation_key = "connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, lywsd_coordinator) -> None:
        super().__init__(lywsd_coordinator.connectivity)
        self._lywsd = lywsd_coordinator
        self._attr_unique_id = (
            f"xiaomi_lywsd_{lywsd_coordinator.identifier}_connectivity"
        )
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, lywsd_coordinator.address)},
            name=f"LYWSD02 {lywsd_coordinator.identifier}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
        self._is_on = bool(lywsd_coordinator.connectivity.data)

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        return self._is_on

    @callback
    def _handle_coordinator_update(self) -> None:
        self._is_on = bool(self.coordinator.data)
        super()._handle_coordinator_update()
