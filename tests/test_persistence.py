"""Persisted sync state and drift-rate derivation."""

from __future__ import annotations

import asyncio
import datetime as dt
from unittest.mock import MagicMock

import pytest

from custom_components.xiaomi_lywsd.const import (
    AUTO_SYNC_ADAPTIVE,
    AUTO_SYNC_MAX_DAYS,
    AUTO_SYNC_MIN_DAYS,
    CONF_AUTO_SYNC,
    auto_sync_choice,
    auto_sync_interval_days,
)
from custom_components.xiaomi_lywsd.coordinator import LywsdCoordinator
from custom_components.xiaomi_lywsd.device import Lywsd02mmc

UTC = dt.timezone.utc


def _coordinator(entry_id: str = "entry-persist") -> LywsdCoordinator:
    address = "AA:BB:CC:DD:EE:FF"
    entry = MagicMock()
    entry.entry_id = entry_id
    entry.data = {"address": address}
    entry.options = {"retry_count": 3, "scan_interval": 30}
    hass = MagicMock()
    lock = asyncio.Lock()
    hass.data = {"xiaomi_lywsd": {"lock": lock}}
    coordinator = LywsdCoordinator(hass, entry, address, lock, Lywsd02mmc())
    entry.runtime_data = coordinator
    return coordinator


@pytest.mark.asyncio
async def test_last_sync_survives_a_restart():
    first = _coordinator("entry-restart")
    synced_at = dt.datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    first.note_sync(-12.5, synced_at)
    first.data.units = "celsius"
    first.data.time_format = "24h"
    await first.async_save_persisted()

    # A fresh coordinator stands in for the process restart.
    second = _coordinator("entry-restart")
    assert second.data.last_sync is None
    await second.async_load_persisted()

    assert second.data.last_sync == synced_at
    assert second.data.clock_drift == -12.5
    assert second.data.units == "celsius"
    assert second.data.time_format == "24h"


@pytest.mark.asyncio
async def test_measured_drift_survives_a_restart():
    """A clock-only install measures drift once a sync — up to 180 days apart.
    An unknown drift sensor for months after every restart is worse than a
    value the attached timestamp lets the reader age for themselves."""
    first = _coordinator("entry-drift")
    measured_at = dt.datetime(2026, 3, 1, 9, 0, tzinfo=UTC)
    first.note_sync(-12.5, measured_at, 1.4, 0.5)
    await first.async_save_persisted()

    second = _coordinator("entry-drift")
    await second.async_load_persisted()

    assert second.data.observed_drift == 0.5
    assert second.data.clock_checked == measured_at


@pytest.mark.asyncio
async def test_load_without_stored_file_keeps_defaults():
    coordinator = _coordinator("entry-never-saved")
    await coordinator.async_load_persisted()
    assert coordinator.data.last_sync is None
    assert coordinator.data.drift_rate_per_day is None


def test_note_sync_derives_drift_rate():
    coordinator = _coordinator()
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=UTC)
    # 10 days later the clock had gained 50 s -> 5 s/day.
    coordinator.note_sync(50.0, dt.datetime(2026, 1, 11, tzinfo=UTC))
    assert coordinator.data.drift_rate_per_day == pytest.approx(5.0)
    assert coordinator.data.clock_drift == 50.0


def test_note_sync_ignores_samples_too_close_together():
    """Two syncs minutes apart say nothing about the daily rate."""
    coordinator = _coordinator()
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    coordinator.note_sync(3.0, dt.datetime(2026, 1, 1, 0, 5, tzinfo=UTC))
    assert coordinator.data.drift_rate_per_day is None


def test_note_sync_smooths_successive_rates():
    coordinator = _coordinator()
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=UTC)
    coordinator.note_sync(100.0, dt.datetime(2026, 1, 11, tzinfo=UTC))  # 10/day
    coordinator.note_sync(20.0, dt.datetime(2026, 1, 21, tzinfo=UTC))  # 2/day
    assert coordinator.data.drift_rate_per_day == pytest.approx(6.0)


def test_adaptive_interval_scales_with_drift():
    # Accurate clock -> long interval; sloppy clock -> short one.
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, 6.0, 60) == pytest.approx(10.0)
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, 2.0, 60) == pytest.approx(30.0)
    # 60 / 0.2 = 300 days, clamped to the ceiling.
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, 0.2, 60) == AUTO_SYNC_MAX_DAYS
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, 600.0, 60) == AUTO_SYNC_MIN_DAYS
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, 0.01, 60) == AUTO_SYNC_MAX_DAYS


