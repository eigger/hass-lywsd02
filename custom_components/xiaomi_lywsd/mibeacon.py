"""Read the Xiaomi product id from a MiBeacon advertisement.

The GATT table looks the same across LYWSD02 generations, but the MiBeacon
frame (service data ``0xFE95``) names the hardware: bytes 2–3, little endian.
That is the only cheap, connection-free way to tell a first-generation LYWSD02
from an LYWSD02MMC, and it matters because only the MMC has a 12h mode.
"""

from __future__ import annotations

from collections.abc import Mapping

MIBEACON_SERVICE_UUID = "0000fe95-0000-1000-8000-00805f9b34fb"

PRODUCT_ID_LYWSD02 = 0x045B
PRODUCT_ID_LYWSD02MMC = (0x16E4, 0x2542)

# First-generation LYWSD02: the time characteristic is a fixed 5-byte attribute
# and the 7-byte mode command is rejected with ATT 0x0D, so the display is 24h
# and cannot be changed (issue #34; also nphil/ha-lywsd02, bluetooth-clocks).
FIXED_24H_PRODUCT_IDS = frozenset({PRODUCT_ID_LYWSD02})


def product_id_from_service_data(service_data: Mapping[str, bytes]) -> int | None:
    """Return the MiBeacon product id, or None when no usable frame is present."""
    frame = service_data.get(MIBEACON_SERVICE_UUID)
    if not frame or len(frame) < 4:
        return None
    return frame[2] | (frame[3] << 8)
