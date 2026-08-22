# Xiaomi LYWSD

Home Assistant custom integration for Xiaomi **LYWSD02 / LYWSD02MMC** E-Ink
thermo-hygrometers. Collects temperature, humidity, and battery over a **GATT
connection**, and controls clock time and display units.

> **Beta.** Initial release pending hardware verification. Protocol notes live
> in [`docs/protocol.md`](docs/protocol.md); some values are still unconfirmed.

## Why this integration

This device (device_id `0x2542`) advertises MiBeacon frames with
**`object_include=0`** — no sensor payload. Core `xiaomi_ble` silently drops
those frames and does not poll GATT. Climate values only appear via **GATT
notify (`EBE0CCC1`)**.

So this is not a “clock helper on top of core.” It is the integration that
covers LYWSD02-class devices core cannot read.

| Feature | Provided by |
| --- | --- |
| Temperature / humidity / battery | **This integration** (periodic GATT) |
| E-Ink clock time sync | **This integration** |
| °C / °F display units (screen) | **This integration** |

The `display_units` select changes the **E-Ink screen only**. Sensor values
always arrive in °C; Home Assistant converts to the user’s preferred unit.

## Supported models

- LYWSD02 / LYWSD02MMC (stock firmware)
- **Not supported:** LYWSD03MMC — see [pvvx/ATC](https://github.com/pvvx/ATC_MiThermometer)

## Install

1. HACS → Custom repositories → `https://github.com/eigger/hass-lywsd02`
2. Install, then restart Home Assistant
3. Add the integration, or accept the Bluetooth discovery prompt (manual MAC
   entry is also available)

## ESPHome Bluetooth proxy

Polling and writes need a **connectable** scanner:

```yaml
esp32_ble_tracker:
bluetooth_proxy:
  active: true
```

## Options

- **Poll interval** (default 1800 s / 30 min, minimum 120 s) — LYWSD02 uses a
  **CR2032** coin cell; BLE connect time dominates drain. Long-term life data
  is still missing
- **Create climate sensors** (default on) — when off, climate entities are not
  created **and periodic GATT polling stops** (clock-only mode)
- BLE retries, automatic time sync (default **every 24 hours** / 7d / off)

## Development

```bash
pip install -r requirements-test.txt
python -m ruff check custom_components/ tests/ tools/
python -m pytest tests/ -v
```

```bash
python tools/dump_gatt.py AA:BB:CC:DD:EE:FF
python tools/probe_climate.py AA:BB:CC:DD:EE:FF
python tools/probe_time.py AA:BB:CC:DD:EE:FF -5
python tools/probe_units.py AA:BB:CC:DD:EE:FF
```

For devices only reachable through an ESPHome Bluetooth proxy, use the
`xiaomi_lywsd.dump_gatt` service in Developer Tools (returns hex values) instead
of the standalone `tools/dump_gatt.py` script.

## License

MIT — copyright `eigger`.
