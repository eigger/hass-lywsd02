# hass-lywsd02
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?logo=home-assistant)](https://hacs.xyz/)
[![GitHub Release](https://img.shields.io/github/release/eigger/hass-lywsd02.svg)](https://github.com/eigger/hass-lywsd02/releases)
[![License](https://img.shields.io/github/license/eigger/hass-lywsd02)](https://github.com/eigger/hass-lywsd02/blob/main/LICENSE)
![integration usage](https://img.shields.io/badge/dynamic/json?color=41BDF5&logo=home-assistant&label=integration%20usage&suffix=%20installs&cacheSeconds=15600&url=https://analytics.home-assistant.io/custom_integrations.json&query=%24.xiaomi_lywsd.total)

Xiaomi LYWSD02 / LYWSD02MMC E-Ink Thermo-Hygrometer Home Assistant Integration

> [!IMPORTANT]
> **Beta.** Protocol notes live in [`docs/protocol.md`](docs/protocol.md); some
> values are still unconfirmed. Report your firmware version in issues.

## Why this integration

This device (`device_id 0x2542`) advertises MiBeacon frames with
**`object_include=0`** — no sensor payload. Core `xiaomi_ble` silently drops
those frames and never opens a GATT connection to this model. Temperature,
humidity, and battery are only reachable over **GATT** (notify on
`EBE0CCC1` for climate, read on `EBE0CCC4` for battery).

So this is not a "clock helper on top of core" — it's the integration that
covers LYWSD02-class devices core cannot read at all.

| Feature | Provided by |
| --- | --- |
| Temperature / humidity | **This integration** (periodic GATT poll) |
| Battery | **This integration** (read on any open connection, incl. clock sync) |
| E-Ink clock time sync | **This integration** |
| °C / °F display units (screen) | **This integration** |
| 12h / 24h clock mode (screen) | **This integration** |

The **Display units** and **Clock mode** selects change the E-Ink screen only.
Sensor values always arrive in °C; Home Assistant converts to the user's
preferred unit.

## Feedback & Support

- Found a bug? [Open an issue](https://github.com/eigger/hass-lywsd02/issues)
- Questions or ideas? [Join the discussion](https://github.com/eigger/hass-lywsd02/discussions)

---

## Supported Models

| Model | Firmware | Status |
|-------|----------|--------|
| LYWSD02MMC | stock | confirmed |
| LYWSD02 | stock | should work (same protocol family) |
| LYWSD03MMC | — | **not supported** — see [pvvx/ATC](https://github.com/pvvx/ATC_MiThermometer) |

## Installation

1. Install with HACS (custom repository required), or copy this repo into `custom_components/xiaomi_lywsd`.
2. Restart Home Assistant.
3. Go to **Settings** → **Integrations** and add **Xiaomi LYWSD**, or accept the Bluetooth discovery prompt.
4. If the device isn't discovered, add it manually by MAC address.

## Important Notice

Use a **Bluetooth proxy** instead of a built-in adapter — polling and writes need a **connectable** scanner.

> [!TIP]
> Hardware recommendations: [Great ESP32 Board for an ESPHome Bluetooth Proxy](https://community.home-assistant.io/t/great-esp32-board-for-an-esphome-bluetooth-proxy/916767/31)

**`bluetooth_proxy` must have `active: true`.**

```yaml
esp32_ble_tracker:
bluetooth_proxy:
  active: true
```

## Options

Configure via **Settings** → **Devices & Services** → **Xiaomi LYWSD** → **Configure**:

| Option | Default | Range | Description |
|--------|---------|-------|-------------|
| **Enable climate sensors** | Off | on/off | Creates Temperature / Humidity entities and starts periodic GATT polling. They stay unavailable until the first successful reading |
| **Poll interval** | 30 min | 2–60 min | Only used when climate sensors are enabled. LYWSD02 uses a **CR2032** coin cell; BLE connect time dominates drain |
| **Automatic time sync** | Automatic | off / 1 / 7 / 30 / 90 / 180 days / automatic | How often to write the Home Assistant clock to the device |
| **Tolerated clock error** | 60 s | 10–3600 s | Automatic mode only |
| **BLE retry count** | 3 | 1–10 | Retries when a BLE write fails |

> [!TIP]
> Battery is **not** part of climate sensors — it's one byte read on whatever connection is already open, so a clock-only install still gets a battery level at every automatic sync.

### Automatic (drift based) sync

Each sync measures how far the clock had wandered since the previous one, which
gives a drift rate in seconds per day. The next interval is the tolerated error
divided by that rate, clamped to 1–180 days: an accurate unit stretches out to
months on its own, a sloppy one keeps a short cycle. Until two syncs have been
observed it falls back to 7 days; a clock that holds to within the device's
one-second resolution goes straight to the 180-day ceiling.

Each sample counts for as much as its duration earns. The clock reads in whole
seconds, so twelve hours of it carries about ±2 s/day of rounding error while a
week carries ±0.14 — samples reach full weight at a week and shorter ones scale
down in proportion. Pressing **Sync time** by hand between automatic syncs
therefore refines the estimate without derailing it.

A manual sync is a real sync: it corrects the clock, updates `last_sync`, and
**restarts the countdown**, so the next automatic one is a full interval from
when you pressed it rather than from the previous automatic sync. Watch
`sensor.*_next_sync` move.

The schedule is **stored on disk**, so restarting Home Assistant does not
restart the countdown — a 30-day interval still fires on day 30 even on a box
that reboots weekly. A sync that came due while Home Assistant was down runs
shortly after startup. Repeated failures back off exponentially (30 min → 6 h)
rather than retrying every minute.

The write itself is **aimed at a second boundary** rather than rounded to one —
the device stores whole seconds, and rounding leaves a consistent bias in
whichever direction the link latency happens to fall. The next boundary the
write can still reach is chosen, and the write is held back until that boundary
minus one estimated one-way trip, so the device receives second T at second T.

### Clock diagnostics

Two timestamp sensors, each carrying its context as attributes rather than
spawning more entities:

**Last sync** — when the clock was last corrected.

| Attribute | Meaning |
| --- | --- |
| `drift_seconds` | Error measured just before that correction |
| `drift_seconds_per_day` | Smoothed drift rate driving Automatic mode |
| `write_compensation_seconds` | Seconds between the sampled time and the boundary aimed at — link latency plus the wait for the boundary |

**Next sync** — when the next automatic sync is due. `unknown` when automatic sync is off; the attributes say so outright.

| Attribute | Meaning |
| --- | --- |
| `auto_sync` | `off`, `auto`, or the configured number of days |
| `interval_days` | The cadence in effect. Unchanged by a failure backoff |
| `drift_seconds_per_day` | The rate the interval was derived from |

So `state_attr('sensor.lywsd02_xxxx_next_sync', 'auto_sync') == 'off'` is enough
to alert on a device whose clock is no longer being corrected.

---

## Entities

| Platform | Entity | Notes |
|----------|--------|-------|
| Sensor | Temperature / Humidity | Periodic GATT poll; requires **Enable climate sensors** |
| Sensor | Battery | Read on any open connection, including automatic sync |
| Sensor | Last sync / Next sync | Diagnostic; drift and schedule attributes (see [Clock diagnostics](#clock-diagnostics)) |
| Sensor | Failure count / Last failure | Diagnostic |
| Sensor | Connection duration | Diagnostic; seconds the last/current BLE session stayed open |
| Binary sensor | Connectivity | BLE session open / closed |
| Select | Display units | °C / °F, E-Ink screen only |
| Select | Clock mode | 12h / 24h, E-Ink screen only |
| Button | Sync time | Write current Home Assistant time to the E-Ink clock |

---

## Services

### `xiaomi_lywsd.sync_time`

Connect once, write the current time (or `timezone_offset` if given), and re-arm the automatic sync schedule.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `timezone_offset` | no | Home Assistant timezone | UTC offset in hours (`-12` to `14`) |

```yaml
action: xiaomi_lywsd.sync_time
target:
  device_id: <your device>
```

### `xiaomi_lywsd.read_state`

Connect once and refresh the **Display units** state from the device.

```yaml
action: xiaomi_lywsd.read_state
target:
  device_id: <your device>
```

### `xiaomi_lywsd.dump_gatt`

Connect once (including via Bluetooth proxy) and return the full GATT service
tree with readable characteristic values as hex. Use in **Developer Tools →
Actions** with **Response variable** — the standalone `tools/dump_gatt.py`
script can't reach devices that are only visible through a proxy.

```yaml
action: xiaomi_lywsd.dump_gatt
target:
  device_id: <your device>
```

---

## Upgrading from 0.1.x

Config entries are migrated to version 2 on first load: `auto_sync_hours`
becomes the day-based `auto_sync` choice (**an install that never touched the
options stays off**, matching the 0.1.x default), and a poll interval stored in
seconds becomes minutes.

`sensor.*_clock_drift` is no longer created — its values moved onto `last_sync`
attributes. The old entity stays in the registry as unavailable until deleted
by hand.

Since 0.2.1 the schedule has its own entity, so `next_sync` is **no longer an
attribute of `last_sync`** — read `sensor.*_next_sync` instead. Templates
written against the 0.2.0 attribute need updating.

---

## Development

```bash
pip install -r requirements-test.txt
python -m ruff check custom_components/ tests/ tools/
python -m pytest tests/ -v
```

Standalone protocol probes (Mac / adapter with direct BLE access only — see
`xiaomi_lywsd.dump_gatt` above for devices behind a proxy):

```bash
python tools/dump_gatt.py AA:BB:CC:DD:EE:FF
python tools/probe_climate.py AA:BB:CC:DD:EE:FF
python tools/probe_time.py AA:BB:CC:DD:EE:FF -5
python tools/probe_units.py AA:BB:CC:DD:EE:FF
```

---

## References

- [`docs/protocol.md`](docs/protocol.md) — reverse-engineered GATT characteristic reference for this integration
- [h4/lywsd02](https://github.com/h4/lywsd02) — GATT UUID / payload reference implementation
- [ashald/home-assistant-lywsd02](https://github.com/ashald/home-assistant-lywsd02) — 12h/24h clock-mode payload reference
- [pvvx/ATC_MiThermometer](https://github.com/pvvx/ATC_MiThermometer) — custom firmware for LYWSD03MMC
