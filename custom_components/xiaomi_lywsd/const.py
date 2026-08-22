"""Constants for the Xiaomi LYWSD integration."""

from __future__ import annotations

DOMAIN = "xiaomi_lywsd"
LOCK = "lock"
STORAGE_VERSION = 1

MANUFACTURER = "Xiaomi"
MODEL = "LYWSD02MMC"

# ── Options ──────────────────────────────────────────────────────────────────
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CLIMATE_SENSORS = "climate_sensors"
CONF_RETRY_COUNT = "retry_count"
CONF_AUTO_SYNC = "auto_sync"
CONF_AUTO_SYNC_TOLERANCE = "auto_sync_tolerance"
# 0.1.x option, converted once by async_migrate_entry and never read at runtime.
CONF_AUTO_SYNC_HOURS_V1 = "auto_sync_hours"

DEFAULT_RETRY_COUNT = 3

# ── Climate polling ──────────────────────────────────────────────────────────
# Off by default: the clock is the point of this integration, and every poll
# opens a BLE session on a CR2032 device. Interval is stored/shown in minutes.
DEFAULT_CLIMATE_SENSORS = False
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 2
MAX_SCAN_INTERVAL = 60

# ── Automatic clock sync ─────────────────────────────────────────────────────
# Stored as a string so the fixed day counts and "auto" share one dropdown.
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

# ── Display ──────────────────────────────────────────────────────────────────
TIME_FORMAT_12H = "12h"
TIME_FORMAT_24H = "24h"
TIME_FORMAT_OPTIONS = (TIME_FORMAT_12H, TIME_FORMAT_24H)


def scan_interval_minutes(raw: int | None) -> int:
    """Clamp the stored poll interval to the offered range."""
    if raw is None:
        return DEFAULT_SCAN_INTERVAL
    try:
        minutes = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_SCAN_INTERVAL
    return max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, minutes))


def scan_interval_seconds(raw: int | None) -> int:
    """Poll interval in seconds."""
    return scan_interval_minutes(raw) * 60


def auto_sync_choice(options: dict) -> str:
    """Return the auto-sync option, falling back to the default.

    Entries created before 0.2.0 are stamped with an explicit value by
    ``async_migrate_entry``, so an absent key here always means a 0.2 entry
    that has not been configured — never a 0.1.x install that had sync off.
    """
    value = str(options.get(CONF_AUTO_SYNC, DEFAULT_AUTO_SYNC))
    return value if value in AUTO_SYNC_CHOICES else DEFAULT_AUTO_SYNC


def auto_sync_tolerance_seconds(options: dict) -> int:
    """Clamp the adaptive-mode target error to a sane range."""
    raw = options.get(CONF_AUTO_SYNC_TOLERANCE, DEFAULT_AUTO_SYNC_TOLERANCE)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = DEFAULT_AUTO_SYNC_TOLERANCE
    return max(MIN_AUTO_SYNC_TOLERANCE, min(MAX_AUTO_SYNC_TOLERANCE, value))


def auto_sync_interval_days(
    choice: str, drift_rate_per_day: float | None, tolerance: int
) -> float:
    """Days between automatic syncs.

    Adaptive mode divides the tolerated error by the observed drift rate, so a
    clock that barely drifts stretches out to months while a sloppy one keeps a
    short cycle. Falls back to the bootstrap interval only while no rate has
    been measured yet.
    """
    if choice == AUTO_SYNC_ADAPTIVE:
        if drift_rate_per_day is None:
            # Nothing measured yet — two syncs are needed for a rate.
            days = AUTO_SYNC_BOOTSTRAP_DAYS
        else:
            rate = abs(drift_rate_per_day)
            # A measured zero means the clock held to within the device's
            # one-second resolution over the whole interval, which is the best
            # result there is. Treating it like "unknown" would put an accurate
            # clock on a shorter cycle than a slightly worse one.
            days = AUTO_SYNC_MAX_DAYS if rate < 1e-6 else tolerance / rate
    else:
        try:
            days = float(choice)
        except (TypeError, ValueError):
            days = AUTO_SYNC_BOOTSTRAP_DAYS
    return max(AUTO_SYNC_MIN_DAYS, min(AUTO_SYNC_MAX_DAYS, days))
