"""Ensure strings.json / en.json / ko.json / icons.json stay in step."""

from __future__ import annotations

import json
import os

COMPONENT_DIR = os.path.join(
    os.path.dirname(__file__), "..", "custom_components", "xiaomi_lywsd"
)
STRINGS_PATH = os.path.join(COMPONENT_DIR, "strings.json")
EN_PATH = os.path.join(COMPONENT_DIR, "translations", "en.json")
KO_PATH = os.path.join(COMPONENT_DIR, "translations", "ko.json")
ICONS_PATH = os.path.join(COMPONENT_DIR, "icons.json")


def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _keys(obj, prefix=""):
    out: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            out.add(path)
            out |= _keys(value, path)
    return out


def test_translation_key_sets_match():
    strings = _load(STRINGS_PATH)
    en = _load(EN_PATH)
    ko = _load(KO_PATH)
    sk, ek, kk = _keys(strings), _keys(en), _keys(ko)
    assert sk == ek, f"en missing {sk - ek}, extra {ek - sk}"
    assert sk == kk, f"ko missing {sk - kk}, extra {kk - sk}"


def test_every_named_entity_has_an_icon():
    """A new entity with no icons.json entry falls back to the generic dot.

    Nothing else catches that: the entity works, the name is translated, and
    only a look at the device page shows it. Device classes supply their own
    icon, but the diagnostics here mostly have none.
    """
    named = _load(STRINGS_PATH)["entity"]
    icons = _load(ICONS_PATH)["entity"]
    for platform, entities in named.items():
        missing = set(entities) - set(icons.get(platform, {}))
        assert not missing, f"{platform} entities without an icon: {missing}"
        extra = set(icons.get(platform, {})) - set(entities)
        assert not extra, f"{platform} icons for unknown entities: {extra}"


def test_json_files_valid():
    for path in (STRINGS_PATH, EN_PATH, KO_PATH, ICONS_PATH):
        assert isinstance(_load(path), dict)
