"""The Xiaomi LYWSD Bluetooth integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import TypeVar

from bleak import BleakClient
from bleak_retry_connector import (
    close_stale_connections_by_address,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_SYNC_HOURS,
    CONF_RETRY_COUNT,
    DEFAULT_AUTO_SYNC_HOURS,
    DEFAULT_RETRY_COUNT,
    DOMAIN,
    LOCK,
    MANUFACTURER,
    MODEL,
)
from .coordinator import LywsdCoordinator
from .device import LywsdDevice, LywsdVerifyError, device_for
from .types import LywsdConfigEntry

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
]

T = TypeVar("T")

SERVICE_SYNC_TIME = "sync_time"
SERVICE_READ_STATE = "read_state"


async def async_setup_entry(hass: HomeAssistant, entry: LywsdConfigEntry) -> bool:
    """Set up Xiaomi LYWSD from a config entry."""
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    if LOCK not in hass.data[DOMAIN]:
        hass.data[DOMAIN][LOCK] = asyncio.Lock()

    address = entry.data.get(CONF_ADDRESS) or entry.unique_id
    assert address is not None
    address = address.upper()

    device_cls = device_for("LYWSD02MMC")
    assert device_cls is not None
    coordinator = LywsdCoordinator(
        hass,
        entry,
        address,
        hass.data[DOMAIN][LOCK],
        device_cls(),
    )
    entry.runtime_data = coordinator

    identifier = coordinator.identifier
    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        connections={(CONNECTION_BLUETOOTH, address)},
        manufacturer=MANUFACTURER,
        model=MODEL,
        name=f"LYWSD02 {identifier}",
    )

    # First refresh may fail if the device is briefly out of range — do not
    # abort setup; the next poll interval will recover.
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.warning(
            "Initial LYWSD poll for %s failed (will retry): %s", address, err
        )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)
    _async_maybe_create_proxy_issues(hass, entry, address)
    _async_setup_auto_sync(hass, entry)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LywsdConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        hass.services.async_remove(DOMAIN, SERVICE_SYNC_TIME)
        hass.services.async_remove(DOMAIN, SERVICE_READ_STATE)

    async_delete_issue(hass, DOMAIN, f"no_connectable_scanner_{entry.entry_id}")
    async_delete_issue(hass, DOMAIN, f"proxy_not_active_{entry.entry_id}")
    return True


async def async_execute(
    hass: HomeAssistant,
    entry: LywsdConfigEntry,
    op: Callable[[BleakClient, LywsdDevice], Awaitable[T]],
    *,
    wrap_errors: bool = True,
) -> T:
    """Acquire domain lock, connect, run op, always disconnect.

    This is the only BLE access path for the integration. It does **not**
    mutate coordinator bookkeeping (``failure_count`` / listeners) — callers own
    that so poll failures are not double-counted and mid-failure broadcasts
    cannot flip ``last_update_success``.

    ``LywsdVerifyError`` is never retried — the device already accepted the write
    and re-sending only causes extra E-Ink refreshes / battery use.
    ``wrap_errors=False`` skips wrapping unexpected errors as ``HomeAssistantError``
    (used by quiet auto-sync); the exception is still raised.
    """
    coordinator = entry.runtime_data
    address = coordinator.address
    options = {**entry.data, **entry.options}
    max_retries = int(options.get(CONF_RETRY_COUNT, DEFAULT_RETRY_COUNT))
    device_cls = device_for("LYWSD02MMC")
    assert device_cls is not None
    device = device_cls()

    async with hass.data[DOMAIN][LOCK]:
        for attempt in range(1, max_retries + 1):
            client: BleakClient | None = None
            try:
                ble_device = bluetooth.async_ble_device_from_address(
                    hass, address, connectable=True
                )
                if ble_device is None:
                    raise HomeAssistantError(
                        f"기기를 찾을 수 없습니다 ({address}). "
                        "범위와 연결 가능한 Bluetooth 어댑터/프록시를 확인하세요."
                    )

                await close_stale_connections_by_address(address)
                client = await establish_connection(
                    BleakClient, ble_device, ble_device.address
                )
                result = await op(client, device)
                _clear_proxy_issues(hass, entry)
                return result
            except LywsdVerifyError:
                raise
            except HomeAssistantError:
                # Missing device / explicit HA errors — do not burn retries.
                raise
            except Exception as err:
                _LOGGER.warning(
                    "BLE op failed for %s (attempt %s/%s): %s",
                    address,
                    attempt,
                    max_retries,
                    err,
                )
                if attempt < max_retries:
                    await asyncio.sleep(1)
                    continue
                if not wrap_errors:
                    raise
                raise HomeAssistantError(
                    f"BLE 작업 실패 ({address}): {err}"
                ) from err
            finally:
                if client is not None:
                    try:
                        if client.is_connected:
                            await client.disconnect()
                    except Exception as disc_err:
                        _LOGGER.warning(
                            "%s disconnect warning: %s", address, disc_err
                        )

    raise RuntimeError("async_execute exhausted retries without result")  # pragma: no cover


def _async_register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_SYNC_TIME):
        return

    async def handle_sync_time(call: ServiceCall) -> None:
        for entry in _entries_from_call(hass, call):
            offset = call.data.get("timezone_offset")
            if offset is None:
                utcoffset = dt_util.now().utcoffset()
                offset = int(utcoffset.total_seconds() // 3600) if utcoffset else 0
            else:
                offset = int(offset)
            await _service_sync_time(hass, entry, offset)

    async def handle_read_state(call: ServiceCall) -> None:
        for entry in _entries_from_call(hass, call):
            await _service_read_state(hass, entry)

    hass.services.async_register(DOMAIN, SERVICE_SYNC_TIME, handle_sync_time)
    hass.services.async_register(DOMAIN, SERVICE_READ_STATE, handle_read_state)


async def _service_sync_time(
    hass: HomeAssistant, entry: LywsdConfigEntry, offset: int
) -> None:
    coordinator = entry.runtime_data

    async def _op(client, device):
        result = await device.set_time(client, dt_util.now(), offset)
        coordinator.data.last_sync = dt_util.now()
        coordinator.data.last_drift_seconds = result.drift_seconds
        return result

    try:
        await async_execute(hass, entry, _op)
        coordinator.record_action_success()
    except Exception as err:
        coordinator.record_failure()
        if isinstance(err, LywsdVerifyError):
            raise HomeAssistantError(
                "기기가 시간 쓰기를 확인하지 못했습니다"
            ) from err
        raise


async def _service_read_state(
    hass: HomeAssistant, entry: LywsdConfigEntry
) -> None:
    coordinator = entry.runtime_data

    async def _op(client, device):
        units = await device.get_units(client)
        coordinator.data.units = units
        return units

    try:
        await async_execute(hass, entry, _op)
        coordinator.record_action_success()
    except Exception:
        coordinator.record_failure()
        raise


def _extract_referenced_entities(hass: HomeAssistant, call: ServiceCall):
    """Resolve service targets across HA versions.

    Newer cores moved the helper to ``homeassistant.helpers.target`` and take
    ``TargetSelection`` instead of ``ServiceCall``. Fall back to the old
    ``helpers.service`` API for HA 2025.1-era installs.
    """
    try:
        from homeassistant.helpers import target as target_helpers

        extract = target_helpers.async_extract_referenced_entity_ids
        selection_cls = target_helpers.TargetSelection
    except (ImportError, AttributeError):
        from homeassistant.helpers.service import (  # type: ignore[attr-defined]
            async_extract_referenced_entity_ids as extract,
        )

        return extract(hass, call)

    return extract(hass, selection_cls(call.data), expand_group=True)


def _entries_from_call(
    hass: HomeAssistant, call: ServiceCall
) -> list[LywsdConfigEntry]:
    """Resolve entity/device/area/label/floor targets to config entries.

    A target is required. Missing targets must not fan out to every entry.
    """
    from homeassistant.helpers import entity_registry as er

    selected = _extract_referenced_entities(hass, call)
    entity_ids = selected.referenced | selected.indirectly_referenced
    device_ids = set(selected.referenced_devices)

    if not entity_ids and not device_ids:
        # No expanded targets — also reject bare calls with no selectors.
        if not any(
            call.data.get(key)
            for key in ("entity_id", "device_id", "area_id", "label_id", "floor_id")
        ):
            raise ServiceValidationError(
                "xiaomi_lywsd 서비스는 entity/device/area/label 타깃이 필요합니다"
            )
        raise ServiceValidationError(
            "타깃에 해당하는 Xiaomi LYWSD 기기를 찾지 못했습니다"
        )

    found: dict[str, LywsdConfigEntry] = {}

    def _add(entry) -> None:
        if entry and entry.domain == DOMAIN:
            found[entry.entry_id] = entry  # type: ignore[assignment]

    registry = er.async_get(hass)
    for entity_id in entity_ids:
        ent = registry.async_get(entity_id)
        if ent is None or ent.config_entry_id is None:
            continue
        _add(hass.config_entries.async_get_entry(ent.config_entry_id))

    device_registry = dr.async_get(hass)
    for device_id in device_ids:
        device = device_registry.async_get(device_id)
        if device is None:
            continue
        for entry_id in device.config_entries:
            _add(hass.config_entries.async_get_entry(entry_id))

    if not found:
        raise ServiceValidationError(
            "타깃에 해당하는 Xiaomi LYWSD 기기를 찾지 못했습니다"
        )

    return list(found.values())


def _async_maybe_create_proxy_issues(
    hass: HomeAssistant, entry: LywsdConfigEntry, address: str
) -> None:
    """Warn when no connectable path exists — do not fail setup."""
    try:
        any_scanner = bluetooth.async_scanner_count(hass, connectable=True)
        connectable = bluetooth.async_ble_device_from_address(
            hass, address, connectable=True
        )
        any_device = bluetooth.async_ble_device_from_address(
            hass, address, connectable=False
        )
    except Exception as err:
        _LOGGER.debug("proxy issue check skipped: %s", err)
        return

    if any_scanner == 0:
        async_create_issue(
            hass,
            DOMAIN,
            f"no_connectable_scanner_{entry.entry_id}",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="no_connectable_scanner",
        )
        return

    if connectable is None and any_device is not None:
        async_create_issue(
            hass,
            DOMAIN,
            f"proxy_not_active_{entry.entry_id}",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="proxy_not_active",
        )


def _clear_proxy_issues(hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
    async_delete_issue(hass, DOMAIN, f"no_connectable_scanner_{entry.entry_id}")
    async_delete_issue(hass, DOMAIN, f"proxy_not_active_{entry.entry_id}")


def _async_setup_auto_sync(hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
    options = {**entry.data, **entry.options}
    hours = int(options.get(CONF_AUTO_SYNC_HOURS, DEFAULT_AUTO_SYNC_HOURS))
    if hours <= 0:
        return

    async def _tick(now: datetime) -> None:
        coordinator = entry.runtime_data

        async def _op(client, device):
            utcoffset = dt_util.now().utcoffset()
            offset = int(utcoffset.total_seconds() // 3600) if utcoffset else 0
            result = await device.set_time(client, dt_util.now(), offset)
            coordinator.data.last_sync = dt_util.now()
            coordinator.data.last_drift_seconds = result.drift_seconds
            coordinator.data.consecutive_auto_failures = 0
            return result

        try:
            await async_execute(hass, entry, _op, wrap_errors=False)
            coordinator.record_action_success()
        except Exception as err:
            coordinator.data.consecutive_auto_failures += 1
            coordinator.record_failure()
            _LOGGER.debug("auto sync failed for %s: %s", coordinator.address, err)
            if coordinator.data.consecutive_auto_failures == 3:
                _LOGGER.warning(
                    "Automatic time sync failed 3 times for %s",
                    coordinator.address,
                )

    unsub = async_track_time_interval(hass, _tick, timedelta(hours=hours))
    entry.async_on_unload(unsub)
