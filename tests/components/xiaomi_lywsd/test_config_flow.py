"""Config flow tests."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch


from custom_components.xiaomi_lywsd.config_flow import MAC_RE
from homeassistant.const import CONF_ADDRESS
from homeassistant.config_entries import SOURCE_USER, SOURCE_BLUETOOTH
from custom_components.xiaomi_lywsd.const import DOMAIN

MANIFEST_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
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


async def test_bluetooth_supported(hass):
    with patch(
        "custom_components.xiaomi_lywsd.config_flow.onboarding.async_is_onboarded",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_BLUETOOTH},
            data=_discovery("AA:BB:CC:DD:EE:01", "LYWSD02MMC"),
        )
    assert result["type"] == "form"
    assert result["step_id"] == "bluetooth_confirm"


async def test_bluetooth_not_supported(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_BLUETOOTH},
        data=_discovery("AA:BB:CC:DD:EE:02", "LYWSD03MMC"),
    )
    assert result["type"] == "abort"
    assert result["reason"] == "not_supported"


async def _manual_flow(hass):
    with patch(
        "custom_components.xiaomi_lywsd.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        return await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )


async def test_manual_valid_mac_normalized(hass):
    result = await _manual_flow(hass)
    with patch("custom_components.xiaomi_lywsd.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_ADDRESS: "aa:bb:cc:dd:ee:ff"}
        )
        await hass.async_block_till_done()
    assert result["type"] == "create_entry"
    assert result["data"][CONF_ADDRESS] == "AA:BB:CC:DD:EE:FF"
    assert result["title"].startswith("LYWSD02 ")


async def test_manual_invalid_mac(hass):
    result = await _manual_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "not-a-mac"}
    )
    assert result["type"] == "form"
    assert result["errors"]["base"] == "invalid_mac"


async def test_manual_duplicate(hass, mock_config_entry):
    mock_config_entry.add_to_hass(hass)
    result = await _manual_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_ADDRESS: "aa:bb:cc:dd:ee:ff"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


def test_mac_regex():
    assert MAC_RE.match("AA:BB:CC:DD:EE:FF")
    assert MAC_RE.match("aa:bb:cc:dd:ee:ff")
    assert not MAC_RE.match("AABBCCDDEEFF")
    assert not MAC_RE.match("AA:BB:CC:DD:EE")


async def test_user_empty_goes_to_manual(hass):
    result = await _manual_flow(hass)
    assert result["type"] == "form"
    assert result["step_id"] == "manual"
