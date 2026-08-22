"""Constants for the Xiaomi LYWSD integration."""

from __future__ import annotations

DOMAIN = "xiaomi_lywsd"
LOCK = "lock"

CONF_RETRY_COUNT = "retry_count"
CONF_AUTO_SYNC_HOURS = "auto_sync_hours"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_CLIMATE_SENSORS = "climate_sensors"

DEFAULT_RETRY_COUNT = 3
DEFAULT_AUTO_SYNC_HOURS = 24
DEFAULT_SCAN_INTERVAL = 1800
DEFAULT_CLIMATE_SENSORS = True
MIN_SCAN_INTERVAL = 120

MANUFACTURER = "Xiaomi"
MODEL = "LYWSD02MMC"
