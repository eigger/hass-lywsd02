<!-- hass-standards:header:start -->
# hass-lywsd02

Xiaomi LYWSD02 / LYWSD02MMC E-Ink 온습도계를 위한 Home Assistant 통합입니다.

[English](README.md) | **한국어**

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-lywsd02?style=flat)](https://github.com/eigger/hass-lywsd02/releases)
[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat)](#설치)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202025.1.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-lywsd02/tests.yml?branch=main&style=flat&label=Tests)](https://github.com/eigger/hass-lywsd02/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-lywsd02/validate.yml?branch=main&style=flat&label=Validate)](https://github.com/eigger/hass-lywsd02/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-lywsd02?style=flat)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/eigger/hass-lywsd02/latest/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/eigger/hass-lywsd02/releases)
<!-- hass-standards:badges:end -->
<!-- hass-standards:header:end -->

Downloads 배지는 릴리스 asset 다운로드 합계이며 활성 설치 수가 아닙니다.

## 이 통합이 필요한 이유

이 기기(`device_id 0x2542`)는 `object_include=0`(센서 데이터 없음)인 MiBeacon 프레임을
광고하므로 Core의 `xiaomi_ble`가 이를 버리고 GATT 연결도 열지 않습니다.
온도, 습도, 배터리는 GATT로만 읽을 수 있습니다.

| 기능 | 설명 |
| --- | --- |
| 온도 / 습도 | 주기적인 GATT 폴링(선택) |
| 배터리 | 열려 있는 모든 연결에서 읽기 |
| E-Ink 시계 동기화 | 수동, 일정, 오차 감지 기반 |
| °C / °F, 12시간 / 24시간 | E-Ink 화면만 변경하며 센서 값은 항상 °C |

## 지원 모델

| 모델 | 펌웨어 | 상태 |
| --- | --- | --- |
| LYWSD02MMC | 순정 | 확인됨 |
| LYWSD02 | 순정 | 동작 예상 (같은 프로토콜) |
| LYWSD03MMC | — | 지원하지 않음 — [pvvx/ATC](https://github.com/pvvx/ATC_MiThermometer) 참고 |

프로토콜 설명: [`docs/protocol.md`](docs/protocol.md). 이슈를 등록할 때 펌웨어 버전을 알려 주세요.

## 설치

<!-- hass-standards:installation:start -->
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eigger&repository=hass-lywsd02)
<!-- hass-standards:installation:end -->

1. HACS에서 **Xiaomi LYWSD**를 설치하거나 `custom_components/xiaomi_lywsd`를 `custom_components` 디렉터리에 복사합니다.
2. Home Assistant를 다시 시작합니다.
3. **설정** → **기기 및 서비스**에서 **Xiaomi LYWSD**를 추가하거나 Bluetooth 검색 알림을 수락합니다(검색되지 않으면 MAC 주소로 추가).

### Bluetooth 프록시

내장 어댑터 대신 **Bluetooth 프록시**를 사용하세요. 폴링과 쓰기에는 연결 가능한 스캐너가 필요하며
`bluetooth_proxy`에 `active: true`가 필요합니다. 기기에 GATT 연결을 잡고 있는 다른 앱은 닫으세요.
바인드 키나 페어링은 필요 없습니다.

```yaml
esp32_ble_tracker:
bluetooth_proxy:
  active: true
```

[Bluetooth 프록시 설정 안내](https://github.com/eigger/blesession/blob/main/docs/bluetooth.ko.md), [하드웨어 추천](https://community.home-assistant.io/t/great-esp32-board-for-an-esphome-bluetooth-proxy/916767/31)을 참고하세요.

## 옵션

**설정** → **기기 및 서비스** → **Xiaomi LYWSD** → **구성**:

| 옵션 | 기본값 | 범위 | 설명 |
| --- | --- | --- | --- |
| 온습도 센서 활성화 | 꺼짐 | 켜짐/꺼짐 | 온도 / 습도 엔티티를 만들고 GATT 폴링을 시작합니다 |
| 폴링 간격 | 30분 | 2–60분 | 온습도 센서 사용 시에만 적용. CR2032 전지를 쓰며 BLE 연결 시간이 전력 소모의 대부분입니다 |
| 자동 시각 동기화 | 자동 | 꺼짐 / 1 / 7 / 30 / 90 / 180일 / 자동 | Home Assistant 시각을 기기에 기록하는 주기 |
| 허용 시계 오차 | 60초 | 10–3600초 | 자동 모드의 간격과 오차 감지 동기화의 기준 |
| BLE 재시도 횟수 | 3 | 1–10 | 쓰기 실패 시 재시도 횟수 |

## 시각 동기화

- **자동** 모드는 동기화할 때마다 오차율을 측정하고 다음 간격을 *허용 오차 ÷ 오차율*(1–180일)로 정합니다. 두 번 관측하기 전에는 7일입니다. 수동 **시각 동기화**도 반영되며 카운트다운을 다시 시작합니다.
- 일정은 디스크에 저장되어 재시작해도 초기화되지 않고, Home Assistant가 꺼져 있는 동안 예정 시각이 지났다면 시작 직후 실행합니다. 반복 실패 시 30분에서 6시간까지 대기 시간을 늘립니다.
- 기기가 정수 초를 저장하므로 쓰기는 초 경계를 목표로 실행합니다.

### 폴링마다 확인 (온습도 센서 사용 시)

폴링 때 연결이 이미 열려 있으므로 시계도 읽고, 아래 경우 **같은 연결에서** 바로 동기화합니다.

- 오차가 허용 시계 오차를 초과할 때
- 기기에 저장된 UTC 오프셋이 Home Assistant와 다를 때. **일광 절약 시간(DST) 전환**은 오차만으로 알 수 없어 이 방식으로 반영합니다.

폴링에서 오차가 허용 범위 안이면 예정된 동기화를 건너뜁니다. 동기화 후 한 시간 이내에도 시계가 틀리면 쓰기를 반복하지 않고 경고를 남깁니다. 로컬 epoch를 쓰는 펌웨어일 가능성이 크니([`docs/protocol.md`](docs/protocol.md) §3) 제보해 주세요. 시계만 쓰는 설치(온습도 꺼짐, 기본값)는 폴링하지 않으므로 DST는 다음 동기화 때 반영됩니다.

## 시계 진단

| 센서 | 설명 |
| --- | --- |
| 마지막 동기화 | 시계를 마지막으로 수정한 시각. 속성: `drift_seconds`, `drift_seconds_per_day`, `write_compensation_seconds` |
| 다음 동기화 | 다음 자동 동기화 예정 시각(꺼져 있으면 `unknown`). 속성: `auto_sync`, `interval_days`, `drift_seconds_per_day` |
| 시계 오차 | 마지막으로 측정한 오차(초, 양수는 화면이 빠름). 폴링과 동기화마다 갱신 |

시계는 정수 초로 응답하므로 오차 측정값이 약 1초 범위에서 흩어질 수 있습니다. **통계** 도우미(24시간, `mean`)로 완화하세요.
시계가 더 이상 수정되지 않는 기기는 `state_attr('sensor.lywsd02_xxxx_next_sync', 'auto_sync') == 'off'`로 알림을 만들 수 있습니다.

## 엔티티

| 플랫폼 | 엔티티 | 설명 |
| --- | --- | --- |
| 센서 | 온도 / 습도 | **온습도 센서 활성화** 필요 |
| 센서 | 배터리 | 열려 있는 모든 연결에서 읽기 |
| 센서 | 마지막 동기화 / 다음 동기화 / 시계 오차 | 진단용 |
| 센서 | 실패 횟수 / 마지막 실패 / 연결 시간 | 진단용 |
| 이진 센서 | 연결 상태 | BLE 세션 열림 / 닫힘 |
| 선택 | 표시 단위 | °C / °F, 화면에만 적용 |
| 선택 | 시계 모드 | 12시간 / 24시간, 화면에만 적용 |
| 버튼 | 시각 동기화 | 현재 시각을 시계에 기록 |

## 서비스

모든 서비스는 `target: device_id`를 사용합니다.

| 서비스 | 설명 |
| --- | --- |
| `xiaomi_lywsd.sync_time` | 현재 시각을 기록하고 일정을 다시 설정. 선택 `timezone_offset`(시간 단위 `-12`~`14`, 기본값은 Home Assistant 시간대) |
| `xiaomi_lywsd.read_state` | 기기에서 **표시 단위** 상태를 갱신 |
| `xiaomi_lywsd.dump_gatt` | 프록시 경유 포함, GATT 서비스 트리와 읽을 수 있는 값을 16진수로 반환. **개발자 도구** → **작업**에서 응답 변수와 함께 사용 |

```yaml
action: xiaomi_lywsd.sync_time
target:
  device_id: <your device>
```

## 개발

테스트는 Python 3.14 / Home Assistant 2026.10.2에서 실행하며, 지원 최소 버전은 Home Assistant 2025.1.0(Python 3.13, `requirements-test-minimum.txt`)입니다.

```bash
pip install -r requirements-test.txt -r requirements_lint.txt
python -m ruff check custom_components/ tests/ tools/
python -m pytest tests/components/xiaomi_lywsd/ -v
```

`tools/`에는 직접 BLE 접근이 가능한 어댑터용 독립 조사 도구(`dump_gatt.py`, `probe_climate.py`, `probe_time.py`, `probe_units.py`)가 있습니다. 프록시 뒤 기기는 `xiaomi_lywsd.dump_gatt`를 쓰세요.

## 참고 자료

- [`docs/protocol.md`](docs/protocol.md) — GATT 특성 참고 자료
- [h4/lywsd02](https://github.com/h4/lywsd02) — UUID / 데이터 형식 참고 구현
- [ashald/home-assistant-lywsd02](https://github.com/ashald/home-assistant-lywsd02) — 12시간/24시간 데이터 형식 참고
- [pvvx/ATC_MiThermometer](https://github.com/pvvx/ATC_MiThermometer) — LYWSD03MMC용 커스텀 펌웨어

<!-- hass-standards:support:start -->
## 지원

- [Issues](https://github.com/eigger/hass-lywsd02/issues): 버그를 신고하거나 기능을 요청하세요.
- [Discussions](https://github.com/eigger/hass-lywsd02/discussions): 질문하고 사용 경험을 공유하세요.
<!-- hass-standards:support:end -->

<!-- hass-standards:related-projects:start -->
<!-- hass-standards:related-projects:end -->

<!-- hass-standards:license:start -->
## 라이선스

[MIT License](LICENSE) 라이선스로 배포됩니다.
<!-- hass-standards:license:end -->
