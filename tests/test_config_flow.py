"""Config flow tests."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest

from custom_components.xiaomi_lywsd.config_flow import LywsdConfigFlow, MAC_RE
from homeassistant.const import CONF_ADDRESS

MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "custom_components",
    "xiaomi_lywsd",
    "manifest.json",
)


def _discovery(address: str, name: str):
    info = MagicMock()
    info.address = address
    info.name = name
    return info


def test_manifest_local_name_matcher():
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        manifest = json.load(f)
    matchers = manifest.get("bluetooth", [])
    assert matchers, "bluetooth matchers should be populated (T3)"
    for entry in matchers:
        local_name = entry["local_name"]
        assert local_name[:3].find("*") == -1
        assert entry.get("connectable") is True


@pytest.mark.asyncio
async def test_bluetooth_supported():
    flow = LywsdConfigFlow()
    result = await flow.async_step_bluetooth(_discovery("AA:BB:CC:DD:EE:01", "LYWSD02MMC"))
    assert result["type"] == "form"
    assert result["step_id"] == "bluetooth_confirm"


@pytest.mark.asyncio
async def test_bluetooth_not_supported():
    flow = LywsdConfigFlow()
    result = await flow.async_step_bluetooth(_discovery("AA:BB:CC:DD:EE:02", "LYWSD03MMC"))
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


@pytest.mark.asyncio
async def test_manual_valid_mac_normalized():
    flow = LywsdConfigFlow()
    result = await flow.async_step_manual({CONF_ADDRESS: "aa:bb:cc:dd:ee:ff"})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"
    assert result["title"].startswith("LYWSD02 ")


@pytest.mark.asyncio
async def test_manual_invalid_mac():
    flow = LywsdConfigFlow()
    result = await flow.async_step_manual({CONF_ADDRESS: "not-a-mac"})
    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_mac"


def test_mac_regex():
    assert MAC_RE.match("AA:BB:CC:DD:EE:FF")
    assert MAC_RE.match("aa:bb:cc:dd:ee:ff")
    assert not MAC_RE.match("AABBCCDDEEFF")
    assert not MAC_RE.match("AA:BB:CC:DD:EE")


@pytest.mark.asyncio
async def test_user_empty_goes_to_manual():
    flow = LywsdConfigFlow()
    with patch(
        "custom_components.xiaomi_lywsd.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await flow.async_step_user()
    assert result["type"] == "form"
    assert result["step_id"] == "manual"
