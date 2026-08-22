"""Regression tests for service target extraction across HA versions."""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock

import custom_components.xiaomi_lywsd as integ
from custom_components.xiaomi_lywsd import _extract_referenced_entities


def test_helpers_service_does_not_expose_moved_symbol():
    """Guard against MagicMock hiding ImportError for moved helpers."""
    import homeassistant.helpers.service as ha_service

    assert type(ha_service) is types.ModuleType
    assert not hasattr(ha_service, "async_extract_referenced_entity_ids")


def test_extract_uses_helpers_target_api():
    call = MagicMock()
    call.data = {"entity_id": "button.lywsd_sync", "device_id": ["dev1"]}
    selected = _extract_referenced_entities(MagicMock(), call)
    assert "button.lywsd_sync" in selected.referenced
    assert "dev1" in selected.referenced_devices


def test_extract_falls_back_to_legacy_service_api(monkeypatch):
    """Old HA path: helpers.service.async_extract_referenced_entity_ids(hass, call)."""
    selected_obj = types.SimpleNamespace(
        referenced={"button.x"},
        indirectly_referenced=set(),
        referenced_devices=set(),
    )

    def legacy_extract(hass, call):
        return selected_obj

    # Empty target module → AttributeError on TargetSelection → legacy path.
    fake_target = types.ModuleType("homeassistant.helpers.target")
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.target", fake_target)
    monkeypatch.setattr(
        sys.modules["homeassistant.helpers"], "target", fake_target, raising=False
    )
    monkeypatch.setattr(
        sys.modules["homeassistant.helpers.service"],
        "async_extract_referenced_entity_ids",
        legacy_extract,
        raising=False,
    )

    call = MagicMock()
    call.data = {"entity_id": "button.x"}
    selected = integ._extract_referenced_entities(MagicMock(), call)
    assert "button.x" in selected.referenced