def test_adaptive_interval_without_a_rate_uses_bootstrap():
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, None, 60) == pytest.approx(7.0)


def test_measured_zero_drift_earns_the_longest_interval():
    """A clock that held to within the device's 1 s resolution is the best
    case, not an unknown — it must not land on a shorter cycle than a worse
    clock (0.3 s/day already reaches the ceiling)."""
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, 0.0, 60) == AUTO_SYNC_MAX_DAYS
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, -0.0, 60) == AUTO_SYNC_MAX_DAYS
    # And still shorter than the ceiling once real drift shows up.
    assert auto_sync_interval_days(AUTO_SYNC_ADAPTIVE, 2.0, 60) < AUTO_SYNC_MAX_DAYS


def test_fixed_interval_choices_are_days():
    assert auto_sync_interval_days("30", 999.0, 60) == pytest.approx(30.0)


def test_auto_sync_choice_falls_back_to_default():
    assert auto_sync_choice({CONF_AUTO_SYNC: "90"}) == "90"
    assert auto_sync_choice({}) == AUTO_SYNC_ADAPTIVE
    assert auto_sync_choice({CONF_AUTO_SYNC: "nonsense"}) == AUTO_SYNC_ADAPTIVE


@pytest.mark.asyncio
async def test_battery_survives_a_restart():
    """A clock-only install may not poll for months; unknown until then is worse."""
    first = _coordinator("entry-battery")
    first.data.battery = 63
    await first.async_save_persisted()

    second = _coordinator("entry-battery")
    await second.async_load_persisted()
    assert second.data.battery == 63


def test_long_samples_keep_the_plain_average():
    """The weighting must not change what a normal automatic cycle does."""
    coordinator = _coordinator()
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=UTC)
    coordinator.note_sync(70.0, dt.datetime(2026, 1, 8, tzinfo=UTC))  # 10/day
    assert coordinator.data.drift_rate_per_day == pytest.approx(10.0)
    coordinator.note_sync(14.0, dt.datetime(2026, 1, 15, tzinfo=UTC))  # 2/day
    assert coordinator.data.drift_rate_per_day == pytest.approx(6.0)


def test_a_short_manual_sync_barely_moves_the_estimate():
    """12 hours of a 1-second clock is ±2 s/day of noise — it must not get the
    same say as a week of measurement."""
    coordinator = _coordinator()
    coordinator.data.drift_rate_per_day = 3.0
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, 0, 0, tzinfo=UTC)

    # A wildly wrong short reading: 4 s over 12 h reads as 8 s/day.
    coordinator.note_sync(4.0, dt.datetime(2026, 1, 1, 12, 0, tzinfo=UTC))

    # Old 50/50 blend would have landed on 5.5 and nearly halved the interval.
    assert coordinator.data.drift_rate_per_day == pytest.approx(3.18, abs=0.01)


def test_repeated_manual_syncs_cannot_run_away_with_the_estimate():
    coordinator = _coordinator()
    coordinator.data.drift_rate_per_day = 3.0
    when = dt.datetime(2026, 1, 1, tzinfo=UTC)
    coordinator.data.last_sync = when

    for _ in range(10):
        when += dt.timedelta(hours=13)
        coordinator.note_sync(5.0, when)  # ~9.2 s/day each time

    # Ten noisy presses drift the estimate but do not replace it.
    assert 3.0 < coordinator.data.drift_rate_per_day < 6.0


def test_sample_weight_rises_with_duration():
    """Same measured rate, different durations — the longer one moves more."""
    rates = []
    for hours, drift in ((12, 4.0), (72, 24.0), (168, 56.0)):  # all 8 s/day
        coordinator = _coordinator()
        coordinator.data.drift_rate_per_day = 3.0
        start = dt.datetime(2026, 1, 1, tzinfo=UTC)
        coordinator.data.last_sync = start
        coordinator.note_sync(drift, start + dt.timedelta(hours=hours))
        rates.append(coordinator.data.drift_rate_per_day)

    assert rates == sorted(rates)
    assert rates[-1] == pytest.approx(5.5)  # a full week is the plain average


def test_first_sample_is_taken_whatever_its_length():
    """With nothing to blend against, the only reading available is the estimate."""
    coordinator = _coordinator()
    coordinator.data.last_sync = dt.datetime(2026, 1, 1, tzinfo=UTC)
    coordinator.note_sync(4.0, dt.datetime(2026, 1, 1, 12, 0, tzinfo=UTC))
    assert coordinator.data.drift_rate_per_day == pytest.approx(8.0)
