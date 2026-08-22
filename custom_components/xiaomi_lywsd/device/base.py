"""Abstract LYWSD device interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar


class LywsdDeviceError(Exception):
    """Base error for device-layer failures."""


class LywsdVerifyError(LywsdDeviceError):
    """Write succeeded but read-back did not match the expected value."""


class LywsdUnsupportedError(LywsdDeviceError):
    """The device firmware does not implement this feature."""


class LywsdClockRepairError(LywsdDeviceError):
    """A mode command landed but the follow-up clock write did not.

    Distinct because the display may now be showing 1970 and the user has to
    run a sync — silently reporting a generic failure would hide that.
    """


@dataclass(frozen=True)
class ClimateReading:
    """One temperature/humidity sample from GATT notify."""

    temperature: float  # °C
    humidity: int  # %


@dataclass(frozen=True)
class SyncResult:
    """Result of a time sync operation."""

    written_epoch: int
    read_back_epoch: int
    drift_seconds: float  # device clock - HA clock, measured before write


class LywsdDevice(ABC):
    """GATT operations for a connected BleakClient."""

    MODEL: ClassVar[str]

    @abstractmethod
    async def read_climate(self, client, timeout: float) -> ClimateReading:
        """Subscribe for one notify and return temperature/humidity."""

    @abstractmethod
    async def get_battery(self, client) -> int | None:
        """Return battery percent, or None if unavailable."""

    @abstractmethod
    async def set_time(
        self, client, when: datetime, tz_offset_hours: int
    ) -> SyncResult:
        """Write wall clock time and return drift/verify metadata."""

    @abstractmethod
    async def get_units(self, client) -> str:
        """Return ``celsius`` or ``fahrenheit``."""

    @abstractmethod
    async def set_units(self, client, units: str) -> None:
        """Write display units; roll back on verify failure."""

    async def set_time_format(
        self, client, time_format: str, when: datetime, tz_offset_hours: int
    ) -> SyncResult:
        """Switch the E-Ink clock between 12h and 24h, then re-sync the clock.

        Returns the sync result of the trailing clock write. Not every LYWSD02
        firmware implements the mode command, so the default refuses rather
        than writing bytes a device might misread.
        """
        raise LywsdUnsupportedError(
            f"{type(self).__name__} does not support time format switching"
        )

    async def read_history(self, client):
        """Phase 3 — not implemented yet."""
        raise NotImplementedError
