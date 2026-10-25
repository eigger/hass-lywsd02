"""Drift-triggered sync: read the clock on the poll's connection, write on need.

The connection is what costs battery on a CR2032 device, not the exchange over
it — so these tests care as much about *how many connections* a decision takes
as about whether the clock ends up right.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.xiaomi_lywsd import (
    _auto_sync_interval,
    _clock_recently_verified,
    _run_auto_sync,
)
from custom_components.xiaomi_lywsd.coordinator import LywsdCoordinator
from custom_components.xiaomi_lywsd.device import Lywsd02mmc
from custom_components.xiaomi_lywsd.device.lywsd02mmc import (
    UUID_BATTERY,
    UUID_DATA,
    UUID_TIME,
    decode_time,
    encode_time,
)
from custom_components.xiaomi_lywsd.sensor import DIAGNOSTIC_SENSORS, LywsdSensor
from tests.components.xiaomi_lywsd.fake_client import FakeBleakClient
from tests.components.xiaomi_lywsd.stub_clock import StubClock

KST = dt.timezone(dt.timedelta(hours=9))
# A fraction just short of the next second keeps set_time's boundary wait — a
# real asyncio.sleep on this path — down to a few milliseconds.
NOW = dt.datetime(2026, 3, 1, 12, 0, 0, 990000, tzinfo=KST)


def _coord(hass, options: dict | None = None):
    hass.data = {"xiaomi_lywsd": {"lock": asyncio.Lock()}}
    entry = MagicMock()
    entry.entry_id = "drift"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    entry.options = {
        "scan_interval": 30,
        "retry_count": 1,
        "climate_sensors": True,
        **(options or {}),
    }
    entry.unique_id = "AA:BB:CC:DD:EE:FF"
    coord = LywsdCoordinator(
        hass,
        entry,
        "AA:BB:CC:DD:EE:FF",
        hass.data["xiaomi_lywsd"]["lock"],
        Lywsd02mmc(),
    )
    entry.runtime_data = coord
    return hass, entry, coord


def _client(device_offset: float, tz_hours: int = 9) -> FakeBleakClient:
    """Fake device whose clock sits ``device_offset`` seconds off NOW."""
    client = FakeBleakClient(
        {
            UUID_BATTERY: b"\x5a",
            UUID_TIME: encode_time(int(NOW.timestamp() + device_offset), tz_hours),
        },
        notify={UUID_DATA: b"\x1a\x09\x37"},
    )
    real_read = client.read_gatt_char
    client.reads: list[str] = []

    async def read(uuid):
        client.reads.append(str(uuid).lower())
        return await real_read(uuid)

    client.read_gatt_char = read
    return client


async def _poll(coord, client, now=NOW):
    ble = MagicMock()
    ble.address = "AA:BB:CC:DD:EE:FF"
    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=ble,
        ),
        patch(
            "custom_components.xiaomi_lywsd.close_stale_connections_by_address",
            new_callable=AsyncMock,
        ),
        patch(
            "custom_components.xiaomi_lywsd.establish_connection",
            new_callable=AsyncMock,
            return_value=client,
        ) as connect,
        patch(
            "custom_components.xiaomi_lywsd.coordinator.dt_util.now",
            return_value=now,
        ),
    ):
        data = await coord._async_update_data()
    return data, connect


def _time_writes(client) -> list[bytes]:
    return [
        payload for uuid, payload, _resp in client.writes if uuid == UUID_TIME.lower()
    ]


@pytest.mark.asyncio
async def test_poll_syncs_on_its_own_connection_when_drift_exceeds_tolerance(hass):
    """The whole point: the correction rides on the poll, not a second connect."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    client = _client(300.0)

    data, connect = await _poll(coord, client)

    written = _time_writes(client)
    assert len(written) == 1
    assert decode_time(written[0])[0] == pytest.approx(NOW.timestamp(), abs=2)
    # One connection for climate + battery + clock read + clock write.
    assert connect.await_count == 1
    assert data.last_sync == NOW
    assert data.clock_drift == pytest.approx(300.0, abs=1.0)
    # Climate still came back — the clock work must not displace the poll.
    assert data.temperature == pytest.approx(23.30)
    assert data.battery == 90


def _drift_sensor(coord) -> LywsdSensor:
    return LywsdSensor(
        coord, next(d for d in DIAGNOSTIC_SENSORS if d.key == "observed_drift")
    )


