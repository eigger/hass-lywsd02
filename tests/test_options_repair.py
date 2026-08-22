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
