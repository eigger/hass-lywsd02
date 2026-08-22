# Xiaomi LYWSD

Home Assistant 커스텀 통합 — Xiaomi **LYWSD02 / LYWSD02MMC** E-Ink 온습도계를
**GATT 연결**로 온·습도·배터리 수집하고, 시계 시각·표시 단위를 제어합니다.

> **Beta.** 실물 검증을 전제로 한 초기 릴리스입니다. 프로토콜은
> [`docs/protocol.md`](docs/protocol.md)가 유일한 근거이며, 일부 값은 아직 미검증입니다.

## 왜 이 통합이 필요한가

이 기기(device_id `0x2542`)의 MiBeacon 광고는 **`object_include=0`** 이라 센서
페이로드가 없습니다. 코어 `xiaomi_ble`는 이 프레임을 조용히 버리고, GATT 폴링도
하지 않습니다. 온습도는 **GATT notify (`EBE0CCC1`)로만** 나옵니다.

따라서 이 통합은 "코어를 보완하는 시계 도구"가 아니라 **코어가 구조적으로 값을
줄 수 없는 LYWSD02 계열을 GATT로 커버하는 통합**입니다.

| 기능 | 담당 |
| --- | --- |
| 온도 / 습도 / 배터리 | **이 통합** (주기적 GATT 연결) |
| E-Ink 시계 시간 동기화 | **이 통합** |
| °C / °F 표시 단위 (화면) | **이 통합** |

`display_units` select는 **E-Ink 화면**만 바꿉니다. 센서 값은 항상 °C로 들어오며
HA가 사용자 단위로 변환합니다.

## 지원 모델

- LYWSD02 / LYWSD02MMC (순정 펌웨어)
- **미지원:** LYWSD03MMC — [pvvx/ATC](https://github.com/pvvx/ATC_MiThermometer) 참고

## 설치

1. HACS → 사용자 지정 저장소 → `https://github.com/eigger/hass-lywsd02`
2. 설치 후 Home Assistant 재시작
3. 통합 추가 또는 블루투스 발견 알림 확인 (수동 MAC 입력 가능)

## ESPHome Bluetooth 프록시

폴링/쓰기를 위해 **연결 가능한** 스캐너가 필요합니다.

```yaml
esp32_ble_tracker:
bluetooth_proxy:
  active: true
```

## 옵션

- **폴링 주기** (기본 600초, 최소 120초) — 배터리 수명 장기 데이터는 아직 없습니다
- **기후 센서 생성** (기본 켜짐) — 코어가 이미 온습도를 주는 개체만 시계 제어가 필요하면 끄세요
- BLE 재시도, 자동 시간 동기화(기본 끔 / 24h / 7d)

## 개발

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

## 라이선스

MIT — 저작권자 `eigger`.
