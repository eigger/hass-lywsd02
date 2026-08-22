"""Protocol encode/decode and device-layer tests (no Home Assistant)."""

from __future__ import annotations

import struct
from datetime import datetime, timezone

import pytest

from custom_components.xiaomi_lywsd.device.base import LywsdDeviceError, LywsdVerifyError
from custom_components.xiaomi_lywsd.device.lywsd02mmc import (
    UUID_DATA,
    UUID_TIME,
    UUID_UNITS,
    Lywsd02mmc,
    decode_climate,
    decode_time,
    decode_units,
    encode_time,
    encode_units,
)
from custom_components.xiaomi_lywsd.device import device_for
from tests.fake_client import FakeBleakClient


from tests.stub_clock import StubClock as _StubClock


@pytest.mark.parametrize(
    "tz",
    [9, -5, 0, 14, -12],
)
def test_encode_time_roundtrip(tz: int):
    epoch = 1_700_000_000
    payload = encode_time(epoch, tz)
    assert len(payload) == 5
    got_epoch, got_tz = decode_time(payload)
    assert got_epoch == epoch
    assert got_tz == tz


def test_encode_time_uses_signed_tz_byte():
    payload = encode_time(1_700_000_000, -5)
    # struct <Ib → last byte is signed -5 == 0xFB
    assert payload[-1] == struct.pack("b", -5)[0]


def test_decode_time_4_byte_payload():
    epoch = 1_700_000_000
    payload = struct.pack("<I", epoch)
    got_epoch, got_tz = decode_time(payload)
    assert got_epoch == epoch
    assert got_tz == 0


def test_units_roundtrip():
    assert encode_units("celsius") == b"\x00"
    assert encode_units("fahrenheit") == b"\x01"
    assert decode_units(encode_units("celsius")) == "celsius"
    assert decode_units(encode_units("fahrenheit")) == "fahrenheit"
    # Legacy community °C byte still decodes.
    assert decode_units(b"\xff") == "celsius"


@pytest.mark.asyncio
async def test_set_time_writes_expected_bytes():
    when = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    epoch = int(when.timestamp())
    initial_epoch = epoch - 120
    client = FakeBleakClient(
        {UUID_TIME: encode_time(initial_epoch, 9)},
    )
    device = Lywsd02mmc()
    result = await device.set_time(client, when, 9, **_StubClock().hooks)
    assert result.drift_seconds == pytest.approx(-120.0)
    # The write is aimed at the next whole second, not at the sampled one.
    assert result.written_epoch == epoch + 1
    assert any(w[0] == UUID_TIME and w[2] is True for w in client.writes)
    written = next(w[1] for w in client.writes if w[0] == UUID_TIME)
    assert written == encode_time(epoch + 1, 9)


@pytest.mark.asyncio
async def test_set_time_verify_error_on_mismatch():
    when = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
    client = FakeBleakClient(
        {UUID_TIME: encode_time(int(when.timestamp()) - 100, 9)},
        reject={UUID_TIME},
    )
    device = Lywsd02mmc()
    with pytest.raises(LywsdVerifyError):
        await device.set_time(client, when, 9, **_StubClock().hooks)


@pytest.mark.asyncio
async def test_set_units_rolls_back_on_verify_failure():
    client = FakeBleakClient(
        {UUID_UNITS: b"\x00"},
        reject={UUID_UNITS},
    )
    # First write is rejected (store unchanged). Rollback write must still be attempted.
    # reject blocks ALL updates — so rollback also won't stick, but the write is recorded.
    device = Lywsd02mmc()
    with pytest.raises(LywsdVerifyError):
        await device.set_units(client, "fahrenheit")
    # At least one write of 0x01 (attempt) and one of original 0x00 (rollback)
    payloads = [w[1] for w in client.writes if w[0] == UUID_UNITS]
    assert b"\x01" in payloads
    assert b"\x00" in payloads


def test_device_for_names():
    assert device_for("LYWSD02") is not None
    assert device_for("LYWSD02MMC") is not None
    assert device_for("LYWSD02MMC_ABCD") is not None
    assert device_for("LYWSD03MMC") is None
    assert device_for(None) is None
    assert device_for("") is None


def test_decode_climate_positive():
    reading = decode_climate(b"\x1a\x09\x37")
    assert reading.temperature == pytest.approx(23.30)
    assert reading.humidity == 55


def test_decode_climate_negative_temp():
    # int16 -16 → -0.16 °C
    reading = decode_climate(b"\xf0\xff\x32")
    assert reading.temperature == pytest.approx(-0.16)
    assert reading.humidity == 50


@pytest.mark.asyncio
async def test_read_climate_notify_and_stop():
    client = FakeBleakClient(
        {},
        notify={UUID_DATA: b"\x1a\x09\x37"},
    )
    device = Lywsd02mmc()
    reading = await device.read_climate(client, timeout=2)
    assert reading.temperature == pytest.approx(23.30)
    assert reading.humidity == 55
    assert UUID_DATA in client.notify_starts
    assert UUID_DATA in client.notify_stops


@pytest.mark.asyncio
async def test_read_climate_timeout_still_stops_notify():
    client = FakeBleakClient({}, notify_timeout=True)
    device = Lywsd02mmc()
    with pytest.raises(LywsdDeviceError, match="timed out"):
        await device.read_climate(client, timeout=0.05)
    assert UUID_DATA in client.notify_stops
