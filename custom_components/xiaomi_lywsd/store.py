"""Persistent state for Xiaomi LYWSD.

Entity state restore is not enough here: the auto-sync scheduler needs the last
sync time *before* any entity exists, and ``async_track_time_interval`` restarts
its countdown on every Home Assistant restart — a 30-day cycle would never fire
on a box that reboots weekly. Storing the timestamp lets the scheduler compute
the real remaining time instead.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, STORAGE_VERSION, TIME_FORMAT_OPTIONS

_LOGGER = logging.getLogger(__name__)


def _parse_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw
    parsed = dt_util.parse_datetime(str(raw))
    return parsed


def _parse_float(raw: Any) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


class LywsdStore:
    """Small typed wrapper around one ``Store`` per config entry."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}")

    async def async_load(self) -> dict[str, Any]:
        """Return persisted values, tolerating a missing or corrupt file."""
        try:
            raw = await self._store.async_load()
        except Exception as err:  # pragma: no cover - defensive
            _LOGGER.warning("LYWSD store load failed, starting fresh: %s", err)
            return {}
        if not isinstance(raw, dict):
            return {}

        time_format = raw.get("time_format")
        return {
            "last_sync": _parse_dt(raw.get("last_sync")),
            "clock_drift": _parse_float(raw.get("clock_drift")),
            "drift_rate_per_day": _parse_float(raw.get("drift_rate_per_day")),
            "units": raw.get("units") or None,
            "time_format": (
                time_format if time_format in TIME_FORMAT_OPTIONS else None
            ),
        }

    async def async_save(
        self,
        *,
        last_sync: datetime | None,
        clock_drift: float | None,
        drift_rate_per_day: float | None,
        units: str | None,
        time_format: str | None,
    ) -> None:
        """Write the durable subset of coordinator state."""
        await self._store.async_save(
            {
                "last_sync": last_sync.isoformat() if last_sync else None,
                "clock_drift": clock_drift,
                "drift_rate_per_day": drift_rate_per_day,
                "units": units,
                "time_format": time_format,
            }
        )

    async def async_remove(self) -> None:
        """Drop the file when the config entry is removed."""
        await self._store.async_remove()
