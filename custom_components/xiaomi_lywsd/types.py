"""Type aliases for the Xiaomi LYWSD integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import LywsdCoordinator

LywsdConfigEntry: TypeAlias = ConfigEntry["LywsdCoordinator"]