@pytest.mark.asyncio
async def test_drift_sensor_reports_the_measured_residual_after_a_sync(hass):
    """After a write the sensor must show what the read-back measured, not an
    assumed zero — the device stores whole seconds and rarely lands exactly."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    sensor = _drift_sensor(coord)
    assert sensor.available is False  # nothing measured yet

    data, _connect = await _poll(coord, _client(300.0))

    # The pre-write error is history; the sensor tracks the live one.
    assert data.clock_drift == pytest.approx(300.0, abs=1.0)
    assert abs(data.observed_drift) <= 2.0
    assert data.clock_checked == NOW
    assert sensor.available is True
    assert sensor.native_value == data.observed_drift
    assert sensor.extra_state_attributes == {"clock_checked": NOW}


@pytest.mark.asyncio
async def test_drift_sensor_tracks_the_error_between_syncs(hass):
    """The point of an entity over an attribute: successive polls are separate
    states, so a growing error is visible as history."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    seen = []
    for offset in (5.0, 12.0, 30.0):
        data, _connect = await _poll(coord, _client(offset))
        seen.append(data.observed_drift)
    assert seen == [
        pytest.approx(5.0, abs=1.5),
        pytest.approx(12.0, abs=1.5),
        pytest.approx(30.0, abs=1.5),
    ]
    assert seen[0] < seen[1] < seen[2]
    assert _drift_sensor(coord).native_value == seen[-1]


@pytest.mark.asyncio
async def test_a_poll_sync_feeds_the_rate_and_re_arms_the_schedule(hass):
    """A drift-triggered sync is a full sync: it measures a rate, and the next
    one is a fresh interval derived from that rate — not the leftover of the
    countdown it interrupted."""
    _hass, entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    coord.data.last_sync = NOW - dt.timedelta(days=10)
    rearmed = []
    coord.reschedule_auto_sync = lambda: rearmed.append(True)

    data, _connect = await _poll(coord, _client(300.0))

    # 300 s over 10 days, and 60 s of tolerance buys 2 days of it.
    assert data.drift_rate_per_day == pytest.approx(30.0, abs=0.5)
    assert data.last_sync == NOW
    assert rearmed == [True]
    options = {**entry.data, **entry.options}
    assert _auto_sync_interval(coord, options).total_seconds() / 86400.0 == (
        pytest.approx(2.0, abs=0.1)
    )


@pytest.mark.asyncio
async def test_poll_reads_the_clock_but_writes_nothing_within_tolerance(hass):
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    client = _client(10.0)

    data, _connect = await _poll(coord, client)

    assert _time_writes(client) == []
    assert UUID_TIME.lower() in client.reads
    assert data.observed_drift == pytest.approx(10.0, abs=1.0)
    assert data.clock_checked == NOW
    # Nothing was corrected, so the sync history must not claim otherwise.
    assert data.last_sync is None


@pytest.mark.asyncio
async def test_poll_resyncs_when_only_the_utc_offset_changed(hass):
    """A DST change moves the offset, not the epoch — drift alone misses it."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    client = _client(0.0, tz_hours=8)

    data, connect = await _poll(coord, client)

    written = _time_writes(client)
    assert len(written) == 1
    assert decode_time(written[0])[1] == 9
    assert connect.await_count == 1
    assert data.last_sync == NOW


@pytest.mark.asyncio
async def test_stale_offset_is_written_even_right_after_a_sync(hass):
    """The min-interval guard is for epoch errors, not a DST change."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    coord.data.last_sync = NOW - dt.timedelta(minutes=5)
    client = _client(0.0, tz_hours=8)

    await _poll(coord, client)

    assert len(_time_writes(client)) == 1


@pytest.mark.asyncio
async def test_device_that_ignores_the_offset_is_written_once_not_hourly(hass, caplog):
    """FakeBleakClient keeps reporting +8 after the write, like such firmware."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    client = _client(0.0, tz_hours=8)

    await _poll(coord, client)
    assert len(_time_writes(client)) == 1
    # The device's clock is right in UTC at each later poll; only its byte is.
    later = NOW + dt.timedelta(hours=2)
    client = _client(7200.0, tz_hours=8)
    await _poll(coord, client, later)
    assert _time_writes(client) == []
    assert "no longer checking the offset" in caplog.text

    client = _client(14400.0, tz_hours=8)
    await _poll(coord, client, later + dt.timedelta(hours=2))
    assert _time_writes(client) == []


@pytest.mark.asyncio
async def test_latch_clears_once_the_device_reports_the_right_offset(hass):
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    await _poll(coord, _client(0.0, tz_hours=8))
    await _poll(coord, _client(7200.0, tz_hours=8), NOW + dt.timedelta(hours=2))
    assert coord._tz_unsupported

    await _poll(coord, _client(14400.0, tz_hours=9), NOW + dt.timedelta(hours=4))
    assert not coord._tz_unsupported
    assert coord._tz_attempted is None

    client = _client(18000.0, tz_hours=8)
    await _poll(coord, client, NOW + dt.timedelta(hours=5))
    assert len(_time_writes(client)) == 1


@pytest.mark.asyncio
async def test_short_time_read_without_offset_byte_is_not_compared(hass):
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    client = _client(0.0)
    client._store[UUID_TIME.lower()] = int(NOW.timestamp()).to_bytes(4, "little")

    await _poll(coord, client)

    assert _time_writes(client) == []


@pytest.mark.asyncio
async def test_negative_half_hour_zone_matches_the_floored_offset(hass):
    """-3:30 floors to -4 on every write path, so a device holding -4 is fine."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    st_johns = dt.timezone(dt.timedelta(hours=-3, minutes=-30))
    now = NOW.astimezone(st_johns)
    client = _client(0.0, tz_hours=-4)

    await _poll(coord, client, now)

    assert _time_writes(client) == []


