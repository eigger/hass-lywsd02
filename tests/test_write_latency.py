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

    async def sleep(self, seconds: float) -> None:
        """Stand in for asyncio.sleep so the boundary wait costs no real time."""
        self.t += seconds


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
        clock.half()  # request in flight
        if len(data) == 5:
            # True time, as an epoch, at the instant the device applies it.
            client.applied_true_epoch = base_epoch + (clock.t - 1000.0)
            stored["epoch"] = float(decode_time(bytes(data))[0])
            stored["at"] = clock.t
        clock.half()  # ack coming back
        await real_write(uuid, data, response=response)

    client.applied_true_epoch = None
    client.read_gatt_char = read
    client.write_gatt_char = write
    return client


async def _run(when: dt.datetime, step: float):
    clock = _Clock(step=step)
    client = _client(clock, when)
    result = await Lywsd02mmc().set_time(
        client, when, 9, monotonic=clock, sleeper=clock.sleep
    )
    return result, clock, client


@pytest.mark.asyncio
@pytest.mark.parametrize("step", [0.0, 0.4, 1.0, 2.2])
@pytest.mark.parametrize("micros", [0, 200_000, 500_000, 900_000])
async def test_the_device_receives_second_t_at_second_t(step, micros):
    """The whole point: no rounding bias left, whatever the link costs.

    The device stores whole seconds, so the only way to avoid a guaranteed
    half-second error is to make the write arrive *on* the boundary it carries.
    """
    when = dt.datetime(2026, 8, 23, 12, 0, 0, micros, tzinfo=UTC)
    result, _clock, client = await _run(when, step)

    # The device applied `written_epoch` when the true time was this.
    assert abs(result.written_epoch - client.applied_true_epoch) < 0.05


@pytest.mark.asyncio
async def test_the_wait_never_exceeds_one_second():
    """Aiming at a boundary must not stretch the connection open."""
    for micros in (0, 1, 500_000, 999_999):
        when = dt.datetime(2026, 8, 23, 12, 0, 0, micros, tzinfo=UTC)
        _result, clock, _ = await _run(when, 0.0)
        assert clock.t - 1000.0 <= 1.0


@pytest.mark.asyncio
async def test_written_time_is_never_behind_the_sample():
    """Rounding down used to be half the error; aiming forward cannot."""
    for micros in (0, 300_000, 800_000):
        when = dt.datetime(2026, 8, 23, 12, 0, 0, micros, tzinfo=UTC)
        result, _clock, _ = await _run(when, 0.6)
        assert result.written_epoch >= when.timestamp()


@pytest.mark.asyncio
async def test_slow_link_does_not_trip_the_verify():
    """Read-back is compared with the current time, not with what was written —
    otherwise the device ticking during the round trip looks like a mismatch."""
    when = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    clock = _Clock(step=1.5)  # 4.5 s across three round trips
    client = _client(clock, when)

    result = await Lywsd02mmc().set_time(client, when, 9, monotonic=clock, sleeper=clock.sleep)
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
        await Lywsd02mmc().set_time(client, when, 9, monotonic=clock, sleeper=clock.sleep)


@pytest.mark.asyncio
async def test_drift_is_measured_against_the_same_instant():
    """The device value is from mid-round-trip; comparing it with the sampling
    instant would report the link latency as clock drift."""
    when = dt.datetime(2026, 8, 23, 12, 0, 0, tzinfo=UTC)
    clock = _Clock(step=1.0)
    client = _client(clock, when)  # device is perfectly in sync

    result = await Lywsd02mmc().set_time(client, when, 9, monotonic=clock, sleeper=clock.sleep)
    assert abs(result.drift_seconds) <= 0.5
