"""Device layer — GATT encoding without Home Assistant imports."""

from __future__ import annotations

from .base import (
    ClimateReading,
    LywsdDevice,
    LywsdDeviceError,
    LywsdVerifyError,
    SyncResult,
)
from .lywsd02mmc import Lywsd02mmc

_MODELS: dict[str, type[LywsdDevice]] = {
    "LYWSD02": Lywsd02mmc,
    "LYWSD02MMC": Lywsd02mmc,
}


def device_for(local_name: str | None) -> type[LywsdDevice] | None:
    """Map advertisement local_name to a device class. Unknown → None."""
    if not local_name:
        return None
    name = local_name.strip().upper()
    for key, cls in sorted(_MODELS.items(), key=lambda item: -len(item[0])):
        if name == key or name.startswith(key):
            return cls
    return None


__all__ = [
    "ClimateReading",
    "LywsdDevice",
    "LywsdDeviceError",
    "LywsdVerifyError",
    "SyncResult",
    "Lywsd02mmc",
    "device_for",
]
