"""LYWSD02 / LYWSD02MMC GATT implementation.

Protocol values come from ``docs/protocol.md``. Values marked 미검증 there
are provisional (h4/lywsd02 community reference).
"""

from __future__ import annotations

import asyncio
import logging
import math
import struct
import time
from datetime import datetime, timezone
from typing import ClassVar

from .base import (
    ClimateReading,
    ClockReading,
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
# The clock answers in whole seconds, so an epoch of N places the device
# anywhere in [N, N+1) and the middle of that window is the unbiased estimate.
# Reading N as N exactly would report a perfect clock as half a second slow.
EPOCH_MIDPOINT = 0.5
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


def _utc_timestamp(when: datetime) -> float:
    """Seconds since the epoch for an aware or naive-UTC datetime."""
    if when.tzinfo is None:
        return when.replace(tzinfo=timezone.utc).timestamp()
    return when.astimezone(timezone.utc).timestamp()


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

    async def get_time(
        self, client, when: datetime, *, monotonic=time.monotonic
    ) -> ClockReading:
        """Read the clock and report its error against ``when``.

        One 5-byte read on a connection that is already open, which is what
        makes drift worth checking on every climate poll: the connection is the
        expensive part, the read is a single round trip on top of it.

        Two corrections separate the clock's error from the way it was read.

        The value in the response was true at roughly the midpoint of that
        round trip, not when the request left, so the comparison is made
        against ``when`` advanced by one estimated one-way trip. Without that
        correction every reading over a proxy hop looks slow by the link
        latency, and a threshold near the device's one-second resolution would
        fire on the link rather than on the clock.

        And the answer is a whole second: an epoch of N means the device is
        somewhere in [N, N+1), so the estimate is N + ``EPOCH_MIDPOINT``.
        Taking N flat would report a perfect clock as half a second slow every
        time — a bias that survives averaging and, worse, propagates into the
        drift rate, where half a second over a short interval is enough to
        stretch the next one noticeably.
        """
        started = monotonic()
        raw = await client.read_gatt_char(UUID_TIME)
        one_way = (monotonic() - started) / 2.0
        epoch, tz_offset = decode_time(raw)
        base_ts = _utc_timestamp(when)
        return ClockReading(
            epoch=epoch,
            tz_offset_hours=tz_offset,
            drift_seconds=float(epoch + EPOCH_MIDPOINT - (base_ts + one_way)),
            one_way_seconds=one_way,
            sampled_at=started,
        )

    async def set_time(
        self,
        client,
        when: datetime,
        tz_offset_hours: int,
        *,
        monotonic=time.monotonic,
        sleeper=asyncio.sleep,
        reading: ClockReading | None = None,
    ) -> SyncResult:
        """Write the wall clock so it lands on a whole second.

        The device stores whole seconds, so rounding the target leaves up to
        half a second of quantisation — and not evenly: when the link latency
        lands the target just above .5 every time, rounding goes up every time
        and the display runs consistently early. Flooring just moves the bias
        the other way.

        So the write is aimed instead of rounded. The next second boundary the
        write can still reach is chosen, and the write is held back until the
        boundary minus one estimated one-way trip. The device then receives
        second T at second T, and what is left is the error in the latency
        estimate rather than a guaranteed half second.

        Latency is measured, not assumed: the preceding read's round trip gives
        the estimate, and the wait is capped by construction at one second.

        A caller that has just read the clock — the poll cycle, which decides
        whether to write at all from that read — passes it as ``reading`` and
        the read is not repeated. It must have been taken with the same
        ``when``, since both are anchored to the same monotonic timeline.
        """
        if reading is None:
            reading = await self.get_time(client, when, monotonic=monotonic)
        started = reading.sampled_at
        one_way = reading.one_way_seconds
        drift_seconds = reading.drift_seconds
        base_ts = _utc_timestamp(when)

        def _now_ts() -> float:
            return base_ts + (monotonic() - started)

        # First boundary the write can still reach, then wait for its cue.
        written_epoch = int(math.floor(_now_ts() + one_way)) + 1
        wait = (written_epoch - one_way) - _now_ts()
        if wait > 0:
            await sleeper(wait)
        compensation = float(written_epoch) - base_ts

        payload = encode_time(written_epoch, tz_offset_hours)
        await client.write_gatt_char(UUID_TIME, payload, response=WRITE_RESPONSE)

        after = await client.read_gatt_char(UUID_TIME)
        after_epoch, _ = decode_time(after)
        # The device has been ticking since the write landed, so check it
        # against the current time rather than against what was written.
        expected_now = base_ts + (monotonic() - started) - one_way
        residual = float(after_epoch + EPOCH_MIDPOINT - expected_now)
        if abs(residual) > TIME_VERIFY_TOLERANCE:
            raise LywsdVerifyError(
                f"time read-back mismatch: expected ~{expected_now:.1f}, "
                f"read {after_epoch}"
            )
        return SyncResult(
            written_epoch=written_epoch,
            read_back_epoch=after_epoch,
            drift_seconds=drift_seconds,
            compensation_seconds=float(compensation),
            residual_seconds=residual,
        )

    async def set_time_format(
        self,
        client,
        time_format: str,
        when: datetime,
        tz_offset_hours: int,
        *,
        monotonic=time.monotonic,
        sleeper=asyncio.sleep,
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
            result = await self.set_time(
                client, when, tz_offset_hours, monotonic=monotonic, sleeper=sleeper
            )
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
