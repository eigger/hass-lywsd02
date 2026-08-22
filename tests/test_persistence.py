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
    CONF_AUTO_SYNC_HOURS,
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


def test_fixed_interval_choices_are_days():
    assert auto_sync_interval_days("30", 999.0, 60) == pytest.approx(30.0)


def test_legacy_hours_option_is_migrated():
    assert auto_sync_choice({CONF_AUTO_SYNC_HOURS: 0}) == "0"
    assert auto_sync_choice({CONF_AUTO_SYNC_HOURS: 24}) == "1"
    assert auto_sync_choice({CONF_AUTO_SYNC_HOURS: 168}) == "7"
    # An explicit new value always wins over the legacy key.
    assert (
        auto_sync_choice({CONF_AUTO_SYNC: "90", CONF_AUTO_SYNC_HOURS: 24}) == "90"
    )
    assert auto_sync_choice({}) == AUTO_SYNC_ADAPTIVE
