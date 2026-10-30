<!-- hass-standards:header:start -->
# hass-lywsd02

Xiaomi LYWSD02 / LYWSD02MMC E-Ink Thermo-Hygrometer Home Assistant Integration

**English** | [한국어](README.ko.md)

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-lywsd02?style=flat)](https://github.com/eigger/hass-lywsd02/releases)
[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat)](#installation)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202025.1.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-lywsd02/tests.yml?branch=main&style=flat&label=Tests)](https://github.com/eigger/hass-lywsd02/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-lywsd02/validate.yml?branch=main&style=flat&label=Validate)](https://github.com/eigger/hass-lywsd02/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-lywsd02?style=flat)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/eigger/hass-lywsd02/latest/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/eigger/hass-lywsd02/releases)
<!-- hass-standards:badges:end -->
<!-- hass-standards:header:end -->

Downloads counts release asset downloads, not active installations.

## Why this integration

This device (`device_id 0x2542`) advertises MiBeacon frames with `object_include=0`
(no sensor payload), so core `xiaomi_ble` drops them and never opens a GATT
connection. Temperature, humidity and battery are only reachable over GATT.

| Feature | Notes |
| --- | --- |
| Temperature / humidity | Periodic GATT poll (opt-in) |
| Battery | Read on any open connection |
| E-Ink clock sync | Manual, scheduled, or drift-triggered |
| °C / °F and 12h / 24h | Changes the E-Ink screen only; sensors always report °C |

## Supported models

| Model | Firmware | Status |
| --- | --- | --- |
| LYWSD02MMC | stock | confirmed |
| LYWSD02 | stock | should work (same protocol) |
| LYWSD03MMC | — | not supported — see [pvvx/ATC](https://github.com/pvvx/ATC_MiThermometer) |

Protocol notes: [`docs/protocol.md`](docs/protocol.md). Please include your firmware version in issues.

## Installation

<!-- hass-standards:installation:start -->
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eigger&repository=hass-lywsd02)
<!-- hass-standards:installation:end -->

1. Install **Xiaomi LYWSD** from HACS, or copy `custom_components/xiaomi_lywsd` into your `custom_components` directory.
2. Restart Home Assistant.
3. Add **Xiaomi LYWSD** under **Settings** → **Devices & services**, or accept the Bluetooth discovery prompt (otherwise add it by MAC address).

### Bluetooth proxy

Use a **Bluetooth proxy** rather than a built-in adapter: polling and writes need a connectable scanner, and `bluetooth_proxy` must have `active: true`. Close other apps holding a GATT connection to the device. No bindkey or pairing is needed.

```yaml
esp32_ble_tracker:
bluetooth_proxy:
  active: true
```

See the [Bluetooth proxy setup guide](https://github.com/eigger/blesession/blob/main/docs/bluetooth.md) and [hardware recommendations](https://community.home-assistant.io/t/great-esp32-board-for-an-esphome-bluetooth-proxy/916767/31).

## Options

**Settings** → **Devices & services** → **Xiaomi LYWSD** → **Configure**:

| Option | Default | Range | Description |
| --- | --- | --- | --- |
| Enable climate sensors | Off | on/off | Creates temperature / humidity entities and starts GATT polling |
| Poll interval | 30 min | 2–60 min | Only with climate sensors. The device uses a CR2032; BLE connect time dominates drain |
| Automatic time sync | Automatic | off / 1 / 7 / 30 / 90 / 180 days / automatic | How often to write the Home Assistant clock to the device |
| Tolerated clock error | 60 s | 10–3600 s | Sets the Automatic interval and the threshold for drift-triggered sync |
| BLE retry count | 3 | 1–10 | Retries when a write fails |

## Time sync

- **Automatic** measures drift at each sync and sets the next interval to *tolerated error ÷ drift rate*, clamped to 1–180 days (7 days until two syncs are observed). A manual **Sync time** also counts and restarts the countdown.
- The schedule is stored on disk, so a restart does not reset it; a sync that came due while Home Assistant was down runs shortly after startup. Repeated failures back off from 30 min to 6 h.
- Writes are aimed at a second boundary, since the device stores whole seconds.

### Check on every poll (climate sensors on)

Each poll already holds a connection, so it also reads the clock and, on the same connection, syncs when:

- the error exceeds the tolerated clock error, or
- the UTC offset stored on the device differs from Home Assistant's, which is how a **daylight saving change** is picked up (drift alone cannot see it).

A poll that finds the clock within tolerance skips the sync that was scheduled. If the clock is still wrong less than an hour after a sync, the write is not repeated and a warning is logged; this usually means a firmware whose epoch is local rather than UTC ([`docs/protocol.md`](docs/protocol.md) §3), so please report it. Clock-only installs (climate off, the default) never poll, so DST is applied at the next sync.

## Clock diagnostics

| Sensor | Description |
| --- | --- |
| Last sync | When the clock was last corrected. Attributes: `drift_seconds`, `drift_seconds_per_day`, `write_compensation_seconds` |
| Next sync | When the next automatic sync is due (`unknown` if off). Attributes: `auto_sync`, `interval_days`, `drift_seconds_per_day` |
| Clock drift | Last measured error in seconds (positive = display is fast). Updated on every poll and sync |

The clock answers in whole seconds, so expect drift readings to scatter by about a second. A **Statistics** helper (24 h, `mean`) smooths it. To alert on a device that is no longer corrected, check `state_attr('sensor.lywsd02_xxxx_next_sync', 'auto_sync') == 'off'`.

## Entities

| Platform | Entity | Notes |
| --- | --- | --- |
| Sensor | Temperature / Humidity | Requires **Enable climate sensors** |
| Sensor | Battery | Read on any open connection |
| Sensor | Last sync / Next sync / Clock drift | Diagnostic |
| Sensor | Failure count / Last failure / Connection duration | Diagnostic |
| Binary sensor | Connectivity | BLE session open / closed |
| Select | Display units | °C / °F, screen only |
| Select | Clock mode | 12h / 24h, screen only |
| Button | Sync time | Write the current time to the clock |

## Services

All services take `target: device_id`.

| Service | Description |
| --- | --- |
| `xiaomi_lywsd.sync_time` | Write the current time and re-arm the schedule. Optional `timezone_offset` (hours, `-12` to `14`; default: Home Assistant timezone) |
| `xiaomi_lywsd.read_state` | Refresh the **Display units** state from the device |
| `xiaomi_lywsd.dump_gatt` | Return the GATT service tree with readable values as hex, including via a proxy. Use in **Developer tools** → **Actions** with a response variable |

```yaml
action: xiaomi_lywsd.sync_time
target:
  device_id: <your device>
```

## Development

Tests run on Python 3.14 / Home Assistant 2026.10.2; the minimum supported Home Assistant is 2025.1.0 (Python 3.13, `requirements-test-minimum.txt`).

```bash
pip install -r requirements-test.txt -r requirements_lint.txt
python -m ruff check custom_components/ tests/ tools/
python -m pytest tests/components/xiaomi_lywsd/ -v
```

`tools/` has standalone probes for adapters with direct BLE access (`dump_gatt.py`, `probe_climate.py`, `probe_time.py`, `probe_units.py`); for a device behind a proxy use `xiaomi_lywsd.dump_gatt`.

## References

- [`docs/protocol.md`](docs/protocol.md) — GATT characteristic reference
- [h4/lywsd02](https://github.com/h4/lywsd02) — UUID / payload reference implementation
- [ashald/home-assistant-lywsd02](https://github.com/ashald/home-assistant-lywsd02) — 12h/24h payload reference
- [pvvx/ATC_MiThermometer](https://github.com/pvvx/ATC_MiThermometer) — custom firmware for LYWSD03MMC

<!-- hass-standards:support:start -->
## Support

- [Issues](https://github.com/eigger/hass-lywsd02/issues): Report bugs or request features.
- [Discussions](https://github.com/eigger/hass-lywsd02/discussions): Ask questions and share your experience.
<!-- hass-standards:support:end -->

<!-- hass-standards:related-projects:start -->
<!-- hass-standards:related-projects:end -->

<!-- hass-standards:license:start -->
## License

Released under the [MIT License](LICENSE).
<!-- hass-standards:license:end -->
