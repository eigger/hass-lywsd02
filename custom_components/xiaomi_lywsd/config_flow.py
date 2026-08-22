"""Config flow for Xiaomi LYWSD."""

from __future__ import annotations

import dataclasses
import re
from typing import Any

import voluptuous as vol

from homeassistant.components import onboarding
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)

from .const import (
    CONF_AUTO_SYNC_HOURS,
    CONF_CLIMATE_SENSORS,
    CONF_RETRY_COUNT,
    CONF_SCAN_INTERVAL,
    DEFAULT_AUTO_SYNC_HOURS,
    DEFAULT_CLIMATE_SENSORS,
    DEFAULT_RETRY_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    scan_interval_minutes_for_ui,
)
from .device import device_for

MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")

OPTIONS_SCHEMA = {
    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): NumberSelector(
        NumberSelectorConfig(
            min=MIN_SCAN_INTERVAL,
            max=MAX_SCAN_INTERVAL,
            step=1,
            mode=NumberSelectorMode.BOX,
            unit_of_measurement="min",
        )
    ),
    vol.Required(
        CONF_CLIMATE_SENSORS, default=DEFAULT_CLIMATE_SENSORS
    ): bool,
    vol.Required(CONF_RETRY_COUNT, default=DEFAULT_RETRY_COUNT): NumberSelector(
        NumberSelectorConfig(
            min=1,
            max=10,
            step=1,
            mode=NumberSelectorMode.BOX,
        )
    ),
    vol.Required(
        CONF_AUTO_SYNC_HOURS, default=str(DEFAULT_AUTO_SYNC_HOURS)
    ): SelectSelector(
        SelectSelectorConfig(
            options=[
                {"value": "0", "label": "Disabled"},
                {"value": "24", "label": "Every 24 hours"},
                {"value": "168", "label": "Every 7 days"},
            ],
            mode=SelectSelectorMode.DROPDOWN,
        )
    ),
}

@dataclasses.dataclass
class Discovery:
    """A discovered bluetooth device."""

    title: str
    discovery_info: BluetoothServiceInfoBleak


def _identifier(address: str) -> str:
    return address.replace(":", "")[-8:]


def _title_for(address: str) -> str:
    return f"LYWSD02 {_identifier(address)}"


class LywsdConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Xiaomi LYWSD."""

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, Discovery] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()

        if device_for(discovery_info.name) is None:
            return self.async_abort(reason="not_supported")

        title = _title_for(discovery_info.address)
        self.context["title_placeholders"] = {"name": title}
        self._discovery_info = discovery_info
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None or not onboarding.async_is_onboarded(self.hass):
            return self._async_create_entry_from_discovery()

        self._set_confirm_only()
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders=self.context["title_placeholders"],
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address.upper(), raise_on_progress=False)
            self._abort_if_unique_id_configured()
            discovery = self._discovered_devices[address]
            self.context["title_placeholders"] = {"name": discovery.title}
            self._discovery_info = discovery.discovery_info
            return self._async_create_entry_from_discovery()

        current_addresses = self._async_current_ids(include_ignore=False)
        for discovery_info in async_discovered_service_info(self.hass, False):
            address = discovery_info.address.upper()
            if address in current_addresses or address in self._discovered_devices:
                continue
            if device_for(discovery_info.name) is None:
                continue
            self._discovered_devices[address] = Discovery(
                title=_title_for(address),
                discovery_info=discovery_info,
            )

        if not self._discovered_devices:
            return await self.async_step_manual()

        titles = {
            address: discovery.title
            for address, discovery in self._discovered_devices.items()
        }
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): vol.In(titles)}),
        )

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            if not MAC_RE.match(address):
                errors["base"] = "invalid_mac"
            else:
                await self.async_set_unique_id(address, raise_on_progress=False)
                self._abort_if_unique_id_configured()
                title = _title_for(address)
                self.context["title_placeholders"] = {"name": title}
                return self.async_create_entry(
                    title=title,
                    data={CONF_ADDRESS: address},
                )

        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema({vol.Required(CONF_ADDRESS): str}),
            errors=errors,
        )

    def _async_create_entry_from_discovery(self) -> ConfigFlowResult:
        assert self._discovery_info is not None
        address = self._discovery_info.address.upper()
        return self.async_create_entry(
            title=self.context["title_placeholders"]["name"],
            data={CONF_ADDRESS: address},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler()


class OptionsFlowHandler(OptionsFlowWithReload):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            # SelectSelector returns strings; normalize to int.
            if CONF_AUTO_SYNC_HOURS in user_input:
                user_input[CONF_AUTO_SYNC_HOURS] = int(
                    user_input[CONF_AUTO_SYNC_HOURS]
                )
            if CONF_RETRY_COUNT in user_input:
                user_input[CONF_RETRY_COUNT] = int(user_input[CONF_RETRY_COUNT])
            if CONF_SCAN_INTERVAL in user_input:
                user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            return self.async_create_entry(title="", data=user_input)

        suggested_values = {**self.config_entry.data, **self.config_entry.options}
        # Select options are strings in the UI.
        if CONF_AUTO_SYNC_HOURS in suggested_values:
            suggested_values[CONF_AUTO_SYNC_HOURS] = str(
                suggested_values[CONF_AUTO_SYNC_HOURS]
            )
        # Legacy installs stored seconds; the selector is minutes now.
        if CONF_SCAN_INTERVAL in suggested_values:
            suggested_values[CONF_SCAN_INTERVAL] = scan_interval_minutes_for_ui(
                suggested_values[CONF_SCAN_INTERVAL]
            )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                vol.Schema(OPTIONS_SCHEMA), suggested_values
            ),
        )
