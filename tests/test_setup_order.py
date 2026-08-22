"""Setup order: the schedule must be armed before entities exist."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

import pytest

from custom_components.xiaomi_lywsd import async_setup_entry
from custom_components.xiaomi_lywsd.const import CONF_AUTO_SYNC


@pytest.mark.asyncio
async def test_schedule_is_armed_before_platforms_are_forwarded():
    """next_sync is entity state now. If the timer were armed afterwards, every
    restart would publish "unknown / off" first and correct it a moment later —
    enough to trip an automation watching for sync being turned off."""
    address = "AA:BB:CC:DD:EE:FF"
    entry = MagicMock()
    entry.entry_id = "entry-order"
    entry.unique_id = address
    entry.data = {"address": address}
    entry.options = {CONF_AUTO_SYNC: "30"}
    entry.async_on_unload = MagicMock()

    hass = MagicMock()
    hass.data = {}
    seen: dict = {}

    async def forward(entry_arg, _platforms):
        coord = entry_arg.runtime_data
        seen["next_sync"] = coord.data.next_sync
        seen["mode"] = coord.data.auto_sync_mode

    hass.config_entries.async_forward_entry_setups = forward

    now = dt.datetime(2026, 6, 1, tzinfo=dt.timezone.utc)
    with patch("custom_components.xiaomi_lywsd.dr.async_get"), patch(
        "custom_components.xiaomi_lywsd.async_track_point_in_time"
    ), patch("custom_components.xiaomi_lywsd.dt_util.now", return_value=now), patch(
        "custom_components.xiaomi_lywsd._async_maybe_create_proxy_issues"
    ), patch("custom_components.xiaomi_lywsd._async_register_services"):
        assert await async_setup_entry(hass, entry) is True

    assert seen["next_sync"] is not None, "entities saw an unscheduled coordinator"
    assert seen["mode"] == "30"
