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
[![Downloads](https://img.shields.io/github/downloads/eigger/hass-lywsd02/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/eigger/hass-lywsd02/releases)
<!-- hass-standards:badges:end -->
<!-- hass-standards:header:end -->

Downloads 배지는 모든 GitHub 릴리스의 첨부 asset 다운로드 합계이며 활성 설치 수가 아닙니다.

> [!IMPORTANT]
> **베타 버전입니다.** 프로토콜 설명은 [`docs/protocol.md`](docs/protocol.md)에 있으며 일부
> 값은 아직 확인되지 않았습니다. 이슈를 등록할 때 펌웨어 버전을 알려 주세요.

## 이 통합이 필요한 이유

이 기기(`device_id 0x2542`)는 **`object_include=0`**인 MiBeacon 프레임을 광고합니다.
즉, 센서 데이터가 없습니다. Core의 `xiaomi_ble`는 이 프레임을 조용히 버리며 이 모델에
GATT 연결을 열지 않습니다. 온도, 습도, 배터리 값은 **GATT**로만 읽을 수 있습니다
(온습도는 `EBE0CCC1` 알림, 배터리는 `EBE0CCC4` 읽기).

따라서 이 통합은 단순히 Core 위에 시계 기능을 추가하는 도우미가 아니라,
Core가 전혀 읽지 못하는 LYWSD02 계열 기기를 지원하는 통합입니다.

| 기능 | 제공 주체 |
| --- | --- |
| 온도 / 습도 | **이 통합** (주기적인 GATT 폴링) |
| 배터리 | **이 통합** (시각 동기화를 포함한 모든 열린 연결에서 읽기) |
| E-Ink 시계 시각 동기화 | **이 통합** |
| °C / °F 표시 단위 (화면) | **이 통합** |
| 12시간 / 24시간 시계 모드 (화면) | **이 통합** |

**표시 단위**와 **시계 모드** 선택 엔티티는 E-Ink 화면만 변경합니다.
센서 값은 항상 °C로 수신하며 Home Assistant가 사용자의 선호 단위로 변환합니다.

## 지원 모델

| 모델 | 펌웨어 | 상태 |
|-------|----------|--------|
| LYWSD02MMC | 순정 | 확인됨 |
| LYWSD02 | 순정 | 동작 예상 (같은 프로토콜 계열) |
| LYWSD03MMC | — | **지원하지 않음** — [pvvx/ATC](https://github.com/pvvx/ATC_MiThermometer) 참고 |

## 설치

<!-- hass-standards:installation:start -->
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eigger&repository=hass-lywsd02)
<!-- hass-standards:installation:end -->

1. HACS 기본 통합 목록에서 **Xiaomi LYWSD**를 설치하거나, `custom_components/xiaomi_lywsd`를 Home Assistant의 `custom_components` 디렉터리에 복사합니다.
2. Home Assistant를 다시 시작합니다.
3. **설정** → **통합**에서 **Xiaomi LYWSD**를 추가하거나 Bluetooth 검색 알림을 수락합니다.
4. 기기가 검색되지 않으면 MAC 주소로 수동 추가합니다.

## 중요 안내

내장 어댑터 대신 **Bluetooth 프록시**를 사용하세요. 폴링과 쓰기에는 **연결 가능한** 스캐너가 필요합니다.

> [!TIP]
> 하드웨어 추천: [ESPHome Bluetooth 프록시용 ESP32 보드](https://community.home-assistant.io/t/great-esp32-board-for-an-esphome-bluetooth-proxy/916767/31)

프록시 펌웨어 설치, Home Assistant 등록, 공통 문제 해결은 [Bluetooth 프록시 설정 안내](https://github.com/eigger/blesession/blob/main/docs/bluetooth.ko.md)를 따르세요.

LYWSD02 계열 기기에는 정상적인 코인 전지와 사용 가능한 연결 지원 스캐너가 필요합니다. 설정 또는 폴링 전에 GATT 연결을 점유한 다른 앱을 닫으세요. 이 통합은 바인드 키를 요청하지 않으며 페어링/본딩을 구현하지 않습니다. 순정 펌웨어의 LYWSD02MMC는 확인되었으며 원래 LYWSD02는 아직 확인되지 않았습니다. 여기서 추가 하드웨어/프록시 검증을 주장하지 않습니다.

**`bluetooth_proxy`에는 반드시 `active: true`가 필요합니다.**

```yaml
esp32_ble_tracker:
bluetooth_proxy:
  active: true
```

## 옵션

**설정** → **기기 및 서비스** → **Xiaomi LYWSD** → **구성**에서 설정합니다.

| 옵션 | 기본값 | 범위 | 설명 |
|--------|---------|-------|-------------|
| **온습도 센서 활성화** | 꺼짐 | 켜짐/꺼짐 | 온도 / 습도 엔티티를 만들고 주기적인 GATT 폴링을 시작합니다. 첫 읽기가 성공할 때까지 사용할 수 없는 상태로 표시됩니다 |
| **폴링 간격** | 30분 | 2–60분 | 온습도 센서가 활성화된 경우에만 사용합니다. LYWSD02는 **CR2032** 코인 전지를 사용하며 BLE 연결 시간이 전력 소모의 대부분을 차지합니다 |
| **자동 시각 동기화** | 자동 | 꺼짐 / 1 / 7 / 30 / 90 / 180일 / 자동 | Home Assistant 시각을 기기에 기록하는 주기 |
| **허용 시계 오차** | 60초 | 10–3600초 | 자동 모드의 간격을 정하며 오차 확인 시 동기화를 실행하는 기준입니다 |
| **BLE 재시도 횟수** | 3 | 1–10 | BLE 쓰기 실패 시 재시도 횟수 |

> [!TIP]
> 배터리는 온습도 센서에 **포함되지 않습니다**. 이미 열린 연결에서 1바이트만 읽으므로 시계만 사용하는 설치에서도 자동 동기화 때마다 배터리 잔량을 가져옵니다.

### 자동 (오차 기반) 동기화

매번 동기화할 때 이전 동기화 이후 시계가 얼마나 틀어졌는지 측정하여 하루당 초 단위의
오차율을 구합니다. 다음 간격은 허용 오차를 이 오차율로 나눈 값이며 1–180일로 제한됩니다.
정확한 기기는 스스로 수개월 간격으로 늘어나고 오차가 큰 기기는 짧은 주기를 유지합니다.
두 번의 동기화를 관측하기 전에는 7일을 사용하며, 기기의 1초 해상도 내에서 정확한 시계는
바로 최대 180일 간격을 사용합니다.

각 표본에는 측정 기간에 비례한 가중치가 부여됩니다. 시계는 정수 초로 읽히므로 12시간
표본의 반올림 오차는 약 ±2초/일이고 일주일 표본은 ±0.14초/일입니다. 일주일 이상이면
전체 가중치를 적용하고 더 짧으면 비례해서 줄입니다. 따라서 자동 동기화 사이에
**시각 동기화**를 수동으로 눌러도 추정이 흐트러지지 않고 더 정교해집니다.

수동 동기화도 실제 동기화입니다. 시계를 수정하고 `last_sync`를 갱신하며
**카운트다운을 다시 시작합니다**. 다음 자동 동기화는 이전 자동 동기화 시점이 아니라
버튼을 누른 시점에서 전체 간격이 지난 뒤 실행됩니다. `sensor.*_next_sync`의 변화를 확인하세요.

일정은 **디스크에 저장**되므로 Home Assistant를 재시작해도 카운트다운이 초기화되지
않습니다. 매주 재시작하는 시스템에서도 30일 간격은 30일째에 실행됩니다.
Home Assistant가 중지된 동안 예정 시각이 지났다면 시작 직후 실행합니다.
반복 실패 시 매분 재시도하지 않고 지수적으로 대기 시간을 늘립니다(30분 → 6시간).

쓰기는 초 단위로 반올림하는 대신 **초 경계를 목표로 실행**합니다. 기기는 정수 초를
저장하므로 단순히 반올림하면 연결 지연 방향에 따라 일정한 편향이 남습니다.
아직 도달 가능한 다음 초 경계를 선택하고 그 경계에서 추정 편도 전송 시간을 뺀
시점까지 쓰기를 지연하여, 기기가 초 T에 시각 T를 받도록 합니다.

### 온습도 폴링 시 오차 확인

온습도 센서가 활성화되면 폴링 간격마다 연결이 이미 열리며 **배터리를 소모하는 것은
연결 자체**입니다. 여기에 5바이트 시계 읽기를 더하는 것은 한 번의 왕복뿐입니다.
따라서 폴링마다 시계를 읽고 오차가 허용 시계 오차를 초과하는 즉시 **같은 연결에서
동기화**합니다. 이를 일정으로 미루면 현재 연결에서 할 일을 나중에 두 번째 연결을
열어 실행하게 되므로 미루지 않습니다.

반대도 마찬가지입니다. 폴링에서 오차가 허용 범위 안에 충분히 들어온 것으로
측정되면 예정된 동기화를 **건너뛰고** 간격을 다시 시작합니다. 수정할 것이 없다는
측정 결과를 근거로 연결 한 번을 절약합니다.

고정 일정이 잡아낼 수 없는 상황도 감지합니다. **배터리 교체 또는 펌웨어 초기화**로
화면 시각이 1970년으로 돌아가면 동기화 간격 전체가 아니라 폴링 한 번 이내에
알아냅니다. 정확한 기기의 동기화 간격은 6개월일 수 있습니다.

읽기는 저렴하고 쓰기는 그렇지 않으므로 두 가지 보호 장치를 둡니다.

- **동기화 후 한 시간 이내**에도 오차가 허용 범위를 벗어나면 쓰기를 반복하지 않고
  경고를 한 번 기록합니다. 쓰기가 적용되지 않는다면 펌웨어 문제를 의심할 수 있으며,
  특히 UTC가 아닌 로컬 epoch일 가능성이 큽니다([`docs/protocol.md`](docs/protocol.md) §3 참고).
  이 경우 쓰기로 해결되지 않는 시간대 크기의 일정한 오차로 나타납니다. 제보해 주세요.
- 시계 읽기나 쓰기가 실패해도 폴링 전체는 실패하지 않습니다. 폴링의 목적은 온습도
  측정이며 다음 폴링에서 다시 시도합니다. 일정은 안전장치로 계속 유지됩니다.

시계만 사용하는 설치(기본값인 온습도 센서 꺼짐)는 폴링하지 않으므로 달라지지
않습니다. 적응형 일정만 연결을 엽니다.

### 시계 진단

진단 맥락을 별도 엔티티로 늘리지 않고 속성에 담는 타임스탬프 센서 두 개를 제공합니다.

**마지막 동기화** — 시계를 마지막으로 수정한 시각입니다.

| 속성 | 의미 |
| --- | --- |
| `drift_seconds` | 수정 직전에 측정한 오차 |
| `drift_seconds_per_day` | 자동 모드의 기준이 되는 평활화된 오차율 |
| `write_compensation_seconds` | 시각 표본 채취부터 목표 초 경계까지의 시간(초). 연결 지연과 경계를 기다리는 시간을 합친 값 |

**시계 오차** — 마지막으로 *측정한* 기기 시계 오차(초)입니다. 부호가 있으며 양수는
화면의 시계가 빠르다는 뜻입니다. 시간에 따른 모양이 중요하므로 속성이 아닌 센서로
제공합니다. 온습도 폴링을 켜면 동기화 사이에서 점차 증가하고 동기화할 때마다
돌아오며, 상승 기울기가 가팔라지는 기기는 배터리가 줄어드는 기기입니다.
`clock_checked` 속성은 측정 시각을 나타냅니다.

동기화 후의 값은 0으로 가정하지 않고 쓰기 직후 다시 읽어 측정한 값입니다.
기기는 정수 초를 저장하므로 목표와 정확히 일치하는 것은 일반적인 결과가 아니라
운이 좋은 경우입니다. 온습도 폴링이 없으면 이 센서는 동기화할 때마다 한 번 갱신됩니다.

**측정값이 약 1초 범위에서 흩어질 수 있습니다.** 시계는 정수 초로 응답하므로 epoch N은
기기가 [N, N+1) 범위 어딘가에 있다는 뜻일 뿐입니다. 이 구간의 중간값을 보고하므로
편향은 없지만 1초 폭 안 어디에나 위치할 수 있습니다. 구간 내 위치는 폴링 시점과
기기 자체 틱의 상대적인 시점에 따라 결정되며, 연결 설정 시간도 매번 수백 밀리초씩
달라집니다. 따라서 천천히 이동하는 대신 폴링마다 새로 정해집니다. 왕복 연결의
비대칭도 약간의 오차를 추가합니다.

이 잡음의 크기는 약 1초인 반면 정확한 기기의 오차는 하루에 1초 미만입니다.
따라서 하루 이력은 경사보다 산포로 보이며 추세가 잡음을 넘어서려면 1~2주가
걸립니다. 더 빨리 보려면 평균을 사용하세요. 오차 센서에 24시간 구간과 `mean`을
사용하는 **통계** 도우미를 적용하면 산포가 약 5배 줄어듭니다. 각 측정 오차는
천천히 이동하는 것이 아니라 독립적으로 정해지기 때문입니다.

**다음 동기화** — 다음 자동 동기화 예정 시각입니다. 자동 동기화가 꺼져 있으면
`unknown`이며 속성에도 그 상태가 명시됩니다.

| 속성 | 의미 |
| --- | --- |
| `auto_sync` | `off`, `auto` 또는 설정한 일수 |
| `interval_days` | 적용 중인 주기. 실패 후 대기 시간 증가의 영향을 받지 않음 |
| `drift_seconds_per_day` | 간격 계산에 사용한 오차율 |

따라서 `state_attr('sensor.lywsd02_xxxx_next_sync', 'auto_sync') == 'off'`만으로
시계가 더 이상 수정되지 않는 기기에 대한 알림을 만들 수 있습니다.

---

## 엔티티

| 플랫폼 | 엔티티 | 설명 |
|----------|--------|-------|
| 센서 | 온도 / 습도 | 주기적인 GATT 폴링. **온습도 센서 활성화** 필요 |
| 센서 | 배터리 | 자동 동기화를 포함한 모든 열린 연결에서 읽기 |
| 센서 | 마지막 동기화 / 다음 동기화 | 진단용. 오차 및 일정 속성([시계 진단](#시계-진단) 참고) |
| 센서 | 시계 오차 | 진단용. 측정한 시계 오차(초)를 모든 폴링과 동기화마다 갱신 |
| 센서 | 실패 횟수 / 마지막 실패 | 진단용 |
| 센서 | 연결 시간 | 진단용. 마지막/현재 BLE 세션이 열린 시간(초) |
| 이진 센서 | 연결 상태 | BLE 세션 열림 / 닫힘 |
| 선택 | 표시 단위 | °C / °F. E-Ink 화면에만 적용 |
| 선택 | 시계 모드 | 12시간 / 24시간. E-Ink 화면에만 적용 |
| 버튼 | 시각 동기화 | 현재 Home Assistant 시각을 E-Ink 시계에 기록 |

---

## 서비스

### `xiaomi_lywsd.sync_time`

한 번 연결하여 현재 시각(지정한 경우 `timezone_offset` 사용)을 기록하고 자동 동기화 일정을 다시 설정합니다.

| 매개변수 | 필수 | 기본값 | 설명 |
|-----------|----------|---------|-------------|
| `timezone_offset` | 아니요 | Home Assistant 시간대 | UTC 오프셋(시간 단위, `-12`~`14`) |

```yaml
action: xiaomi_lywsd.sync_time
target:
  device_id: <your device>
```

### `xiaomi_lywsd.read_state`

한 번 연결하여 기기에서 **표시 단위** 상태를 갱신합니다.

```yaml
action: xiaomi_lywsd.read_state
target:
  device_id: <your device>
```

### `xiaomi_lywsd.dump_gatt`

한 번 연결하여(Bluetooth 프록시 포함) 읽을 수 있는 특성의 값을 16진수로 포함한 전체
GATT 서비스 트리를 반환합니다. **개발자 도구 → 작업**에서 **응답 변수**와 함께
사용하세요. 독립 실행형 `tools/dump_gatt.py` 스크립트는 프록시로만 보이는 기기에
접근할 수 없습니다.

```yaml
action: xiaomi_lywsd.dump_gatt
target:
  device_id: <your device>
```

---

## 0.1.x에서 업그레이드

처음 로드할 때 구성 항목을 버전 2로 마이그레이션합니다. `auto_sync_hours`는 일 단위
`auto_sync` 선택으로 바뀌며(**옵션을 한 번도 변경하지 않은 설치는 0.1.x 기본값대로
꺼짐을 유지**), 초 단위로 저장된 폴링 간격은 분 단위로 바뀝니다.

`sensor.*_clock_drift`는 더 이상 생성되지 않으며 값은 `last_sync` 속성으로 이동했습니다.
기존 엔티티는 직접 삭제할 때까지 레지스트리에 사용할 수 없는 상태로 남습니다.

0.2.1부터 일정에 별도 엔티티가 생겨 `next_sync`는 **더 이상 `last_sync`의 속성이
아닙니다**. 대신 `sensor.*_next_sync`를 읽으세요. 0.2.0의 속성을 사용한 템플릿은
수정해야 합니다.

---

## 개발

현재 테스트 환경은 Python 3.14 / Home Assistant 2026.10.2입니다. 지원 최소는 Home Assistant 2025.1.0으로 유지하며 Python 3.13과 `requirements-test-minimum.txt`로 별도 검증합니다.

```bash
pip install -r requirements-test.txt -r requirements_lint.txt
python -m ruff check custom_components/ tests/ tools/
python -m pytest tests/components/xiaomi_lywsd/ -v
```

독립 실행형 프로토콜 조사 도구(Mac / 직접 BLE 접근이 가능한 어댑터 전용.
프록시 뒤 기기는 위의 `xiaomi_lywsd.dump_gatt` 참고):

```bash
python tools/dump_gatt.py AA:BB:CC:DD:EE:FF
python tools/probe_climate.py AA:BB:CC:DD:EE:FF
python tools/probe_time.py AA:BB:CC:DD:EE:FF -5
python tools/probe_units.py AA:BB:CC:DD:EE:FF
```

---

## 참고 자료

- [`docs/protocol.md`](docs/protocol.md) — 이 통합에서 역공학으로 정리한 GATT 특성 참고 자료
- [h4/lywsd02](https://github.com/h4/lywsd02) — GATT UUID / 데이터 형식 참고 구현
- [ashald/home-assistant-lywsd02](https://github.com/ashald/home-assistant-lywsd02) — 12시간/24시간 시계 모드 데이터 형식 참고 자료
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
