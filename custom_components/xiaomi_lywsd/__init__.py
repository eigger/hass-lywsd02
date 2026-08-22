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
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)
from homeassistant.util import dt as dt_util

from .const import (
    AUTO_SYNC_CHOICES,
    AUTO_SYNC_DISABLED,
    AUTO_SYNC_RETRY_BASE_SECONDS,
    AUTO_SYNC_RETRY_MAX_SECONDS,
    CONF_RETRY_COUNT,
    DEFAULT_RETRY_COUNT,
    CONF_AUTO_SYNC,
    CONF_AUTO_SYNC_HOURS_V1,
    CONF_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
    STARTUP_SYNC_DELAY_SECONDS,
    auto_sync_choice,
    auto_sync_interval_days,
    auto_sync_tolerance_seconds,
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
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SELECT,
    Platform.SENSOR,
]

T = TypeVar("T")

SERVICE_SYNC_TIME = "sync_time"
SERVICE_READ_STATE = "read_state"
SERVICE_DUMP_GATT = "dump_gatt"


async def async_read_battery_into(client, device, coordinator) -> None:
    """Piggyback a battery read on a connection that is already open.

    One byte from EBE0CCC4, so it costs nothing next to whatever the connection
    was opened for — and it is the only way a clock-only install (climate
    polling off by default) ever learns the battery level. Every path that
    holds a connection calls this: both selects, both services, the button and
    automatic sync. ``get_battery`` swallows its own errors, so it can never
    turn a successful operation into a failure.
    """
    battery = await device.get_battery(client)
    if battery is not None:
        coordinator.data.battery = battery


def _auto_sync_from_v1_hours(raw: object) -> str:
    """Map the 0.1.x hours option onto a day-based choice.

    A missing key means the 0.1.x default, which was **off** — the 0.2 default
    is not. Getting this wrong would start BLE writes on every upgraded install
    that simply left the default alone.
    """
    if raw is None:
        return AUTO_SYNC_DISABLED
    try:
        hours = int(raw)
    except (TypeError, ValueError):
        return AUTO_SYNC_DISABLED
    if hours <= 0:
        return AUTO_SYNC_DISABLED
    days = max(1, round(hours / 24))
    numeric = [c for c in AUTO_SYNC_CHOICES if c.isdigit() and c != AUTO_SYNC_DISABLED]
    return min(numeric, key=lambda c: abs(int(c) - days))


