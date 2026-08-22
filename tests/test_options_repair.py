"""Auto-sync option and proxy repair issue tests."""

from __future__ import annotations

import datetime as dt
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from custom_components.xiaomi_lywsd import (
    _async_maybe_create_proxy_issues,
    _async_setup_auto_sync,
)
from custom_components.xiaomi_lywsd.const import (
    AUTO_SYNC_RETRY_BASE_SECONDS,
    CONF_AUTO_SYNC,
    CONF_AUTO_SYNC_TOLERANCE,
    STARTUP_SYNC_DELAY_SECONDS,
)
from custom_components.xiaomi_lywsd.coordinator import LywsdData


def _auto_sync_entry(options: dict) -> MagicMock:
    """Config entry whose runtime_data exposes just what the scheduler reads."""
    entry = MagicMock()
    entry.data = {}
    entry.options = options
    entry.async_on_unload = MagicMock()
    coordinator = MagicMock()
    coordinator.data = LywsdData()
    coordinator.address = "AA:BB:CC:DD:EE:FF"
    coordinator.reschedule_auto_sync = None
    entry.runtime_data = coordinator
    return entry


def test_auto_sync_disabled_registers_nothing():
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "0"})

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track:
        _async_setup_auto_sync(hass, entry)
        track.assert_not_called()
        entry.async_on_unload.assert_not_called()
        assert entry.runtime_data.data.next_sync is None


def test_auto_sync_schedules_from_persisted_last_sync():
    """The interval must survive a restart, not restart its countdown."""
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "30"})
    entry.runtime_data.data.last_sync = dt.datetime(
        2026, 1, 1, tzinfo=dt.timezone.utc
    )
    now = dt.datetime(2026, 1, 20, tzinfo=dt.timezone.utc)

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track, patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ):
        _async_setup_auto_sync(hass, entry)

    when = track.call_args.args[2]
    # 19 days already elapsed before the restart — 11 days left, not 30.
    assert when == dt.datetime(2026, 1, 31, tzinfo=dt.timezone.utc)
    assert entry.runtime_data.data.next_sync == when
    entry.async_on_unload.assert_called_once()


def test_auto_sync_overdue_fires_shortly_after_startup():
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "30"})
    entry.runtime_data.data.last_sync = dt.datetime(
        2025, 1, 1, tzinfo=dt.timezone.utc
    )
    now = dt.datetime(2026, 1, 20, tzinfo=dt.timezone.utc)

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track, patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ):
        _async_setup_auto_sync(hass, entry)

    when = track.call_args.args[2]
    assert when == now + timedelta(seconds=STARTUP_SYNC_DELAY_SECONDS)


def test_auto_sync_never_synced_fires_shortly_after_startup():
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "180"})
    now = dt.datetime(2026, 1, 20, tzinfo=dt.timezone.utc)

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track, patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ):
        _async_setup_auto_sync(hass, entry)

    assert track.call_args.args[2] == now + timedelta(
        seconds=STARTUP_SYNC_DELAY_SECONDS
    )


def test_auto_sync_adaptive_uses_observed_drift():
    hass = MagicMock()
    entry = _auto_sync_entry(
        {CONF_AUTO_SYNC: "auto", CONF_AUTO_SYNC_TOLERANCE: 60}
    )
    entry.runtime_data.data.last_sync = dt.datetime(
        2026, 1, 1, tzinfo=dt.timezone.utc
    )
    # 6 s/day of drift against a 60 s budget -> 10 days.
    entry.runtime_data.data.drift_rate_per_day = 6.0
    now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track, patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ):
        _async_setup_auto_sync(hass, entry)

    assert track.call_args.args[2] == dt.datetime(
        2026, 1, 11, tzinfo=dt.timezone.utc
    )


def test_proxy_issue_no_scanner():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "e1"

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=0,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch("custom_components.xiaomi_lywsd.async_create_issue") as create,
    ):
        _async_maybe_create_proxy_issues(hass, entry, "AA:BB:CC:DD:EE:FF")
        create.assert_called_once()
        assert create.call_args.kwargs["translation_key"] == "no_connectable_scanner"