@pytest.mark.asyncio
async def test_poll_leaves_a_matching_offset_alone(hass):
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    client = _client(0.0, tz_hours=9)

    await _poll(coord, client)

    assert _time_writes(client) == []


@pytest.mark.asyncio
async def test_sync_is_not_repeated_every_poll_when_the_write_does_not_take(
    hass, caplog
):
    """A clock that stays wrong after a write is a firmware question, not a
    reason to burn the battery correcting it every poll."""
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    coord.data.last_sync = NOW - dt.timedelta(minutes=10)
    client = _client(32400.0)  # exactly one timezone away — the epoch hazard

    with caplog.at_level("WARNING"):
        data, _connect = await _poll(coord, client)

    assert _time_writes(client) == []
    assert data.observed_drift == pytest.approx(32400.0, abs=1.0)
    assert "not rewriting it every poll" in caplog.text

    # ...and the warning is not repeated on the next poll.
    caplog.clear()
    with caplog.at_level("WARNING"):
        await _poll(coord, _client(32400.0))
    assert "not rewriting it every poll" not in caplog.text


@pytest.mark.asyncio
async def test_clock_is_left_alone_when_automatic_sync_is_off(hass):
    _hass, _entry, coord = _coord(hass, {"auto_sync": "0"})
    client = _client(300.0)

    data, _connect = await _poll(coord, client)

    assert UUID_TIME.lower() not in client.reads
    assert _time_writes(client) == []
    assert data.observed_drift is None


@pytest.mark.asyncio
async def test_a_failed_clock_read_does_not_fail_the_poll(hass):
    _hass, _entry, coord = _coord(hass)
    # No UUID_TIME in the store — FakeBleakClient raises KeyError on read.
    client = FakeBleakClient(
        {UUID_BATTERY: b"\x5a"}, notify={UUID_DATA: b"\x1a\x09\x37"}
    )

    data, _connect = await _poll(coord, client)

    assert data.temperature == pytest.approx(23.30)
    assert data.observed_drift is None


@pytest.mark.asyncio
async def test_set_time_reuses_a_reading_instead_of_reading_twice(hass):
    """The poll decides from a reading; paying for a second one would waste the
    round trip the decision was made on."""
    device = Lywsd02mmc()
    client = _client(300.0)
    clock = StubClock(1000.0)

    reading = await device.get_time(client, NOW, monotonic=clock)
    before = len(client.reads)
    await device.set_time(client, NOW, 9, reading=reading, **clock.hooks)

    # Only the verify read-back, not another sample of the clock.
    assert len(client.reads) == before + 1
    assert reading.drift_seconds == pytest.approx(300.0, abs=1.0)


def test_recent_in_tolerance_reading_lets_a_scheduled_sync_stand_down(hass):
    _hass, _entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    options = {**_entry.data, **_entry.options}
    coord.data.clock_checked = NOW - dt.timedelta(minutes=5)
    coord.data.observed_drift = 12.0

    with patch("custom_components.xiaomi_lywsd.dt_util.now", return_value=NOW):
        assert _clock_recently_verified(coord, options) is True

        # Too close to the tolerance to be worth trusting until the next poll.
        coord.data.observed_drift = 45.0
        assert _clock_recently_verified(coord, options) is False

        # Comfortable, but measured two poll intervals ago.
        coord.data.observed_drift = 12.0
        coord.data.clock_checked = NOW - dt.timedelta(hours=2)
        assert _clock_recently_verified(coord, options) is False

    # Clock-only installs never poll, so there is nothing to stand down on.
    coord.data.clock_checked = NOW - dt.timedelta(minutes=5)
    with patch("custom_components.xiaomi_lywsd.dt_util.now", return_value=NOW):
        assert (
            _clock_recently_verified(coord, {**options, "climate_sensors": False})
            is False
        )


@pytest.mark.asyncio
async def test_scheduled_sync_skips_the_connection_after_a_clean_reading(hass):
    hass, entry, coord = _coord(hass, {"auto_sync_tolerance": 60})
    coord.data.clock_checked = NOW - dt.timedelta(minutes=5)
    coord.data.observed_drift = 3.0

    with (
        patch("custom_components.xiaomi_lywsd.dt_util.now", return_value=NOW),
        patch(
            "custom_components.xiaomi_lywsd.establish_connection",
            new_callable=AsyncMock,
        ) as connect,
    ):
        skipped = await _run_auto_sync(hass, entry)

    assert skipped is True
    connect.assert_not_awaited()
    assert coord.data.consecutive_auto_failures == 0
