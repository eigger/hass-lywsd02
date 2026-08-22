"""LYWSD02 / LYWSD02MMC GATT implementation.

Protocol values come from ``docs/protocol.md``. Values marked 미검증 there
are provisional (h4/lywsd02 community reference).
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
from datetime import datetime, timezone
from typing import ClassVar

from .base import (
    ClimateReading,
    LywsdClockRepairError,
    LywsdDevice,
    LywsdDeviceError,
    LywsdUnsupportedError,
    LywsdVerifyError,
    SyncResult,
)

_LOGGER = logging.getLogger(__name__)

UUID_TIME = "ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6"
UUID_UNITS = "ebe0ccbe-7a0a-4b0c-8a1a-6ff2997da3a6"
UUID_DATA = "ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6"
UUID_BATTERY = "ebe0ccc4-7a0a-4b0c-8a1a-6ff2997da3a6"

# Measured on LYWSD02MMC (A4:C1:38:16:C5:C4): stock read was 0x00 while the
# E-Ink showed °C. h4/lywsd02 and ashald/home-assistant-lywsd02 both use 0xFF.
# Firmware revisions differ, so decode accepts either and write uses the
# measured value.
UNIT_CELSIUS = b"\x00"
UNIT_CELSIUS_ALT = b"\xff"
UNIT_FAHRENHEIT = b"\x01"

UNITS_TO_CODE = {
    "celsius": UNIT_CELSIUS,
    "fahrenheit": UNIT_FAHRENHEIT,
}
CODE_TO_UNITS = {
    UNIT_CELSIUS: "celsius",
    UNIT_CELSIUS_ALT: "celsius",
    UNIT_FAHRENHEIT: "fahrenheit",
}

TIME_VERIFY_TOLERANCE = 2.0
WRITE_RESPONSE = True  # 미검증: community clients use withResponse=True
DEFAULT_CLIMATE_TIMEOUT = 15.0

# 12h/24h shares the clock characteristic and is told apart by payload length:
# 5 bytes (<Ib) sets the wall clock, 7 bytes (<IHB) sets the display mode.
# Source: ashald/home-assistant-lywsd02. Support varies by firmware revision,
# and the epoch field is zero — a device that reads it as a time write would
# jump to 1970, so callers must restore the clock afterwards.
TIME_FORMAT_12H_PAYLOAD = struct.pack("<IHB", 0, 0, 0xAA)
TIME_FORMAT_24H_PAYLOAD = struct.pack("<IHB", 0, 0, 0x00)

TIME_FORMAT_TO_CODE = {
    "12h": TIME_FORMAT_12H_PAYLOAD,
    "24h": TIME_FORMAT_24H_PAYLOAD,
}


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
        raise LywsdDeviceError(
            f"unknown units payload hex={bytes(payload).hex()} raw={payload!r}"
        ) from err


def encode_time_format(time_format: str) -> bytes:
    """Encode the 12h/24h display mode command."""
    try:
        return TIME_FORMAT_TO_CODE[time_format]
    except KeyError as err:
        raise ValueError(f"unknown time format: {time_format}") from err


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
        self, client, when: datetime, tz_offset_hours: int, *, monotonic=time.monotonic
    ) -> SyncResult:
        """Write the wall clock, compensating for the trip it takes to get there.

        ``when`` is the instant the caller sampled, not the instant the write
        lands. Between the two sit a GATT read round trip and the outbound write
        — hundreds of milliseconds each over an ESPHome proxy — and the device
        stores whole seconds, so truncating instead of rounding threw away up to
        another one. All three errors point the same way, leaving the display
        seconds *behind* real time.

        So the elapsed time is measured on a monotonic clock, half the observed
        read round trip is added as an estimate of the outbound leg, and the
        result is rounded rather than floored. What is left is the device's own
        one-second resolution.
        """
        started = monotonic()
        before = await client.read_gatt_char(UUID_TIME)
        read_rtt = monotonic() - started
        # The value in that response was true at roughly the midpoint of the
        # round trip, not when the request left.
        one_way = read_rtt / 2.0
        before_epoch, _ = decode_time(before)

        if when.tzinfo is None:
            when_utc = when.replace(tzinfo=timezone.utc)
        else:
            when_utc = when.astimezone(timezone.utc)
        base_ts = when_utc.timestamp()

        # Compare like with like: the device reading is from base_ts + one_way.
        drift_seconds = float(before_epoch - (base_ts + one_way))

        # Aim at the moment the write will arrive, not the moment it is built.
        elapsed = monotonic() - started
        written_epoch = round(base_ts + elapsed + one_way)
        compensation = written_epoch - int(base_ts)

        payload = encode_time(written_epoch, tz_offset_hours)
        await client.write_gatt_char(UUID_TIME, payload, response=WRITE_RESPONSE)

        after = await client.read_gatt_char(UUID_TIME)
        after_epoch, _ = decode_time(after)
        # The device has been ticking since the write landed, so check it
        # against the current time rather than against what was written.
        expected_now = base_ts + (monotonic() - started) - one_way
        if abs(after_epoch - expected_now) > TIME_VERIFY_TOLERANCE:
            raise LywsdVerifyError(
                f"time read-back mismatch: expected ~{expected_now:.1f}, "
                f"read {after_epoch}"
            )
        return SyncResult(
            written_epoch=written_epoch,
            read_back_epoch=after_epoch,
            drift_seconds=drift_seconds,
            compensation_seconds=float(compensation),
        )

    async def set_time_format(
        self, client, time_format: str, when: datetime, tz_offset_hours: int
    ) -> SyncResult:
        """Write the 12h/24h mode, then rewrite the wall clock.

        The mode command carries a zero epoch in the same characteristic used
        for time. On firmware that does not recognise the 7-byte form the write
        either fails outright or is taken as a time write — hence the
        unconditional re-sync on the same connection, which repairs the clock
        before the caller ever sees it.

        Failure classification, from most to least certain: a dropped link or a
        timeout is re-raised untouched; a rejected mode command that is followed
        by an accepted clock write on the *same characteristic* is genuinely
        unsupported firmware; if both writes fail it is the connection, not the
        firmware. Mislabelling any of these sends the user hunting for a problem
        that is not there.
        """
        payload = encode_time_format(time_format)
        mode_error: Exception | None = None
        try:
            await client.write_gatt_char(UUID_TIME, payload, response=WRITE_RESPONSE)
        except (TimeoutError, asyncio.CancelledError):
            raise
        except Exception as err:
            if not getattr(client, "is_connected", True):
                raise
            mode_error = err

        # The clock write runs either way. It repairs a device that read the
        # mode command as a time write, and it doubles as a probe: the same
        # characteristic accepting a 5-byte write proves the link and the
        # permissions are fine, so a rejected 7-byte write really was the
        # firmware refusing *this command* rather than a transport problem.
        try:
            result = await self.set_time(client, when, tz_offset_hours)
        except Exception as err:
            if mode_error is not None:
                # Both writes failed — that is a connection or permission
                # problem, not a verdict on the firmware.
                raise mode_error
            raise LywsdClockRepairError(
                f"clock mode was written but the follow-up time write failed: {err}"
            ) from err

        if mode_error is not None:
            raise LywsdUnsupportedError(
                f"device accepted a clock write but rejected the {time_format} "
                f"mode command: {mode_error}"
            ) from mode_error
        return result

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
