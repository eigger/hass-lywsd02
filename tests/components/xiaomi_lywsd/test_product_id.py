"""Hardware generation from the MiBeacon advertisement (issue #34)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.xiaomi_lywsd.mibeacon import (
    MIBEACON_SERVICE_UUID,
    product_id_from_service_data,
)
from custom_components.xiaomi_lywsd.select import LywsdTimeFormatSelect
from homeassistant.exceptions import HomeAssistantError
from tests.components.xiaomi_lywsd.test_time_format import _entry

# Real frames: header 0x5030 / 0x5A30, then the product id little endian.
FRAME_LYWSD02 = bytes.fromhex("30505b04aa")
FRAME_LYWSD02MMC = bytes.fromhex("305a422500c4c51638c1a408")


def _info(frame: bytes | None):
    data = {} if frame is None else {MIBEACON_SERVICE_UUID: frame}
    return SimpleNamespace(service_data=data)


def test_product_id_parsed_little_endian():
    assert product_id_from_service_data({MIBEACON_SERVICE_UUID: FRAME_LYWSD02}) == (
        0x045B
    )
    assert (
        product_id_from_service_data({MIBEACON_SERVICE_UUID: FRAME_LYWSD02MMC})
        == 0x2542
    )


@pytest.mark.parametrize("data", [{}, {MIBEACON_SERVICE_UUID: b"\x30\x50\x5b"}])
def test_product_id_absent_or_truncated(data):
    assert product_id_from_service_data(data) is None


@pytest.mark.asyncio
async def test_first_gen_locks_clock_mode_to_24h(hass):
    hass, entry = _entry(hass)
    coordinator = entry.runtime_data
    coordinator.data.time_format = "12h"  # a stale optimistic value
    with patch.object(coordinator, "async_save_persisted", new=AsyncMock()):
        assert coordinator.async_note_service_info(_info(FRAME_LYWSD02))
        await hass.async_block_till_done()
    select = LywsdTimeFormatSelect(hass, entry)

    assert coordinator.clock_mode_fixed_24h
    assert select.options == ["24h"]
    assert select.current_option == "24h"


@pytest.mark.asyncio
async def test_first_gen_select_never_writes(hass):
    hass, entry = _entry(hass)
    entry.runtime_data.data.product_id = 0x045B
    select = LywsdTimeFormatSelect(hass, entry)

    with patch(
        "custom_components.xiaomi_lywsd.select.async_execute", new=AsyncMock()
    ) as execute:
        await select.async_select_option("24h")
        with pytest.raises(HomeAssistantError, match="24시간 표시만"):
            await select.async_select_option("12h")

    execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("frame", [FRAME_LYWSD02MMC, None])
async def test_mmc_or_unknown_keeps_both_modes(hass, frame):
    hass, entry = _entry(hass)
    coordinator = entry.runtime_data
    coordinator.data.time_format = "12h"
    coordinator.async_note_service_info(_info(frame))
    await hass.async_block_till_done()
    select = LywsdTimeFormatSelect(hass, entry)

    assert not coordinator.clock_mode_fixed_24h
    assert select.options == ["12h", "24h"]
    assert select.current_option == "12h"


@pytest.mark.asyncio
async def test_same_product_id_is_not_rewritten(hass):
    hass, entry = _entry(hass)
    coordinator = entry.runtime_data
    with patch.object(coordinator, "async_save_persisted", new=AsyncMock()) as save:
        assert coordinator.async_note_service_info(_info(FRAME_LYWSD02))
        assert not coordinator.async_note_service_info(_info(FRAME_LYWSD02))
        await hass.async_block_till_done()
    assert save.await_count == 1
