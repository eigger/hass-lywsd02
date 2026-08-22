"""Button entities for Xiaomi LYWSD."""

from __future__ import annotations

import logging

from homeassistant.components import bluetooth
from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import async_execute
from .const import MANUFACTURER, MODEL
from .device import LywsdVerifyError
from .types import LywsdConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LywsdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([LywsdSyncTimeButton(hass, entry)])


def _reraise_action_error(action: str, err: Exception) -> None:
    if isinstance(err, HomeAssistantError):
        raise err
    if isinstance(err, LywsdVerifyError):
        raise HomeAssistantError(
            "기기가 시간 쓰기를 확인하지 못했습니다"
        ) from err
    raise HomeAssistantError(f"Failed to {action}: {err}") from err


class LywsdSyncTimeButton(ButtonEntity):
    """Write current HA time to the E-Ink clock."""

    _attr_has_entity_name = True
    _attr_translation_key = "sync_time"

    def __init__(self, hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        coordinator = entry.runtime_data
        self._address = coordinator.address
        self._identifier = coordinator.identifier
        self._attr_unique_id = f"xiaomi_lywsd_{self._identifier}_sync_time"
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

    async def async_press(self) -> None:
        utcoffset = dt_util.now().utcoffset()
        tz_offset_hours = (
            int(utcoffset.total_seconds() // 3600) if utcoffset else 0
        )

        async def _op(client, device):
            result = await device.set_time(
                client, dt_util.now(), tz_offset_hours
            )
            coord = self._entry.runtime_data
            coord.data.last_sync = dt_util.now()
            coord.data.last_drift_seconds = result.drift_seconds
            return result

        try:
            await async_execute(self.hass, self._entry, _op)
            self._entry.runtime_data.record_action_success()
        except Exception as err:
            self._entry.runtime_data.record_failure()
            _reraise_action_error("sync time", err)