async def async_migrate_entry(hass: HomeAssistant, entry: LywsdConfigEntry) -> bool:
    """Stamp pre-0.2 entries with explicit values for the renamed options.

    Doing it once here keeps ``auto_sync_choice`` and ``scan_interval_minutes``
    free of compatibility branches: after this runs, an absent key can only
    mean a 0.2 entry.
    """
    if entry.version >= 2:
        return True

    options = dict(entry.options)
    options[CONF_AUTO_SYNC] = _auto_sync_from_v1_hours(
        options.pop(CONF_AUTO_SYNC_HOURS_V1, None)
    )

    # 0.1.x stored the poll interval in seconds; the option is minutes now.
    raw_interval = options.get(CONF_SCAN_INTERVAL)
    if raw_interval is not None:
        try:
            seconds = int(raw_interval)
        except (TypeError, ValueError):
            options.pop(CONF_SCAN_INTERVAL, None)
        else:
            minutes = seconds // 60 if seconds >= 120 else seconds
            options[CONF_SCAN_INTERVAL] = max(
                MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, minutes)
            )

    hass.config_entries.async_update_entry(entry, options=options, version=2)
    _LOGGER.debug("Migrated %s to entry version 2: %s", entry.entry_id, options)
    return True


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

    # Durable state first: the auto-sync scheduler needs last_sync before any
    # entity exists, and the selects need their restored values.
    await coordinator.async_load_persisted()

    # First refresh may fail if the device is briefly out of range — do not
    # abort setup; the next poll interval will recover. Clock-only mode has no
    # poll interval and must not open a BLE session at setup.
    if coordinator.update_interval is not None:
        try:
            await coordinator.async_config_entry_first_refresh()
        except Exception as err:
            _LOGGER.warning(
                "Initial LYWSD poll for %s failed (will retry): %s", address, err
            )

    # Arm the schedule before the platforms exist. next_sync is entity state
    # now, so leaving this until after would publish "unknown / off" on every
    # restart and correct it a moment later — enough to fire an automation
    # watching for sync being switched off.
    _async_setup_auto_sync(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _async_register_services(hass)
    _async_maybe_create_proxy_issues(hass, entry, address)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LywsdConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    if len(hass.config_entries.async_entries(DOMAIN)) == 1:
        hass.services.async_remove(DOMAIN, SERVICE_SYNC_TIME)
        hass.services.async_remove(DOMAIN, SERVICE_READ_STATE)
        hass.services.async_remove(DOMAIN, SERVICE_DUMP_GATT)

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
            session_open = False
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
                coordinator.begin_connection()
                session_open = True
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
                if session_open:
                    coordinator.end_connection()

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

    async def handle_dump_gatt(call: ServiceCall) -> ServiceResponse:
        # Proxy-reachable diagnostic: walks the same async_execute path as
        # normal ops so ESPHome active proxies work (unlike tools/dump_gatt.py).
        out: dict[str, object] = {}
        for entry in _entries_from_call(hass, call):
            address = entry.runtime_data.address
            out[address] = await _service_dump_gatt(hass, entry)
        return out

    hass.services.async_register(DOMAIN, SERVICE_SYNC_TIME, handle_sync_time)
    hass.services.async_register(DOMAIN, SERVICE_READ_STATE, handle_read_state)
    hass.services.async_register(
        DOMAIN,
        SERVICE_DUMP_GATT,
        handle_dump_gatt,
        supports_response=SupportsResponse.ONLY,
    )


async def _service_sync_time(
    hass: HomeAssistant, entry: LywsdConfigEntry, offset: int
) -> None:
    coordinator = entry.runtime_data

    async def _op(client, device):
        result = await device.set_time(client, dt_util.now(), offset)
        coordinator.note_sync(
            result.drift_seconds, dt_util.now(), result.compensation_seconds
        )
        await async_read_battery_into(client, device, coordinator)
        return result

    try:
        await async_execute(hass, entry, _op)
        # Reschedule first: record_action_success publishes next_sync, and the
        # old value would otherwise stick until the next climate poll — which
        # never comes in clock-only mode.
        await coordinator.async_after_sync()
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
        await async_read_battery_into(client, device, coordinator)
        return units

    try:
        await async_execute(hass, entry, _op)
        coordinator.record_action_success()
        await coordinator.async_save_persisted()
    except Exception:
        coordinator.record_failure()
        raise


async def collect_gatt_dump(client) -> dict:
    """Walk GATT services; read every readable characteristic (hex)."""
    services_out: list[dict] = []
    for service in client.services:
        chars_out: list[dict] = []
        for char in service.characteristics:
            props = list(char.properties)
            char_entry: dict = {
                "uuid": str(char.uuid),
                "handle": getattr(char, "handle", None),
                "properties": props,
            }
            if "read" in props:
                try:
                    value = await client.read_gatt_char(char.uuid)
                    char_entry["value_hex"] = bytes(value).hex()
                except Exception as err:
                    char_entry["read_error"] = str(err)
            chars_out.append(char_entry)
        services_out.append(
            {
                "uuid": str(service.uuid),
                "handle": getattr(service, "handle", None),
                "characteristics": chars_out,
            }
        )
    return {"services": services_out}


async def _service_dump_gatt(
    hass: HomeAssistant, entry: LywsdConfigEntry
) -> dict:
    async def _op(client, device):
        return await collect_gatt_dump(client)

    try:
        return await async_execute(hass, entry, _op)
    except Exception:
        entry.runtime_data.record_failure()
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


def _auto_sync_interval(coordinator, options: dict) -> timedelta:
    """How long to wait between automatic clock writes."""
    choice = auto_sync_choice(options)
    days = auto_sync_interval_days(
        choice,
        coordinator.data.drift_rate_per_day,
        auto_sync_tolerance_seconds(options),
    )
    return timedelta(days=days)


async def _run_auto_sync(hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
    """One quiet automatic sync. Never raises into the scheduler."""
    coordinator = entry.runtime_data

    async def _op(client, device):
        now = dt_util.now()
        utcoffset = now.utcoffset()
        offset = int(utcoffset.total_seconds() // 3600) if utcoffset else 0
        result = await device.set_time(client, now, offset)
        coordinator.note_sync(
            result.drift_seconds, dt_util.now(), result.compensation_seconds
        )
        coordinator.data.consecutive_auto_failures = 0
        await async_read_battery_into(client, device, coordinator)
        return result

    try:
        await async_execute(hass, entry, _op, wrap_errors=False)
    except Exception as err:
        coordinator.data.consecutive_auto_failures += 1
        coordinator.record_failure()
        _LOGGER.debug("auto sync failed for %s: %s", coordinator.address, err)
        if coordinator.data.consecutive_auto_failures == 3:
            _LOGGER.warning(
                "Automatic time sync failed 3 times for %s", coordinator.address
            )
        return

    coordinator.record_action_success()
    await coordinator.async_save_persisted()


def _async_setup_auto_sync(hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
    """Arm a restart-safe automatic sync.

    ``async_track_time_interval`` restarts its countdown on every Home Assistant
    restart, so a 30-day cycle would never fire on a box that reboots weekly.
    Scheduling a single point in time derived from the *persisted* last sync
    makes the interval survive restarts, and a sync that came due while Home
    Assistant was down runs shortly after startup instead of being skipped.
    """
    coordinator = entry.runtime_data
    options = {**entry.data, **entry.options}
    choice = auto_sync_choice(options)
    coordinator.data.auto_sync_mode = choice

    if choice == AUTO_SYNC_DISABLED:
        coordinator.data.next_sync = None
        coordinator.data.sync_interval_days = None
        coordinator.reschedule_auto_sync = None
        return

    state: dict[str, Callable[[], None] | None] = {"unsub": None}

    def _cancel() -> None:
        if state["unsub"] is not None:
            state["unsub"]()
            state["unsub"] = None

    def _schedule(when: datetime) -> None:
        _cancel()
        # The configured cadence, not the gap to `when` — a backoff retry must
        # not make the sensor claim the interval shrank.
        coordinator.data.sync_interval_days = round(
            _auto_sync_interval(coordinator, options).total_seconds() / 86400.0, 2
        )
        coordinator.data.next_sync = when
        state["unsub"] = async_track_point_in_time(hass, _fire, when)
        # Entities are already up by the time setup arms this, so the value
        # only reaches the UI if listeners are told.
        coordinator.async_update_listeners()

    def _due_at() -> datetime:
        now = dt_util.now()
        last_sync = coordinator.data.last_sync
        if last_sync is None:
            # Never synced (fresh install, or the clock was never corrected) —
            # do it right after startup rather than a full interval from now.
            return now + timedelta(seconds=STARTUP_SYNC_DELAY_SECONDS)
        due = last_sync + _auto_sync_interval(coordinator, options)
        if due <= now:
            due = now + timedelta(seconds=STARTUP_SYNC_DELAY_SECONDS)
        return due

    def _retry_at() -> datetime:
        """Exponential backoff while the device stays unreachable."""
        failures = max(1, coordinator.data.consecutive_auto_failures)
        delay = min(
            AUTO_SYNC_RETRY_MAX_SECONDS,
            AUTO_SYNC_RETRY_BASE_SECONDS * (2 ** (failures - 1)),
        )
        return dt_util.now() + timedelta(seconds=delay)

    async def _fire(_now: datetime) -> None:
        state["unsub"] = None
        await _run_auto_sync(hass, entry)
        if coordinator.data.consecutive_auto_failures:
            # last_sync did not move, so _due_at() would be permanently overdue
            # and retry every startup-delay — back off instead.
            _schedule(_retry_at())
        else:
            _schedule(_due_at())

    def _reschedule() -> None:
        _schedule(_due_at())

    coordinator.reschedule_auto_sync = _reschedule

    def _teardown() -> None:
        coordinator.reschedule_auto_sync = None
        _cancel()

    entry.async_on_unload(_teardown)
    _schedule(_due_at())



async def async_remove_entry(hass: HomeAssistant, entry: LywsdConfigEntry) -> None:
    """Delete persisted sync state when the device is removed."""
    from .store import LywsdStore

    try:
        await LywsdStore(hass, entry.entry_id).async_remove()
    except Exception as err:  # pragma: no cover - defensive
        _LOGGER.debug("store removal failed for %s: %s", entry.entry_id, err)
