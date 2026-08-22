"""Constants for the Xiaomi LYWSD integration."""

from __future__ import annotations

DOMAIN = "xiaomi_lywsd"
LOCK = "lock"

CONF_RETRY_COUNT = "retry_count"
CONF_AUTO_SYNC_HOURS = "auto_sync_hours"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CLIMATE_SENSORS = "climate_sensors"

DEFAULT_RETRY_COUNT = 3
DEFAULT_AUTO_SYNC_HOURS = 0
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
