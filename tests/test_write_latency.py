"""Clock write timing: what reaches the device must be the time it arrives."""

from __future__ import annotations

import datetime as dt

import pytest

from custom_components.xiaomi_lywsd.device import Lywsd02mmc, LywsdVerifyError
from custom_components.xiaomi_lywsd.device.lywsd02mmc import (
    UUID_TIME,
    decode_time,
    encode_time,
)
from tests.fake_client import FakeBleakClient

UTC = dt.timezone.utc


class _Clock:
    """Monotonic stub advancing a fixed amount per GATT round trip."""

    def __init__(self, step: float) -> None:
        self.t = 1000.0
        self.step = step

    def __call__(self) -> float:
        return self.t

    def half(self) -> None:
        self.t += self.step / 2.0


def _client(clock: _Clock, when: dt.datetime) -> FakeBleakClient:
    """Fake device that keeps real time and answers from mid-round-trip.

    A response reflects the device partway through the exchange, not when the
    request left — modelling that is the only way to tell a correct latency
    compensation from one that is off by a one-way trip.
    """
    base_epoch = when.timestamp()
    client = FakeBleakClient({UUID_TIME: encode_time(int(base_epoch), 9)})
    real_read, real_write = client.read_gatt_char, client.write_gatt_char
    # None until written: the device starts perfectly in sync with base_epoch.
    stored: dict[str, float | None] = {"epoch": None, "at": None}

    def _device_now() -> float:
        if stored["epoch"] is None:
            return base_epoch + (clock.t - 1000.0)
        return stored["epoch"] + (clock.t - stored["at"])

    async def read(uuid):
        clock.half()  # request in flight
        value = _device_now()
        clock.half()  # response coming back
        if str(uuid).lower() == UUID_TIME.lower():
            return encode_time(int(value), 9)
        return await real_read(uuid)

    async def write(uuid, data, response=False):
        clock.half()
        if len(data) == 5:
            stored["epoch"] = float(decode_time(bytes(data))[0])
            stored["at"] = clock.t
        clock.half()
        await real_write(uuid, data, response=response)

    client.read_gatt_char = read
    client.write_gatt_char = write
    return client


@pytest.mark.asyncio
async def test_written_time_targets_arrival_not_sampling():
    """One second of link latency must not land one second in the past."""
    when = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    clock = _Clock(step=1.0)  # 1 s per round trip
    client = _client(clock, when)

    result = await Lywsd02mmc().set_time(client, when, 9, monotonic=clock)

    sampled = int(when.timestamp())
    # read (1 s) + half of it as the outbound estimate = 1.5 s, rounded.
    assert result.written_epoch == sampled + 2
    assert result.compensation_seconds == 2.0


@pytest.mark.asyncio
async def test_fast_link_only_pays_the_rounding():
    """With no measurable latency the write is the sampled second."""
    when = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    clock = _Clock(step=0.0)
    client = _client(clock, when)

    result = await Lywsd02mmc().set_time(client, when, 9, monotonic=clock)
    assert result.written_epoch == int(when.timestamp())
    assert result.compensation_seconds == 0.0


@pytest.mark.asyncio
async def test_sub_second_sample_rounds_instead_of_truncating():
    """int() always floored, losing up to a second and always the same way."""
    when = dt.datetime(2026, 8, 23, 12, 0, 0, 800_000, tzinfo=UTC)
    clock = _Clock(step=0.0)
    client = _client(clock, when)

    result = await Lywsd02mmc().set_time(client, when, 9, monotonic=clock)
    assert result.written_epoch == int(when.timestamp()) + 1


@pytest.mark.asyncio
async def test_slow_link_does_not_trip_the_verify():
    """Read-back is compared with the current time, not with what was written —
    otherwise the device ticking during the round trip looks like a mismatch."""
    when = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    clock = _Clock(step=1.5)  # 4.5 s across three round trips
    client = _client(clock, when)

    result = await Lywsd02mmc().set_time(client, when, 9, monotonic=clock)
    assert result.read_back_epoch > result.written_epoch - 2


@pytest.mark.asyncio
async def test_a_genuinely_wrong_read_back_still_fails():
    when = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    clock = _Clock(step=0.0)
    client = _client(clock, when)

    async def stuck_read(uuid):
        return encode_time(0, 9)  # device reports 1970

    client.read_gatt_char = stuck_read
    with pytest.raises(LywsdVerifyError):
        await Lywsd02mmc().set_time(client, when, 9, monotonic=clock)


@pytest.mark.asyncio
async def test_drift_is_measured_against_the_same_instant():
    """The device value is from mid-round-trip; comparing it with the sampling
    instant would report the link latency as clock drift."""
    when = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    clock = _Clock(step=1.0)
    client = _client(clock, when)  # device is perfectly in sync

    result = await Lywsd02mmc().set_time(client, when, 9, monotonic=clock)
    assert abs(result.drift_seconds) <= 0.5