def test_proxy_issue_not_active():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "e1"
    passive = MagicMock()

    def _ble(hass, address, connectable=False):
        return None if connectable else passive

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            side_effect=_ble,
        ),
        patch("custom_components.xiaomi_lywsd.async_create_issue") as create,
    ):
        _async_maybe_create_proxy_issues(hass, entry, "AA:BB:CC:DD:EE:FF")
        create.assert_called_once()
        assert create.call_args.kwargs["translation_key"] == "proxy_not_active"


def test_proxy_issue_connectable_ok():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "e1"

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch("custom_components.xiaomi_lywsd.async_create_issue") as create,
    ):
        _async_maybe_create_proxy_issues(hass, entry, "AA:BB:CC:DD:EE:FF")
        create.assert_not_called()


@pytest.mark.asyncio
async def test_auto_sync_backs_off_after_failures():
    """A device out of range must not be retried every startup-delay."""
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "30"})
    coordinator = entry.runtime_data
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    now = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)

    async def failing_sync(_hass, _entry):
        coordinator.data.consecutive_auto_failures += 1

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track, patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ), patch(
        "custom_components.xiaomi_lywsd._run_auto_sync", new=failing_sync
    ):
        _async_setup_auto_sync(hass, entry)
        fire = track.call_args.args[1]
        await fire(now)
        first_retry = track.call_args.args[2]
        await fire(now)
        second_retry = track.call_args.args[2]

    assert first_retry == now + timedelta(seconds=AUTO_SYNC_RETRY_BASE_SECONDS)
    assert second_retry == now + timedelta(
        seconds=AUTO_SYNC_RETRY_BASE_SECONDS * 2
    )


def test_next_sync_is_published_to_listeners():
    """Entities are already up when setup arms the timer, so it must notify."""
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "7"})
    coordinator = entry.runtime_data
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)

    with patch("custom_components.xiaomi_lywsd.async_track_point_in_time"), patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ):
        _async_setup_auto_sync(hass, entry)

    assert coordinator.data.next_sync == dt.datetime(
        2026, 1, 8, tzinfo=dt.timezone.utc
    )
    coordinator.async_update_listeners.assert_called()


def _next_sync_sensor(coordinator):
    from custom_components.xiaomi_lywsd.sensor import DIAGNOSTIC_SENSORS, LywsdSensor

    desc = next(d for d in DIAGNOSTIC_SENSORS if d.key == "next_sync")
    return LywsdSensor(coordinator, desc)


def test_next_sync_sensor_reports_off_when_disabled():
    """Empty state must not be left to interpretation."""
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "0"})
    coordinator = entry.runtime_data

    with patch("custom_components.xiaomi_lywsd.async_track_point_in_time"):
        _async_setup_auto_sync(hass, entry)

    sensor = _next_sync_sensor(coordinator)
    assert sensor.native_value is None
    attrs = sensor.extra_state_attributes
    assert attrs["auto_sync"] == "off"
    assert attrs["interval_days"] is None


def test_next_sync_sensor_reports_fixed_interval():
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "30"})
    coordinator = entry.runtime_data
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)

    with patch("custom_components.xiaomi_lywsd.async_track_point_in_time"), patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ):
        _async_setup_auto_sync(hass, entry)

    sensor = _next_sync_sensor(coordinator)
    assert sensor.native_value == dt.datetime(2026, 1, 31, tzinfo=dt.timezone.utc)
    attrs = sensor.extra_state_attributes
    assert attrs["auto_sync"] == "30"
    assert attrs["interval_days"] == 30.0


