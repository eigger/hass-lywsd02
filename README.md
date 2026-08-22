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
| Temperature / humidity | **This integration** (periodic GATT poll) |
| Battery | **This integration** (read on any connection, incl. clock sync) |
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

- **Enable climate sensors** (default **off**) — creates temperature and
  humidity entities and starts GATT polling. They stay unavailable until the
  first successful reading. **Battery is not part of this** — it is one byte
  from `EBE0CCC4` read on whatever connection is already open, so a clock-only
  install still gets a battery level at every automatic sync
- **Poll interval** (default **30 minutes**, range 2–60) — only used when
  climate sensors are enabled. LYWSD02 uses a **CR2032** coin cell; BLE
  connect time dominates drain
- **Automatic time sync** (default **Automatic**) — off, every 1 / 7 / 30 / 90 /
  180 days, or drift based
- **Tolerated clock error** (default **60 s**) — Automatic mode only
- BLE retry count

### Automatic (drift based) sync

Each sync measures how far the clock had wandered since the previous one, which
gives a drift rate in seconds per day. The next interval is the tolerated error
divided by that rate, clamped to 1–180 days: an accurate unit stretches out to
months on its own, a sloppy one keeps a short cycle. Until two syncs have been
observed it falls back to 7 days; a clock that holds to within the device's
one-second resolution goes straight to the 180-day ceiling.

The schedule is **stored on disk**, so restarting Home Assistant does not restart
the countdown — a 30-day interval still fires on day 30 even on a box that
reboots weekly. A sync that came due while Home Assistant was down runs shortly
after startup. Repeated failures back off exponentially (30 min → 6 h) rather
than retrying every minute.

### Clock diagnostics

Two timestamp sensors, each carrying its context as attributes rather than
spawning more entities:

`sensor.*_last_sync` — when the clock was last corrected.

| Attribute | Meaning |
| --- | --- |
| `drift_seconds` | Error measured just before that correction |
| `drift_seconds_per_day` | Smoothed drift rate driving Automatic mode |

`sensor.*_next_sync` — when the next automatic sync is due. **Empty means
automatic sync is off**, which the attributes state outright.

| Attribute | Meaning |
| --- | --- |
| `auto_sync` | `off`, `auto`, or the configured number of days |
| `interval_days` | The cadence in effect — from the drift rate in Automatic mode, from the dropdown otherwise. Unchanged by a failure backoff |
| `drift_seconds_per_day` | The rate the interval was derived from |

So `state_attr('sensor.lywsd02_xxxx_next_sync', 'auto_sync') == 'off'` is enough
to alert on a device whose clock is no longer being corrected.

## Upgrading from 0.1.x

Config entries are migrated to version 2 on first load: `auto_sync_hours`
becomes the day-based `auto_sync` choice (**an install that never touched the
options stays off**, matching the 0.1.x default), and a poll interval stored in
seconds becomes minutes.

`sensor.*_clock_drift` is no longer created — its values moved onto `last_sync`
attributes. The old entity stays in the registry as unavailable until deleted by
hand.

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
