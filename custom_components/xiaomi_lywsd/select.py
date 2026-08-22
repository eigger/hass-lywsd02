"""Select entities: display units and 12h/24h clock mode."""

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
from homeassistant.util import dt as dt_util

from . import async_execute, async_read_battery_into
from .const import MANUFACTURER, MODEL, TIME_FORMAT_OPTIONS
from .device import (
    LywsdClockRepairError,
    LywsdUnsupportedError,
    LywsdVerifyError,
)
from .types import LywsdConfigEntry

_LOGGER = logging.getLogger(__name__)

OPTIONS = ["celsius", "fahrenheit"]
TIME_FORMATS = list(TIME_FORMAT_OPTIONS)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LywsdConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [
            LywsdDisplayUnitsSelect(hass, entry),
            LywsdTimeFormatSelect(hass, entry),
        ]
    )


class _LywsdSelectBase(CoordinatorEntity, RestoreEntity, SelectEntity):
    """Shared plumbing: device info, availability, optimistic writes."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, hass: HomeAssistant, entry: LywsdConfigEntry, key: str
    ) -> None:
        self.hass = hass
        self._entry = entry
        coordinator = entry.runtime_data
        super().__init__(coordinator)
        self._address = coordinator.address
        self._identifier = coordinator.identifier
        self._attr_translation_key = key
        self._attr_unique_id = f"xiaomi_lywsd_{self._identifier}_{key}"
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


class LywsdDisplayUnitsSelect(_LywsdSelectBase):
    """°C / °F — single source of truth: coordinator.data.units."""

    _attr_options = OPTIONS

    def __init__(self, hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
        super().__init__(hass, entry, "display_units")

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
        coordinator = self._entry.runtime_data
        previous = coordinator.data.units

        async def _op(client, device):
            await device.set_units(client, option)
            coordinator.data.units = option
            return option

        try:
            await async_execute(self.hass, self._entry, _op)
            coordinator.record_action_success()
            await coordinator.async_save_persisted()
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


class LywsdTimeFormatSelect(_LywsdSelectBase):
    """12h / 24h E-Ink clock mode.

    Experimental: the 0xAA/0x00 payloads are still unverified against hardware
    (see docs/protocol.md), the device offers no read-back, and firmware that
    simply ignores the command is indistinguishable from success. Disabled by
    default until measured; state is optimistic and restored across restarts.
    """

    _attr_options = TIME_FORMATS
    _attr_entity_registry_enabled_default = False

    def __init__(self, hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
        super().__init__(hass, entry, "time_format")

    @property
    def current_option(self) -> str | None:
        return self._entry.runtime_data.data.time_format

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._entry.runtime_data.data.time_format in TIME_FORMATS:
            return
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state in TIME_FORMATS:
            self._entry.runtime_data.data.time_format = last_state.state

    async def async_select_option(self, option: str) -> None:
        coordinator = self._entry.runtime_data
        previous = coordinator.data.time_format
        now = dt_util.now()
        utcoffset = now.utcoffset()
        tz_offset_hours = (
            int(utcoffset.total_seconds() // 3600) if utcoffset else 0
        )

        async def _op(client, device):
            # set_time_format rewrites the clock on the same connection, so a
            # firmware that mistakes the mode command for a time write cannot
            # leave the display stuck in 1970.
            result = await device.set_time_format(
                client, option, now, tz_offset_hours
            )
            coordinator.data.time_format = option
            coordinator.note_sync(result.drift_seconds, dt_util.now())
            await async_read_battery_into(client, device, coordinator)
            return option

        try:
            await async_execute(self.hass, self._entry, _op)
            await coordinator.async_after_sync()
            coordinator.record_action_success()
        except LywsdClockRepairError as err:
            # The mode very likely changed; only the clock repair failed, so
            # keep the new option and tell the user to run a sync.
            coordinator.record_failure()
            raise HomeAssistantError(
                "표시 모드는 바뀌었지만 시계 복구에 실패했습니다. "
                "화면이 1970년이면 시간 동기화를 실행하세요."
            ) from err
        except Exception as err:
            coordinator.data.time_format = previous
            coordinator.record_failure()
            if isinstance(err, LywsdUnsupportedError):
                raise HomeAssistantError(
                    "기기가 12/24시간 전환 명령을 거부했습니다 "
                    "(이 펌웨어는 지원하지 않을 수 있습니다)"
                ) from err
            if isinstance(err, HomeAssistantError):
                raise
            raise HomeAssistantError(f"Failed to set clock mode: {err}") from err