def test_next_sync_sensor_reports_adaptive_interval_and_rate():
    hass = MagicMock()
    entry = _auto_sync_entry(
        {CONF_AUTO_SYNC: "auto", CONF_AUTO_SYNC_TOLERANCE: 60}
    )
    coordinator = entry.runtime_data
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    coordinator.data.drift_rate_per_day = 3.0  # 60 / 3 -> 20 days
    now = dt.datetime(2026, 1, 2, tzinfo=dt.timezone.utc)

    with patch("custom_components.xiaomi_lywsd.async_track_point_in_time"), patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ):
        _async_setup_auto_sync(hass, entry)

    sensor = _next_sync_sensor(coordinator)
    assert sensor.native_value == dt.datetime(2026, 1, 21, tzinfo=dt.timezone.utc)
    attrs = sensor.extra_state_attributes
    assert attrs["auto_sync"] == "auto"
    assert attrs["interval_days"] == 20.0
    assert attrs["drift_seconds_per_day"] == 3.0


@pytest.mark.asyncio
async def test_backoff_retry_does_not_shrink_the_reported_interval():
    """A retry is not a schedule change — the sensor must keep showing the
    configured cadence."""
    hass = MagicMock()
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "30"})
    coordinator = entry.runtime_data
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc)
    now = dt.datetime(2026, 3, 1, tzinfo=dt.timezone.utc)

    async def failing_sync(_hass, _entry):
        coordinator.data.consecutive_auto_failures += 1

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track, patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ), patch(
        "custom_components.xiaomi_lywsd._run_auto_sync", new=failing_sync
    ):
        _async_setup_auto_sync(hass, entry)
        await track.call_args.args[1](now)

    sensor = _next_sync_sensor(coordinator)
    assert sensor.extra_state_attributes["interval_days"] == 30.0
    # …while next_sync itself is the near-term retry.
    assert sensor.native_value == now + timedelta(
        seconds=AUTO_SYNC_RETRY_BASE_SECONDS
    )


@pytest.mark.asyncio
async def test_next_sync_always_equals_the_time_actually_scheduled():
    """The sensor is the real firing time in every mode, or unknown when off.

    Not the configured cadence, not last_sync + interval computed twice — the
    exact instant handed to async_track_point_in_time.
    """
    now = dt.datetime(2026, 6, 1, 12, 0, tzinfo=dt.timezone.utc)
    long_ago = dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc)
    recent = dt.datetime(2026, 5, 20, 12, 0, tzinfo=dt.timezone.utc)

    cases = [
        ("never synced", {CONF_AUTO_SYNC: "30"}, None),
        ("overdue at startup", {CONF_AUTO_SYNC: "7"}, long_ago),
        ("fixed interval", {CONF_AUTO_SYNC: "30"}, recent),
        (
            "adaptive",
            {CONF_AUTO_SYNC: "auto", CONF_AUTO_SYNC_TOLERANCE: 60},
            recent,
        ),
    ]

    for label, options, last_sync in cases:
        entry = _auto_sync_entry(options)
        coordinator = entry.runtime_data
        coordinator.data.last_sync = last_sync
        coordinator.data.drift_rate_per_day = 3.0

        with patch(
            "custom_components.xiaomi_lywsd.async_track_point_in_time"
        ) as track, patch(
            "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
        ):
            _async_setup_auto_sync(MagicMock(), entry)

        scheduled = track.call_args.args[2]
        assert coordinator.data.next_sync == scheduled, label
        assert scheduled.tzinfo is not None, label  # timestamp device_class

    # …and a failure retry is also the real next firing, not the cadence.
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "30"})
    coordinator = entry.runtime_data
    coordinator.data.last_sync = recent

    async def failing_sync(_hass, _entry):
        coordinator.data.consecutive_auto_failures += 1

    with patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ) as track, patch(
        "custom_components.xiaomi_lywsd.dt_util.now", return_value=now
    ), patch("custom_components.xiaomi_lywsd._run_auto_sync", new=failing_sync):
        _async_setup_auto_sync(MagicMock(), entry)
        await track.call_args.args[1](now)

    assert coordinator.data.next_sync == track.call_args.args[2]

    # Off is the one case with no time at all.
    entry = _auto_sync_entry({CONF_AUTO_SYNC: "0"})
    with patch("custom_components.xiaomi_lywsd.async_track_point_in_time") as track:
        _async_setup_auto_sync(MagicMock(), entry)
    track.assert_not_called()
    assert entry.runtime_data.data.next_sync is None
