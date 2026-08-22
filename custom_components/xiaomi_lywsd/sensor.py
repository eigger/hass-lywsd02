"""Sensors for Xiaomi LYWSD — climate + diagnostic."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_CLIMATE_SENSORS,
    DEFAULT_CLIMATE_SENSORS,
    MANUFACTURER,
    MODEL,
)
from .coordinator import LywsdData
from .types import LywsdConfigEntry

CLIMATE_VALUE_KEYS = frozenset({"temperature", "humidity", "battery"})

CLIMATE_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="temperature",
        translation_key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    SensorEntityDescription(
        key="humidity",
        translation_key="humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    SensorEntityDescription(
        key="battery",
        translation_key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)

DIAGNOSTIC_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="last_sync",
        translation_key="last_sync",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="failure_count",
        translation_key="failure_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="last_failure",
        translation_key="last_failure",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LywsdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    options = {**entry.data, **entry.options}
    climate_on = bool(options.get(CONF_CLIMATE_SENSORS, DEFAULT_CLIMATE_SENSORS))

    descriptions = list(DIAGNOSTIC_SENSORS)
    if climate_on:
        descriptions = list(CLIMATE_SENSORS) + descriptions

    async_add_entities(
        [LywsdSensor(coordinator, desc) for desc in descriptions]
        + [LywsdConnectionDurationSensor(coordinator)]
    )


class LywsdSensor(CoordinatorEntity, SensorEntity):
    """Coordinator-backed LYWSD sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, description: SensorEntityDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._lywsd = coordinator
        self._attr_translation_key = description.translation_key
        self._attr_unique_id = (
            f"xiaomi_lywsd_{coordinator.identifier}_{description.key}"
        )
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, coordinator.address)},
            name=f"LYWSD02 {coordinator.identifier}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )

    @property
    def available(self) -> bool:
        # Poll health applies only to climate values. Action diagnostics
        # (last_sync, failure_count, …) stay available after a failed poll so a
        # successful sync is still visible.
        if self.entity_description.key in CLIMATE_VALUE_KEYS:
            if not self._lywsd.last_update_success:
                return False
            return (
                getattr(self._lywsd.data, self.entity_description.key, None)
                is not None
            )
        return True

    @property
    def native_value(self):
        data: LywsdData = self._lywsd.data
        return getattr(data, self.entity_description.key, None)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        """Clock health rides on last_sync instead of separate entities.

        Drift is only meaningful next to the sync it was measured at, and a
        standalone sensor added a second row to every dashboard for a number
        nobody graphs.
        """
        if self.entity_description.key != "last_sync":
            return None
        data: LywsdData = self._lywsd.data
        return {
            "drift_seconds": data.clock_drift,
            "drift_seconds_per_day": (
                round(data.drift_rate_per_day, 3)
                if data.drift_rate_per_day is not None
                else None
            ),
            "next_sync": data.next_sync,
        }


class LywsdConnectionDurationSensor(
    CoordinatorEntity,
    SensorEntity,
):
    """Seconds the last/current BLE session stayed connected."""

    _attr_has_entity_name = True
    _attr_translation_key = "connection_duration"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 1

    def __init__(self, lywsd_coordinator) -> None:
        super().__init__(lywsd_coordinator.connection_duration)
        self._lywsd = lywsd_coordinator
        self._attr_unique_id = (
            f"xiaomi_lywsd_{lywsd_coordinator.identifier}_connection_duration"
        )
        self._attr_device_info = DeviceInfo(
            connections={(CONNECTION_BLUETOOTH, lywsd_coordinator.address)},
            name=f"LYWSD02 {lywsd_coordinator.identifier}",
            manufacturer=MANUFACTURER,
            model=MODEL,
        )
        self._native_value = float(lywsd_coordinator.connection_duration.data or 0.0)

    @property
    def available(self) -> bool:
        return True

    @property
    def native_value(self) -> float:
        return self._native_value

    @callback
    def _handle_coordinator_update(self) -> None:
        self._native_value = float(self.coordinator.data or 0.0)
        super()._handle_coordinator_update()
