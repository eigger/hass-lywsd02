"""Polling coordinator for Xiaomi LYWSD."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    AUTO_SYNC_MIN_RATE_SAMPLE_DAYS,
    CONF_CLIMATE_SENSORS,
    CONF_SCAN_INTERVAL,
    DEFAULT_CLIMATE_SENSORS,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    scan_interval_seconds,
)
from .device import LywsdDevice
from .device.lywsd02mmc import DEFAULT_CLIMATE_TIMEOUT
from .store import LywsdStore

_LOGGER = logging.getLogger(__name__)


@dataclass
class LywsdData:
    """Snapshot returned by one poll cycle (and mutated by user actions)."""

    temperature: float | None = None
    humidity: int | None = None
    battery: int | None = None
    units: str | None = None
    time_format: str | None = None
    last_sync: datetime | None = None
    clock_drift: float | None = None
    # Seconds the device clock gains/loses per day, averaged over syncs.
    drift_rate_per_day: float | None = None
    next_sync: datetime | None = None
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
        self._units_warn_logged = False
        self._session_start: float | None = None
        self._unsub_duration: Callable[[], None] | None = None
        self.store = LywsdStore(hass, entry.entry_id)
        # Set by _async_setup_auto_sync so a manual sync re-arms the timer.
        self.reschedule_auto_sync: Callable[[], None] | None = None
        options = {**entry.data, **entry.options}
        climate_on = bool(
            options.get(CONF_CLIMATE_SENSORS, DEFAULT_CLIMATE_SENSORS)
        )
        # Clock-only mode must not open a BLE session every scan_interval —
        # that was burning battery while no climate entity consumed the values.
        if climate_on:
            seconds = scan_interval_seconds(
                options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            )
            update_interval: timedelta | None = timedelta(seconds=seconds)
        else:
            update_interval = None
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.data = LywsdData()
        # Separate coordinators so 1s duration ticks do not refresh climate.
        self.connectivity = DataUpdateCoordinator[bool](
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_connectivity",
            update_interval=None,
        )
        self.connectivity.data = False
        self.connection_duration = DataUpdateCoordinator[float](
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_connection_duration",
            update_interval=None,
        )
        self.connection_duration.data = 0.0

    def begin_connection(self) -> None:
        """Mark BLE session open (after establish_connection succeeds)."""
        self._stop_duration_ticker()
        self._session_start = time.monotonic()
        self.connection_duration.async_set_updated_data(0.0)
        self.connectivity.async_set_updated_data(True)
        self._unsub_duration = async_track_time_interval(
            self.hass, self._tick_duration, timedelta(seconds=1)
        )

    def end_connection(self) -> None:
        """Mark BLE session closed and freeze last duration."""
        self._stop_duration_ticker()
        if self._session_start is not None:
            elapsed = round(time.monotonic() - self._session_start, 1)
            self.connection_duration.async_set_updated_data(elapsed)
        self._session_start = None
        self.connectivity.async_set_updated_data(False)

    def _stop_duration_ticker(self) -> None:
        if self._unsub_duration is not None:
            self._unsub_duration()
            self._unsub_duration = None

    @callback
    def _tick_duration(self, _now: datetime) -> None:
        if self._session_start is None:
            return
        elapsed = round(time.monotonic() - self._session_start, 1)
        self.connection_duration.async_set_updated_data(elapsed)

    async def async_load_persisted(self) -> None:
        """Hydrate durable state before the first refresh or entity setup."""
        stored = await self.store.async_load()
        if not stored:
            return
        self.data.last_sync = stored.get("last_sync")
        self.data.clock_drift = stored.get("clock_drift")
        self.data.drift_rate_per_day = stored.get("drift_rate_per_day")
        if stored.get("battery") is not None:
            self.data.battery = stored["battery"]
        if stored.get("units"):
            self.data.units = stored["units"]
        if stored.get("time_format"):
            self.data.time_format = stored["time_format"]

    async def async_save_persisted(self) -> None:
        """Write durable state. Never let storage errors break a BLE action."""
        try:
            await self.store.async_save(
                last_sync=self.data.last_sync,
                clock_drift=self.data.clock_drift,
                drift_rate_per_day=self.data.drift_rate_per_day,
                battery=self.data.battery,
                units=self.data.units,
                time_format=self.data.time_format,
            )
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.warning("LYWSD %s: store save failed: %s", self.address, err)

    def note_sync(self, drift_seconds: float, when: datetime) -> None:
        """Record a successful clock write and update the observed drift rate.

        ``drift_seconds`` is how far the device clock had wandered since the
        previous sync, so dividing by the elapsed days gives a per-day rate that
        adaptive scheduling can turn back into an interval.
        """
        previous = self.data.last_sync
        if previous is not None:
            elapsed_days = (when - previous).total_seconds() / 86400.0
            if elapsed_days >= AUTO_SYNC_MIN_RATE_SAMPLE_DAYS:
                rate = drift_seconds / elapsed_days
                known = self.data.drift_rate_per_day
                # Smooth so one odd reading cannot swing the interval wildly.
                self.data.drift_rate_per_day = (
                    rate if known is None else (known + rate) / 2.0
                )
        self.data.last_sync = when
        self.data.clock_drift = drift_seconds

    async def async_after_sync(self) -> None:
        """Persist and re-arm the auto-sync timer after any successful sync."""
        await self.async_save_persisted()
        if self.reschedule_auto_sync is not None:
            self.reschedule_auto_sync()

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
                    # Once per coordinator lifetime — unknown bytes must be
                    # visible without enabling debug (proxy T1 path).
                    if not self._units_warn_logged:
                        self._units_warn_logged = True
                        _LOGGER.warning(
                            "LYWSD %s: units read skipped: %s",
                            self.address,
                            err,
                        )
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
            time_format=previous.time_format,
            last_sync=previous.last_sync,
            clock_drift=previous.clock_drift,
            drift_rate_per_day=previous.drift_rate_per_day,
            next_sync=previous.next_sync,
            failure_count=0,
            last_failure=previous.last_failure,
            consecutive_auto_failures=previous.consecutive_auto_failures,
        )
