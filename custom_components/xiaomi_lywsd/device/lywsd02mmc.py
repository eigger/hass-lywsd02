"""LYWSD02 / LYWSD02MMC GATT implementation.

Protocol values come from ``docs/protocol.md``. Values marked 미검증 there
are provisional (h4/lywsd02 community reference).
"""

from __future__ import annotations

import asyncio
import logging
import struct
from datetime import datetime, timezone
from typing import ClassVar

from .base import (
    ClimateReading,
    LywsdDevice,
    LywsdDeviceError,
    LywsdVerifyError,
    SyncResult,
)

_LOGGER = logging.getLogger(__name__)

UUID_TIME = "ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6"
UUID_UNITS = "ebe0ccbe-7a0a-4b0c-8a1a-6ff2997da3a6"
UUID_DATA = "ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6"
UUID_BATTERY = "ebe0ccc4-7a0a-4b0c-8a1a-6ff2997da3a6"

UNIT_CELSIUS = b"\xff"
UNIT_FAHRENHEIT = b"\x01"

UNITS_TO_CODE = {
    "celsius": UNIT_CELSIUS,
    "fahrenheit": UNIT_FAHRENHEIT,
}
CODE_TO_UNITS = {
    UNIT_CELSIUS: "celsius",
    UNIT_FAHRENHEIT: "fahrenheit",
}

TIME_VERIFY_TOLERANCE = 2.0
WRITE_RESPONSE = True  # 미검증: community clients use withResponse=True
DEFAULT_CLIMATE_TIMEOUT = 15.0


def encode_time(epoch: int, tz_offset_hours: int) -> bytes:
    """Pack uint32 LE epoch + int8 timezone offset hours."""
    if tz_offset_hours < -12 or tz_offset_hours > 14:
        raise ValueError(f"tz_offset_hours out of range: {tz_offset_hours}")
    return struct.pack("<Ib", int(epoch), int(tz_offset_hours))


def decode_time(payload: bytes) -> tuple[int, int]:
    """Unpack time characteristic. Returns (epoch, tz_offset_hours)."""
    if len(payload) >= 5:
        epoch, tz = struct.unpack_from("<Ib", payload)
        return int(epoch), int(tz)
    if len(payload) >= 4:
        (epoch,) = struct.unpack_from("<I", payload)
        return int(epoch), 0
    raise LywsdDeviceError(f"time payload too short: {payload!r}")


def encode_units(units: str) -> bytes:
    """Encode display units option to GATT bytes."""
    try:
        return UNITS_TO_CODE[units]
    except KeyError as err:
        raise ValueError(f"unknown units: {units}") from err


def decode_units(payload: bytes) -> str:
    """Decode GATT units byte to option string."""
    key = bytes(payload[:1]) if payload else b""
    try:
        return CODE_TO_UNITS[key]
    except KeyError as err:
        raise LywsdDeviceError(f"unknown units payload: {payload!r}") from err


def decode_climate(payload: bytes) -> ClimateReading:
    """Decode ``<hB`` temperature (°C×100) + humidity (%)."""
    if len(payload) < 3:
        raise LywsdDeviceError(f"climate payload too short: {payload!r}")
    raw_temp, humidity = struct.unpack_from("<hB", payload)
    return ClimateReading(temperature=raw_temp / 100.0, humidity=int(humidity))


class Lywsd02mmc(LywsdDevice):
    """LYWSD02 / LYWSD02MMC."""

    MODEL: ClassVar[str] = "LYWSD02MMC"

    async def read_climate(
        self, client, timeout: float = DEFAULT_CLIMATE_TIMEOUT
    ) -> ClimateReading:
        event = asyncio.Event()
        holder: dict[str, bytes] = {}

        def _handler(_sender, data: bytearray) -> None:
            if "payload" not in holder:
                holder["payload"] = bytes(data)
                event.set()

        await client.start_notify(UUID_DATA, _handler)
        try:
            try:
                await asyncio.wait_for(event.wait(), timeout)
            except TimeoutError as err:
                raise LywsdDeviceError(
                    f"climate notify timed out after {timeout}s"
                ) from err
        finally:
            try:
                await client.stop_notify(UUID_DATA)
            except Exception as stop_err:
                _LOGGER.warning("stop_notify failed: %s", stop_err)

        return decode_climate(holder["payload"])

    async def set_time(
        self, client, when: datetime, tz_offset_hours: int
    ) -> SyncResult:
        before = await client.read_gatt_char(UUID_TIME)
        before_epoch, _ = decode_time(before)

        if when.tzinfo is None:
            when_utc = when.replace(tzinfo=timezone.utc)
        else:
            when_utc = when.astimezone(timezone.utc)
        written_epoch = int(when_utc.timestamp())
        drift_seconds = float(before_epoch - written_epoch)

        payload = encode_time(written_epoch, tz_offset_hours)
        await client.write_gatt_char(UUID_TIME, payload, response=WRITE_RESPONSE)

        after = await client.read_gatt_char(UUID_TIME)
        after_epoch, _ = decode_time(after)
        if abs(after_epoch - written_epoch) > TIME_VERIFY_TOLERANCE:
            raise LywsdVerifyError(
                f"time read-back mismatch: wrote {written_epoch}, read {after_epoch}"
            )
        return SyncResult(
            written_epoch=written_epoch,
            read_back_epoch=after_epoch,
            drift_seconds=drift_seconds,
        )

    async def get_units(self, client) -> str:
        raw = await client.read_gatt_char(UUID_UNITS)
        return decode_units(raw)

    async def set_units(self, client, units: str) -> None:
        original = await client.read_gatt_char(UUID_UNITS)
        payload = encode_units(units)
        await client.write_gatt_char(UUID_UNITS, payload, response=WRITE_RESPONSE)
        after = await client.read_gatt_char(UUID_UNITS)
        if bytes(after[:1]) != payload:
            try:
                await client.write_gatt_char(
                    UUID_UNITS, original, response=WRITE_RESPONSE
                )
            except Exception as rollback_err:
                raise LywsdVerifyError(
                    f"units verify failed and rollback failed: {rollback_err}"
                ) from rollback_err
            raise LywsdVerifyError(
                f"units read-back mismatch: wrote {payload!r}, read {after!r}"
            )

    async def get_battery(self, client) -> int | None:
        try:
            raw = await client.read_gatt_char(UUID_BATTERY)
        except Exception:
            return None
        if not raw:
            return None
        return int(raw[0])
