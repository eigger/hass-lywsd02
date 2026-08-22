"""Polling coordinator for Xiaomi LYWSD."""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .device import LywsdDevice
from .device.lywsd02mmc import DEFAULT_CLIMATE_TIMEOUT

_LOGGER = logging.getLogger(__name__)


@dataclass
class LywsdData:
    """Snapshot returned by one poll cycle (and mutated by user actions)."""

    temperature: float | None = None
    humidity: int | None = None
    battery: int | None = None
    units: str | None = None
    last_sync: datetime | None = None
    last_drift_seconds: float | None = None
    failure_count: int = 0
    last_failure: datetime | None = None
    consecutive_auto_failures: int = 0


class LywsdCoordinator(DataUpdateCoordinator[LywsdData]):
    """Connect once per interval, collect climate + battery, disconnect."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry,
        address: str,
        lock,
        device: LywsdDevice,
    ) -> None:
        self.entry = entry
        self.address = address
        self.lock = lock
        self.device = device
        self.hass = hass
        self.identifier = address.replace(":", "")[-8:]
        options = {**entry.data, **entry.options}
        scan_interval = max(
            MIN_SCAN_INTERVAL,
            int(options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.data = LywsdData()

    def record_action_success(self) -> None:
        """Notify listeners after a button/select/service/auto-sync success.

        Only ``_async_update_data`` may flip ``last_update_success`` via
        ``async_set_updated_data``. An action that touched the device (e.g. time
        sync) did not refresh climate — publishing via ``push`` would revive
        stale temperature/humidity as if a poll had succeeded.
        """
        self.async_update_listeners()

    def record_failure(self) -> None:
        """Failure path: bump counters without flipping last_update_success.

        ``async_set_updated_data`` would set ``last_update_success=True`` and
        reset the poll timer — wrong after a failed button/select/service call.
        """
        self.data.failure_count += 1
        self.data.last_failure = dt_util.now()
        self.async_update_listeners()

    async def _async_update_data(self) -> LywsdData:
        # Late import avoids circular dependency with async_execute.
        from . import async_execute

        previous = self.data

        async def _op(client, device):
            climate = await device.read_climate(client, DEFAULT_CLIMATE_TIMEOUT)
            battery = await device.get_battery(client)
            units = previous.units
            if units is None:
                try:
                    units = await device.get_units(client)
                except Exception as err:
                    _LOGGER.debug("units read skipped: %s", err)
            return climate, battery, units

        try:
            climate, battery, units = await async_execute(
                self.hass, self.entry, _op, wrap_errors=False
            )
        except Exception as err:
            # Bookkeeping lives here — async_execute never mutates failure_count.
            updated = replace(
                previous,
                failure_count=previous.failure_count + 1,
                last_failure=dt_util.now(),
            )
            self.data = updated
            raise UpdateFailed(f"LYWSD poll failed for {self.address}: {err}") from err

        return LywsdData(
            temperature=climate.temperature,
            humidity=climate.humidity,
            battery=battery if battery is not None else previous.battery,
            units=units if units is not None else previous.units,
            last_sync=previous.last_sync,
            last_drift_seconds=previous.last_drift_seconds,
            failure_count=0,
            last_failure=previous.last_failure,
            consecutive_auto_failures=previous.consecutive_auto_failures,
        )
