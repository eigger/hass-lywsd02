"""pytest harness — Home Assistant / bleak mocked so tests run without HA installed."""

from __future__ import annotations

import dataclasses
import sys
import types
from typing import Any
from unittest.mock import MagicMock


class MockBase:
    def __init__(self, *args, **kwargs):
        pass

    def __init_subclass__(cls, **kwargs):
        pass

    def __class_getitem__(cls, item):
        return cls


class MockConfigFlow(MockBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context: dict[str, Any] = {}
        self.hass = MagicMock()

    def _async_current_ids(self, include_ignore=True):
        return set()

    def async_show_form(self, **kwargs):
        return {"type": "form", **kwargs}

    def async_abort(self, **kwargs):
        return {"type": "abort", **kwargs}

    def async_create_entry(self, **kwargs):
        return {"type": "create_entry", **kwargs}

    async def async_set_unique_id(self, *args, **kwargs):
        pass

    def _abort_if_unique_id_configured(self):
        pass

    def _set_confirm_only(self):
        pass

    def add_suggested_values_to_schema(self, schema, suggested):
        return schema


def _make_entity_base(name: str):
    return type(name, (MockBase,), {})


async def _async_noop(*args, **kwargs):
    return None


@dataclasses.dataclass(frozen=True)
class _EntityDescriptionStub:
    key: str = ""
    translation_key: str | None = None
    icon: str | None = None
    entity_category: Any = None
    device_class: Any = None
    state_class: Any = None
    native_unit_of_measurement: str | None = None
    entity_registry_enabled_default: bool = True
    name: str | None = None
    has_entity_name: bool = False
    suggested_display_precision: int | None = None


class MockHomeAssistantError(Exception):
    """Real exception class so pytest.raises works."""


class MockServiceValidationError(Exception):
    pass


ha_exceptions = MagicMock()
ha_exceptions.HomeAssistantError = MockHomeAssistantError
ha_exceptions.ServiceValidationError = MockServiceValidationError
sys.modules["homeassistant.exceptions"] = ha_exceptions

sys.modules["homeassistant"] = MagicMock()
sys.modules["homeassistant.components"] = MagicMock()
sys.modules["homeassistant.components.onboarding"] = MagicMock()
sys.modules["homeassistant.components.bluetooth"] = MagicMock()
sys.modules["homeassistant.components.button"] = MagicMock()
sys.modules["homeassistant.components.select"] = MagicMock()
sys.modules["homeassistant.components.sensor"] = MagicMock()

ha_config_entries = MagicMock()
ha_config_entries.ConfigFlow = MockConfigFlow
ha_config_entries.OptionsFlowWithReload = MockConfigFlow
ha_config_entries.ConfigFlowResult = dict
ha_config_entries.ConfigEntry = MockBase
sys.modules["homeassistant.config_entries"] = ha_config_entries

ha_const = MagicMock()
ha_const.CONF_ADDRESS = "address"
ha_const.Platform = MagicMock()
ha_const.Platform.BUTTON = "button"
ha_const.Platform.SELECT = "select"
ha_const.Platform.SENSOR = "sensor"
ha_const.EntityCategory = MagicMock()
ha_const.EntityCategory.CONFIG = "config"
ha_const.EntityCategory.DIAGNOSTIC = "diagnostic"
ha_const.UnitOfTime = MagicMock()
ha_const.UnitOfTime.SECONDS = "s"
ha_const.UnitOfTemperature = MagicMock()
ha_const.UnitOfTemperature.CELSIUS = "°C"
ha_const.PERCENTAGE = "%"
sys.modules["homeassistant.const"] = ha_const

sys.modules["homeassistant.core"] = MagicMock()
sys.modules["homeassistant.helpers"] = MagicMock()
sys.modules["homeassistant.helpers.selector"] = MagicMock()
sys.modules["homeassistant.helpers.device_registry"] = MagicMock()
sys.modules["homeassistant.helpers.entity"] = MagicMock()
sys.modules["homeassistant.helpers.entity_platform"] = MagicMock()
sys.modules["homeassistant.helpers.event"] = MagicMock()
sys.modules["homeassistant.helpers.issue_registry"] = MagicMock()
sys.modules["homeassistant.helpers.restore_state"] = MagicMock()
sys.modules["homeassistant.helpers.update_coordinator"] = MagicMock()
sys.modules["homeassistant.util"] = MagicMock()
sys.modules["homeassistant.util.dt"] = MagicMock()

# Do NOT MagicMock helpers.service wholesale — that hides missing symbols and
# lets production code import names that do not exist on current HA cores.
_ha_service = types.ModuleType("homeassistant.helpers.service")
sys.modules["homeassistant.helpers.service"] = _ha_service


@dataclasses.dataclass
class _SelectedEntities:
    referenced: set = dataclasses.field(default_factory=set)
    indirectly_referenced: set = dataclasses.field(default_factory=set)
    referenced_devices: set = dataclasses.field(default_factory=set)


class _TargetSelection:
    def __init__(self, data: dict):
        self.data = data or {}


def _extract_from_selection(hass, selection, expand_group: bool = True):
    selected = _SelectedEntities()
    data = getattr(selection, "data", {}) or {}
    entity_ids = data.get("entity_id")
    if isinstance(entity_ids, str):
        selected.referenced.add(entity_ids)
    elif entity_ids:
        selected.referenced.update(entity_ids)
    device_ids = data.get("device_id")
    if isinstance(device_ids, str):
        selected.referenced_devices.add(device_ids)
    elif device_ids:
        selected.referenced_devices.update(device_ids)
    return selected


_ha_target = types.ModuleType("homeassistant.helpers.target")
_ha_target.TargetSelection = _TargetSelection
_ha_target.async_extract_referenced_entity_ids = _extract_from_selection
sys.modules["homeassistant.helpers.target"] = _ha_target

# Wire real submodules onto package MagicMocks. Otherwise
# `import homeassistant.helpers.service` walks attribute chains on the top-level
# MagicMock and gets child mocks (hasattr always True) instead of sys.modules.
_helpers = sys.modules["homeassistant.helpers"]
_helpers.service = _ha_service
_helpers.target = _ha_target
sys.modules["homeassistant"].helpers = _helpers


class _TrackingCoordinator(MockBase):
    """Minimal DataUpdateCoordinator stand-in that records success vs listen."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.data = None
        self.last_update_success = True
        self._set_updated_calls = 0
        self._listener_calls = 0

    def async_set_updated_data(self, data):
        self.data = data
        self.last_update_success = True
        self._set_updated_calls += 1

    def async_update_listeners(self):
        self._listener_calls += 1

    async def async_config_entry_first_refresh(self):
        return None


for _mod_name, _attrs in (
    (
        "homeassistant.components.sensor",
        {
            "SensorEntity": _make_entity_base("SensorEntity"),
            "SensorEntityDescription": _EntityDescriptionStub,
            "SensorDeviceClass": MagicMock(),
            "SensorStateClass": MagicMock(),
        },
    ),
    (
        "homeassistant.components.button",
        {"ButtonEntity": _make_entity_base("ButtonEntity")},
    ),
    (
        "homeassistant.components.select",
        {"SelectEntity": _make_entity_base("SelectEntity")},
    ),
    (
        "homeassistant.helpers.update_coordinator",
        {
            "CoordinatorEntity": _make_entity_base("CoordinatorEntity"),
            "DataUpdateCoordinator": _TrackingCoordinator,
            "UpdateFailed": type("UpdateFailed", (Exception,), {}),
        },
    ),
    (
        "homeassistant.helpers.restore_state",
        {"RestoreEntity": _make_entity_base("RestoreEntity")},
    ),
):
    _mod = sys.modules[_mod_name]
    for _attr, _value in _attrs.items():
        setattr(_mod, _attr, _value)

# Selectors return the config object; config_flow only stores them in Schema.
_sel = sys.modules["homeassistant.helpers.selector"]
for name in (
    "NumberSelector",
    "NumberSelectorConfig",
    "NumberSelectorMode",
    "SelectSelector",
    "SelectSelectorConfig",
    "SelectSelectorMode",
):
    setattr(_sel, name, MagicMock())

sys.modules["bleak"] = MagicMock()
sys.modules["bleak.backends.device"] = MagicMock()
sys.modules["bleak_retry_connector"] = MagicMock()

try:
    import voluptuous  # noqa: F401
except ImportError:
    vol_mock = MagicMock()
    vol_mock.Required = lambda key, default=None: key
    vol_mock.Optional = lambda key, default=None: key
    vol_mock.In = lambda values: values
    vol_mock.Schema = lambda schema: schema
    sys.modules["voluptuous"] = vol_mock
