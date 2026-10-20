"""Entry migration: 0.1.x options must not change behaviour on upgrade."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from custom_components.xiaomi_lywsd import (
    _auto_sync_from_v1_hours,
    async_migrate_entry,
)
from custom_components.xiaomi_lywsd.const import (
    AUTO_SYNC_DISABLED,
    CONF_AUTO_SYNC,
    CONF_SCAN_INTERVAL,
    auto_sync_choice,
)


def _v1_entry(options: dict) -> MagicMock:
    entry = MagicMock()
    entry.entry_id = "entry-v1"
    entry.version = 1
    entry.options = options
    return entry


async def _migrate(entry) -> dict:
    hass = MagicMock()
    captured: dict = {}

    def update(_entry, **kwargs):
        captured.update(kwargs)

    hass.config_entries.async_update_entry = update
    assert await async_migrate_entry(hass, entry) is True
    return captured


@pytest.mark.asyncio
async def test_untouched_v1_install_stays_off():
    """0.1.x defaulted to off and stored nothing — the commonest upgrade."""
    captured = await _migrate(_v1_entry({}))

    assert captured["version"] == 2
    assert captured["options"][CONF_AUTO_SYNC] == AUTO_SYNC_DISABLED
    # And the stamped value is what the runtime then reads.
    assert auto_sync_choice(captured["options"]) == AUTO_SYNC_DISABLED


@pytest.mark.asyncio
async def test_v1_explicit_off_stays_off():
    captured = await _migrate(_v1_entry({"auto_sync_hours": 0}))
    assert captured["options"][CONF_AUTO_SYNC] == AUTO_SYNC_DISABLED
    assert "auto_sync_hours" not in captured["options"]


@pytest.mark.asyncio
async def test_v1_hours_become_day_choices():
    assert (await _migrate(_v1_entry({"auto_sync_hours": 24})))["options"][
        CONF_AUTO_SYNC
    ] == "1"
    assert (await _migrate(_v1_entry({"auto_sync_hours": 168})))["options"][
        CONF_AUTO_SYNC
    ] == "7"


@pytest.mark.asyncio
async def test_v1_scan_interval_seconds_become_minutes():
    captured = await _migrate(_v1_entry({CONF_SCAN_INTERVAL: 1800}))
    assert captured["options"][CONF_SCAN_INTERVAL] == 30


@pytest.mark.asyncio
async def test_v1_scan_interval_out_of_range_is_clamped():
    captured = await _migrate(_v1_entry({CONF_SCAN_INTERVAL: 7200}))
    assert captured["options"][CONF_SCAN_INTERVAL] == 60


@pytest.mark.asyncio
async def test_already_migrated_entry_is_left_alone():
    entry = _v1_entry({})
    entry.version = 2
    hass = MagicMock()
    assert await async_migrate_entry(hass, entry) is True
    hass.config_entries.async_update_entry.assert_not_called()


def test_v1_hours_mapping():
    assert _auto_sync_from_v1_hours(None) == AUTO_SYNC_DISABLED
    assert _auto_sync_from_v1_hours(0) == AUTO_SYNC_DISABLED
    assert _auto_sync_from_v1_hours("garbage") == AUTO_SYNC_DISABLED
    assert _auto_sync_from_v1_hours(24) == "1"
    assert _auto_sync_from_v1_hours(168) == "7"
    # Values the old UI never offered snap to the nearest choice.
    assert _auto_sync_from_v1_hours(24 * 45) == "30"


def test_fresh_02_entry_uses_the_new_default():
    """No key on a v2 entry means unconfigured, not legacy-off."""
    assert auto_sync_choice({}) == "auto"
