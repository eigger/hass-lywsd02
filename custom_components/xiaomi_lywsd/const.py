"""Constants for the Xiaomi LYWSD integration."""

from __future__ import annotations

DOMAIN = "xiaomi_lywsd"
LOCK = "lock"

CONF_RETRY_COUNT = "retry_count"
CONF_AUTO_SYNC_HOURS = "auto_sync_hours"  # legacy (hours); migrated to CONF_AUTO_SYNC
CONF_AUTO_SYNC = "auto_sync"
CONF_AUTO_SYNC_TOLERANCE = "auto_sync_tolerance"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CLIMATE_SENSORS = "climate_sensors"

DEFAULT_RETRY_COUNT = 3
DEFAULT_AUTO_SYNC_HOURS = 0

# Auto sync is stored as a string so the dropdown and "auto" share one option.
AUTO_SYNC_DISABLED = "0"
AUTO_SYNC_ADAPTIVE = "auto"
AUTO_SYNC_CHOICES = ("0", "1", "7", "30", "90", "180", AUTO_SYNC_ADAPTIVE)
DEFAULT_AUTO_SYNC = AUTO_SYNC_ADAPTIVE
# Adaptive mode aims to keep the clock within this many seconds.
DEFAULT_AUTO_SYNC_TOLERANCE = 60
MIN_AUTO_SYNC_TOLERANCE = 10
MAX_AUTO_SYNC_TOLERANCE = 3600
# Used until two syncs have been observed and a drift rate is known.
AUTO_SYNC_BOOTSTRAP_DAYS = 7.0
AUTO_SYNC_MIN_DAYS = 1.0
AUTO_SYNC_MAX_DAYS = 180.0
# Two syncs closer together than this are too noisy to derive a rate from.
AUTO_SYNC_MIN_RATE_SAMPLE_DAYS = 0.5
# Grace period after startup before a due sync fires, so the Bluetooth stack
# and any ESPHome proxies have settled.
STARTUP_SYNC_DELAY_SECONDS = 60
# A device that is simply out of range must not be retried every minute for
# days on end — back off instead of burning the proxy and the log.
AUTO_SYNC_RETRY_BASE_SECONDS = 1800
AUTO_SYNC_RETRY_MAX_SECONDS = 21600

STORAGE_VERSION = 1

TIME_FORMAT_12H = "12h"
TIME_FORMAT_24H = "24h"
TIME_FORMAT_OPTIONS = (TIME_FORMAT_12H, TIME_FORMAT_24H)
# Stored / shown as minutes. Legacy option values were seconds (>= 120).
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_CLIMATE_SENSORS = False
MIN_SCAN_INTERVAL = 2
MAX_SCAN_INTERVAL = 60
# Values at or above this were saved as seconds before the minutes UI.
_LEGACY_SCAN_INTERVAL_SECONDS_FLOOR = 120

MANUFACTURER = "Xiaomi"
MODEL = "LYWSD02MMC"


def scan_interval_seconds(raw: int | None) -> int:
    """Convert option value to seconds.

    New installs store minutes (2–60). Older installs stored seconds (120–3600).
    """
    if raw is None:
        minutes = DEFAULT_SCAN_INTERVAL
    else:
        minutes = int(raw)
    if minutes >= _LEGACY_SCAN_INTERVAL_SECONDS_FLOOR:
        return max(_LEGACY_SCAN_INTERVAL_SECONDS_FLOOR, minutes)
    minutes = max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, minutes))
    return minutes * 60


def scan_interval_minutes_for_ui(raw: int | None) -> int:
    """Normalize stored option to minutes for the options form."""
    if raw is None:
        return DEFAULT_SCAN_INTERVAL
    value = int(raw)
    if value >= _LEGACY_SCAN_INTERVAL_SECONDS_FLOOR:
        return max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, value // 60))
    return max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, value))


def auto_sync_choice(options: dict) -> str:
    """Return the auto-sync option, migrating the legacy hours value.

    Old installs stored ``auto_sync_hours`` as 0 / 24 / 168.
    """
    raw = options.get(CONF_AUTO_SYNC)
    if raw is not None:
        value = str(raw)
        return value if value in AUTO_SYNC_CHOICES else DEFAULT_AUTO_SYNC

    legacy = options.get(CONF_AUTO_SYNC_HOURS)
    if legacy is None:
        return DEFAULT_AUTO_SYNC
    try:
        hours = int(legacy)
    except (TypeError, ValueError):
        return DEFAULT_AUTO_SYNC
    if hours <= 0:
        return AUTO_SYNC_DISABLED
    days = max(1, round(hours / 24))
    # Snap to the nearest offered choice rather than inventing a new one.
    numeric = [c for c in AUTO_SYNC_CHOICES if c not in (AUTO_SYNC_ADAPTIVE,)]
    return min(numeric, key=lambda c: abs(int(c) - days))


def auto_sync_tolerance_seconds(options: dict) -> int:
    """Clamp the adaptive-mode target error to a sane range."""
    raw = options.get(CONF_AUTO_SYNC_TOLERANCE, DEFAULT_AUTO_SYNC_TOLERANCE)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_AUTO_SYNC_TOLERANCE
    return max(MIN_AUTO_SYNC_TOLERANCE, min(MAX_AUTO_SYNC_TOLERANCE, value))


def auto_sync_interval_days(choice: str, drift_rate_per_day, tolerance: int) -> float:
    """Days between automatic syncs.

    Adaptive mode divides the tolerated error by the observed drift rate, so a
    clock that barely drifts stretches out to months while a sloppy one keeps a
    short cycle. Falls back to the bootstrap interval until a rate is known.
    """
    if choice == AUTO_SYNC_ADAPTIVE:
        rate = abs(drift_rate_per_day) if drift_rate_per_day else 0.0
        if rate < 1e-6:
            days = AUTO_SYNC_BOOTSTRAP_DAYS
        else:
            days = tolerance / rate
    else:
        try:
            days = float(choice)
        except (TypeError, ValueError):
            days = AUTO_SYNC_BOOTSTRAP_DAYS
    return max(AUTO_SYNC_MIN_DAYS, min(AUTO_SYNC_MAX_DAYS, days))
