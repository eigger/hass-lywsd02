"""Auto-sync option and proxy repair issue tests."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

from custom_components.xiaomi_lywsd import (
    _async_maybe_create_proxy_issues,
    _async_setup_auto_sync,
)
from custom_components.xiaomi_lywsd.const import CONF_AUTO_SYNC_HOURS


def test_auto_sync_disabled_registers_nothing():
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {}
    entry.options = {CONF_AUTO_SYNC_HOURS: 0}
    entry.async_on_unload = MagicMock()

    with patch(
        "custom_components.xiaomi_lywsd.async_track_time_interval"
    ) as track:
        _async_setup_auto_sync(hass, entry)
        track.assert_not_called()
        entry.async_on_unload.assert_not_called()


def test_auto_sync_registers_interval_and_unload():
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {}
    entry.options = {CONF_AUTO_SYNC_HOURS: 24}
    entry.async_on_unload = MagicMock()
    unsub = MagicMock()

    with patch(
        "custom_components.xiaomi_lywsd.async_track_time_interval",
        return_value=unsub,
    ) as track:
        _async_setup_auto_sync(hass, entry)
        track.assert_called_once()
        assert track.call_args.args[2] == timedelta(hours=24)
        entry.async_on_unload.assert_called_once_with(unsub)


def test_proxy_issue_no_scanner():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "e1"

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=0,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch("custom_components.xiaomi_lywsd.async_create_issue") as create,
    ):
        _async_maybe_create_proxy_issues(hass, entry, "AA:BB:CC:DD:EE:FF")
        create.assert_called_once()
        assert create.call_args.kwargs["translation_key"] == "no_connectable_scanner"


def test_proxy_issue_not_active():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "e1"
    passive = MagicMock()

    def _ble(hass, address, connectable=False):
        return None if connectable else passive

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            side_effect=_ble,
        ),
        patch("custom_components.xiaomi_lywsd.async_create_issue") as create,
    ):
        _async_maybe_create_proxy_issues(hass, entry, "AA:BB:CC:DD:EE:FF")
        create.assert_called_once()
        assert create.call_args.kwargs["translation_key"] == "proxy_not_active"


def test_proxy_issue_connectable_ok():
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "e1"

    with (
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_scanner_count",
            return_value=1,
        ),
        patch(
            "custom_components.xiaomi_lywsd.bluetooth.async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch("custom_components.xiaomi_lywsd.async_create_issue") as create,
    ):
        _async_maybe_create_proxy_issues(hass, entry, "AA:BB:CC:DD:EE:FF")
        create.assert_not_called()
