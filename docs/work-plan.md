# 작업 계획서 — `xiaomi_lywsd`

LYWSD02(MMC) E-Ink 온습도계를 **GATT active connection**으로 제어·수집하는 Home Assistant 커스텀 통합.
이 문서는 **다른 에이전트가 콜드 스타트로 집어들어 그대로 실행**할 수 있도록 쓰였다. 각 태스크는
건드릴 파일, 변경 내용, 필요한 데이터, 테스트, 완료 기준을 명시한다.

- 도메인: `xiaomi_lywsd`
- 작업 디렉터리: `/Users/eigger/Documents/GitHub/hass-lywsd02` (현재 **완전히 비어 있음**, git 저장소 아님)
- 참조 구현: `../hass-niimbot`, `../hass-gicisky`, `../core` (HA 코어 클론)

> **개정 이력.** 초판은 "코어 `xiaomi_ble`가 온습도 센서를 제공하므로 이 통합은 센서를 만들지
> 않는다"를 전제했다. **실제 광고 캡처로 이 전제가 틀렸음이 확정됐다** — 이 기기(device_id
> `0x2542`)의 MiBeacon 프레임에는 sensor object가 실리지 않으며, 암호화 문제도 아니다.
> 온습도는 GATT notify로만 나온다. 이 개정판은 온습도/배터리 수집을 1차 기능으로 승격하고
> 아키텍처를 폴링형으로 바꾼다. 근거는 §0.3, 뒤집힌 결정 목록은 §6.1.

---

## 0. 시작 전 확인 사항

### 0.1 저장소가 비어 있다

`hass-lywsd02/`에는 이 문서 외에 아무것도 없다. `git init`부터 T0에서 수행한다.

### 0.2 리포지토리명 불일치 — 결정 필요

기획서는 리포지토리명을 `hass-lywsd02mmc`로 적었으나 실제 로컬 디렉터리는 `hass-lywsd02`다.
**로컬 디렉터리명을 그대로 `hass-lywsd02`로 확정하고**, `manifest.json`의 `documentation` /
`issue_tracker`를 `https://github.com/eigger/hass-lywsd02`로 쓴다. 리네임은 GitHub 원격 생성 시
유지보수자가 결정할 사항이며, 에이전트가 임의로 디렉터리를 옮기지 않는다.

### 0.3 코어 `xiaomi_ble`가 온습도를 주지 못하는 이유 — **실측 확인됨**

이 절이 이 계획서 전체의 전제다. 초판에서는 추론이었으나, **실제 광고 캡처로 확정됐다.**

#### 캡처된 광고 (2026-08-22, ESPHome 프록시 `44:1B:F6:85:C3:BA` 경유)

```
raw : 0201060f1695fe305a422500c4c51638c1a4080b094c5957534430324d4d43
      └flags┘ └── service data 0xFE95 (12B) ──────┘└ local name "LYWSD02MMC" ┘
```

`tools/decode_mibeacon.py 305a422500c4c51638c1a408` 출력:

| 필드 | 값 | 의미 |
| --- | --- | --- |
| `frctrl` | `0x5A30` | MiBeacon **v5** |
| `device_id` | **`0x2542`** | LYWSD02MMC (`devices.py`에 등록돼 있음) |
| **`object_include`** | **`0`** | **센서 payload 없음 ← 근본 원인** |
| `is_encrypted` | `0` | **암호화 아님. bindkey는 무관하다** |
| `capability_include` | `1` (`0x08`) | capability 프레임 |
| `mac_include` | `1` | `A4:C1:38:16:C5:C4` (주소와 일치) |
| `registered` | `0` | Mi Home에 바인딩되지 않은 상태 |
| `solicited` | `1` | "바인딩 요청" 프레임 |
| `frame_counter` | `0` | |
| 잔여 바이트 | 없음 | 실을 payload가 아예 없다 |

#### 이것이 코어에서 어떻게 버려지는가

`~/.cache/uv/.../xiaomi_ble/parser.py:2150` — 정확히 이 프레임이 걸리는 분기:

```python
# check that data contains object
if frctrl_object_include == 0:
    _LOGGER.debug("Advertisement doesn't contain payload, adv: %s", data.hex())
    return False
```

경고도 아니고 `debug`다. 사용자에게는 **"기기는 발견되는데 엔티티가 안 생긴다"**로만 보인다.
`devices.py`에 `0x2542 → LYWSD02MMC`가 있으므로 이름과 모델은 정상 표시된다 — 그래서 더 헷갈린다.

#### 확정된 사실 세 가지

1. **실패 모드는 A(payload 없음)다. B(암호화)가 아니다.** `is_encrypted=0`이므로 bindkey를
   구해도 아무것도 달라지지 않는다. LYWSD02MMC의 Telink Flasher 키 추출 실패 사례를 쫓을
   필요가 없다 — **README와 이슈 템플릿에서 bindkey 얘기를 뺀다.**
2. **코어는 이 기기를 GATT로 폴링하지 않는다.** `parser.py:2428` `poll_needed()`:
   ```python
   if self.device_id not in [0x03BC, 0x0098]:
       return False
   ```
   `0x2542`는 목록에 없다. **이 통합이 GATT를 점유해도 코어와 경합하지 않는다.**
   초판 §7의 최상위 리스크가 여기서 소멸한다.
3. **온습도는 GATT notify로만 나온다.** `EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6`에 구독하면
   `<hB`(int16 LE 온도 ÷100, uint8 습도)가 올라온다.
   ([h4/lywsd02](https://github.com/h4/lywsd02), [lhvo/LYWSD02MMC](https://github.com/lhvo/LYWSD02MMC))

#### 광고에서 함께 확인된 구현 제약

- **`service_uuids`가 비어 있다.** 16-bit 서비스 UUID 목록이 광고에 없으므로 manifest의
  `service_uuid` 매처는 **이 기기를 절대 못 잡는다.** `local_name` 또는 `service_data_uuid`만
  유효하다. T3의 매처 선택이 이걸로 검증됐다.
- **`local_name`은 매 광고에 실린다** (`0x09` complete local name = `LYWSD02MMC`).
  → `{"local_name": "LYWSD02*"}` 매처가 동작한다.
- **`connectable: true`, source가 ESPHome 프록시.** 유지보수자 환경은 이미
  `bluetooth_proxy: active: true`가 켜져 있다. T9(repair issue)는 유지보수자 본인이 아니라
  **다른 사용자를 위한** 것이다.

#### 남은 불확실성 (T1에서 닫을 것)

이 캡처는 **한 개의 프레임**이다. "이 기기는 절대 sensor 프레임을 안 보낸다"를 증명하려면
장시간 관찰이 필요하다. `registered=0 / solicited=1`은 **미바인딩 상태의 광고**이고, Mi Home에
바인딩된 뒤에는 event 프레임(그때는 암호화될 가능성이 높다)을 보내기 시작할 수도 있다.

> **판정 기준은 단순하다: `service_data[0xFE95][0] & 0x40`.**
> 이 비트가 `object_include`다. 30~60분 캡처해서 **한 번이라도 세워지는 프레임이 있는지** 본다.
> 없으면 모드 A 확정. 있으면 그 프레임을 `tools/decode_mibeacon.py`에 넣어 암호화 여부를 본다.
>
> 어느 쪽이든 **이 통합의 설계는 바뀌지 않는다** — Mi Home 바인딩 없이 값을 얻는 것이 목적이고,
> 그 경로는 GATT뿐이다. 달라지는 것은 README 문구와 이슈 대응 비용뿐이다.

**결론 — 포지셔닝 변경.** 이 통합은 "코어를 보완하는 GATT 제어 도구"가 아니라
**"코어가 구조적으로 값을 줄 수 없는 LYWSD02 계열(device_id `0x2542` 확인)을 GATT로 완전히
커버하는 통합"**이다.


### 0.4 프로토콜은 여전히 실측으로 확정한다

아래 표는 [h4/lywsd02](https://github.com/h4/lywsd02)에서 확인한 **참조 구현값**이다. 초판의
추측표보다 신뢰도가 높지만 여전히 펌웨어 리비전 편차가 있으므로 T1에서 실측 확인한다.

| Characteristic | 용도 | 접근 | 페이로드 |
| --- | --- | --- | --- |
| `EBE0CCB7-7A0A-4B0C-8A1A-6FF2997DA3A6` | 시간 | R/W | `<Ib` — uint32 LE epoch + **int8**(부호 있음) tz offset(hour) = 5바이트. read 시 4바이트만 오는 펌웨어도 있어 참조 구현이 5/4 양쪽을 처리한다 |
| `EBE0CCBE-7A0A-4B0C-8A1A-6FF2997DA3A6` | 표시 단위 | R/W | `b'\xff'` = **°C**, `b'\x01'` = **°F** |
| `EBE0CCC1-7A0A-4B0C-8A1A-6FF2997DA3A6` | 온습도 | **Notify** | `<hB` — int16 LE 온도(÷100) + uint8 습도 |
| `EBE0CCC4-7A0A-4B0C-8A1A-6FF2997DA3A6` | 배터리 | R | uint8 percent |
| `EBE0CCBC-7A0A-4B0C-8A1A-6FF2997DA3A6` | 이력 | Notify | `<IIhBhB` — index, timestamp, max temp, max humidity, min temp, min humidity |

**초판에서 정정된 값 두 가지:**
- 단위 코드는 `0x00`/`0xFF`가 아니라 **`0xFF`=°C / `0x01`=°F**. 방향이 직관과 반대이므로
  주의한다.
- tz offset은 `uint8`이 아니라 **`int8`(signed)**. 참조 구현이 `'Ib'`(소문자 b = signed char)를
  쓴다.

---

## 1. 참조 코드 지도

새로 설계하지 말고 아래 파일의 검증된 패턴을 가져다 쓴다. 두 리포는 같은 유지보수자의 것이고
관례가 일관되다.

| 필요한 것 | 참조 파일 | 가져올 내용 |
| --- | --- | --- |
| **폴링 코디네이터 + 연결당 1사이클** | `hass-niimbot/custom_components/niimbot/__init__.py` (`DataUpdateCoordinator` + `CONF_SCAN_INTERVAL`), `niimprint/parser.py:592` `update_device` | 이 통합의 **주 구조**. 스캔 주기마다 연결→읽기→해제 |
| BLE 연결 수명 관리 | `hass-gicisky/.../gicisky_ble/writer.py:44-80` | `establish_connection` → 작업 → `finally` disconnect, `disconnect_on_missing_services` 데코레이터 |
| 연결 전 stale 정리 | `hass-niimbot/.../__init__.py:112` | `close_stale_connections_by_address(address)` |
| notify 구독 + 응답 대기 | `hass-gicisky/.../gicisky_ble/writer.py` (`start_notify` + `asyncio.Event` + `wait_for`) | 온습도 notify 1건을 타임아웃과 함께 기다리는 패턴 |
| BLE 접근 직렬화 락 | `hass-gicisky/.../__init__.py` (`hass.data[DOMAIN][LOCK]`) | 도메인 전역 `asyncio.Lock` |
| 재시도 + 실패 카운터 | `hass-gicisky/.../__init__.py` (`execute_write_core`) | `max_retries`, 실패 시 `HomeAssistantError`, 실패 횟수/시각 |
| config flow (BT 발견 + 확인) | `hass-gicisky/custom_components/gicisky/config_flow.py` | `async_step_bluetooth` / `bluetooth_confirm` / `user` 3단 구조 |
| options flow | 같은 파일 `OptionsFlowHandler` | `OptionsFlowWithReload` + `add_suggested_values_to_schema` |
| 센서 엔티티 | `hass-niimbot/custom_components/niimbot/sensor.py` | `CoordinatorEntity` + `SensorEntityDescription` 테이블 |
| 버튼 엔티티 + 에러 매핑 | `hass-niimbot/custom_components/niimbot/button.py` | `_get_ble_device()`, `_reraise_action_error()`, `DeviceInfo` |
| 상태 복원 엔티티 | `hass-gicisky/custom_components/gicisky/switch.py` | `RestoreEntity` + `translation_key` + `EntityCategory.CONFIG` |
| services.yaml / icons.json | `hass-niimbot/.../services.yaml`, `icons.json` | 필드 셀렉터, 아이콘 키 구조 |
| 테스트 하네스 | `hass-niimbot/tests/conftest.py` | `sys.modules[...] = MagicMock()`로 HA 없이 pytest |
| CI | `hass-niimbot/.github/workflows/{validate,tests}.yml` | hassfest + HACS, ruff, py3.12/3.13/3.14 |
| ruff 설정 | `hass-niimbot/ruff.toml` | `select=["E","F"]`, `ignore=["E501"]` |

---

## 2. 모든 태스크에 적용되는 규칙

**태스크 하나 = 커밋(또는 PR) 하나.** 의존 그래프가 명시하지 않는 한 태스크는 서로 독립이다.

**엔티티 `unique_id` / `translation_key`는 한 번 정하면 바꾸지 않는다.** 사용자 엔티티 레지스트리에
남아 고아 엔티티와 히스토리 손실을 만든다. 추가는 안전, 개명·삭제는 마이그레이션 대상이다.

**번역은 항상 세 파일 세트.** 새 엔티티/서비스 필드/옵션마다 `strings.json`,
`translations/en.json`, `translations/ko.json`. 한국어는 1급 언어다. 한국어 문구를 못 쓰겠으면
영어를 `ko` 키에 넣지 말고 PR 본문에 그렇게 적는다.

**`[HW]` 표시는 실물 없이는 검증 불가라는 뜻이다.** 기존 동작을 fallback으로 남기고, 미검증
경로를 기본값으로 만들지 않으며, PR 본문에 유지보수자가 확인할 항목을 나열한다.
`[HW]` 항목을 "검증했다"고 쓰지 않는다.

**테스트는 하드웨어 없이 돈다.** `tests/conftest.py`가 `homeassistant`/`bleak`를 목으로 치환하고,
`tests/fake_client.py`가 write 바이트를 기록하고 정해진 read/notify를 재생한다. 태스크마다
`BleakClient`를 즉석 모킹하지 말고 이 fake를 확장한다.

**연결은 사이클 단위로 열고 닫는다.** 한 번 연결했으면 그 안에서 **필요한 모든 것**(온습도 notify,
배터리, 필요 시 단위 read)을 끝내고 즉시 끊는다. 연결을 상시 유지하지 않는다. niimbot의
`keep_connection` 옵션은 이식하지 않는다.

**BLE 예외가 코디네이터 갱신 경로로 새어나가면 안 된다.** `_async_update_data`에서 raise하면
HA가 이를 "Unable to fetch data"로 삼켜 **모든 엔티티가 조용히 멈춘다.** 폴링 실패는
`UpdateFailed`로만 올리고, 사용자 트리거(버튼/서비스/select) 실패만 `HomeAssistantError`로 올린다.

**`manifest.json`의 `version`은 태스크 PR에서 올리지 않는다.** 릴리스는 유지보수자가 묶는다.

**커밋 전 필수:** `python -m ruff check custom_components/ tests/ tools/` 와 `python -m pytest tests/ -v`.

---

## 3. 아키텍처 결정

### 3.1 폴링형 코디네이터 (초판에서 변경)

온습도를 GATT notify로 가져와야 하므로 **주기적 연결이 불가피하다.** 따라서 niimbot 구조를 쓴다:

```python
# coordinator.py
class LywsdCoordinator(DataUpdateCoordinator[LywsdData]):
    def __init__(self, hass, entry, device, address, scan_interval):
        super().__init__(hass, _LOGGER, name=DOMAIN,
                         update_interval=timedelta(seconds=scan_interval))

    async def _async_update_data(self) -> LywsdData:
        # async_execute 로 한 번 연결 → 한 사이클에서 전부 수집
        ...
```

```python
@dataclass
class LywsdData:
    temperature: float | None = None
    humidity: int | None = None
    battery: int | None = None
    units: str | None = None            # "celsius" | "fahrenheit"
    last_sync: datetime | None = None
    last_drift_seconds: float | None = None
    failure_count: int = 0
    last_failure: datetime | None = None
```

**한 폴링 사이클의 순서 (연결 1회 안에서):**

1. `close_stale_connections_by_address(address)`
2. `establish_connection(BleakClient, ble_device, address)`
3. `start_notify(UUID_DATA)` → `asyncio.Event`로 **첫 notify 1건**을 `wait_for(timeout=15)` 대기
4. `stop_notify(UUID_DATA)`
5. `read_gatt_char(UUID_BATTERY)`
6. (옵션이 켜져 있고 아직 모를 때만) `read_gatt_char(UUID_UNITS)`
7. `disconnect()`

3에서 타임아웃이 나면 `UpdateFailed`. **notify를 계속 붙들고 여러 건을 모으지 않는다** — 1건이면
충분하고, 연결 시간이 곧 배터리다.

### 3.2 스캔 주기

- `CONF_SCAN_INTERVAL`, `DEFAULT_SCAN_INTERVAL = 30` (**분**). CR2032 코인셀 기준 보수적 기본값.
  UI 단위는 `min`, 범위 2–60. 예전 설치는 초(≥120)로 저장돼 있을 수 있어 코디네이터가 호환 변환한다.
- 하한 **2분**. 그 이하는 셀렉터에서 선택할 수 없게 막는다. E-Ink 시계 자체가 화면을 1분 단위로
  갱신하므로 그보다 촘촘히 읽을 이유가 없고, 배터리만 깎는다.
- **LYWSD02 / LYWSD02MMC는 CR2032 코인셀**이다 (AAA가 아님). BLE 연결 유지 시간이 곧 소모이므로
  폴링 예산을 타이트하게 잡는다. README에 장기 수명 데이터가 아직 없다고 명시한다.
- `CONF_CLIMATE_SENSORS=False`면 `update_interval=None` — **폴링을 완전히 끈다** (엔티티만 숨기고
  주기마다 연결하던 버그를 피한다).
- `CONF_AUTO_SYNC_HOURS` 기본값 **0** (비활성). 옵션으로 24h / 7d.
### 3.3 코어 `xiaomi_ble`와의 관계

- **중복 위험은 낮지만 0은 아니다.** 사용자의 기기에서는 코어가 값을 못 주지만, 다른 펌웨어/
  다른 개체에서는 코어가 정상 동작할 수 있다. 이 경우 온습도 센서가 두 벌 생긴다.
- 대응: config flow / options에 `CONF_CLIMATE_SENSORS` (기본 **False** — 시계 전용).
  켜면 온습도/배터리 엔티티를 만들고 주기적 GATT 폴링을 시작한다. 끄면 엔티티도 폴링도 없다.
  초판의 "센서 최소주의"가 기본값이 된다.
- **연결 경합은 없다.** §0.3(3) — 코어는 이 device_id를 폴링하지 않는다.
- 같은 BLE 주소를 `connections={(CONNECTION_BLUETOOTH, address)}`로 쓰므로 두 통합의 엔티티가
  **하나의 디바이스 카드에 합쳐진다.** `manufacturer="Xiaomi"`, `model="LYWSD02MMC"`로 맞춘다.

### 3.4 select의 현재 상태

단위 read는 연결이 필요하지만 폴링 사이클에 이미 연결이 있으므로, **모르는 동안만 읽는다**:
값을 한 번 확보하면 이후 사이클에서는 읽지 않고(연결 시간 절약) write 성공 시 낙관적으로 갱신한다.
`RestoreEntity`로 재시작 시 마지막 값을 복원한다(gicisky `switch.py` 패턴).
`xiaomi_lywsd.read_state` 서비스로 강제 재읽기를 제공한다.

### 3.5 엔티티 키 확정 (변경 금지)

`identifier = address.replace(":", "")[-8:]`, 디바이스 표시명 `LYWSD02 {identifier}`.

| 플랫폼 | `translation_key` | `unique_id` | 비고 |
| --- | --- | --- | --- |
| `sensor` | `temperature` | `xiaomi_lywsd_{id}_temperature` | `device_class: temperature`, `°C` 고정(HA가 사용자 단위로 변환) |
| `sensor` | `humidity` | `xiaomi_lywsd_{id}_humidity` | `device_class: humidity`, `%` |
| `sensor` | `battery` | `xiaomi_lywsd_{id}_battery` | `device_class: battery`, `DIAGNOSTIC` |
| `sensor` | `last_sync` | `xiaomi_lywsd_{id}_last_sync` | `device_class: timestamp`, `DIAGNOSTIC` |
| `sensor` | `clock_drift` | `xiaomi_lywsd_{id}_clock_drift` | `s`, `DIAGNOSTIC`, 기본 비활성 |
| `button` | `sync_time` | `xiaomi_lywsd_{id}_sync_time` | |
| `select` | `display_units` | `xiaomi_lywsd_{id}_display_units` | `CONFIG` |

> **온도 센서의 단위 주의.** GATT가 주는 값은 항상 섭씨다(표시 단위 설정과 무관). 엔티티의
> `native_unit_of_measurement`는 **항상 `°C`**로 두고, 화면 표시 단위 전환은 HA가 처리하게 한다.
> `select.display_units`는 **E-Ink 화면 표시**만 바꾸며 센서 값에 영향을 주지 않는다. 이 구분을
> 번역 문구에 명시한다 — 혼동이 확실히 생기는 지점이다.

---

## 4. 대상 구조

```
hass-lywsd02/
├── custom_components/xiaomi_lywsd/
│   ├── __init__.py           # setup/unload, async_execute, 서비스, 자동 동기화
│   ├── manifest.json
│   ├── config_flow.py
│   ├── const.py
│   ├── coordinator.py        # LywsdCoordinator, LywsdData
│   ├── types.py
│   ├── device/
│   │   ├── __init__.py       # 모델 dispatch
│   │   ├── base.py           # 추상 인터페이스
│   │   └── lywsd02mmc.py     # GATT 구현
│   ├── sensor.py
│   ├── button.py
│   ├── select.py
│   ├── services.yaml
│   ├── icons.json
│   ├── strings.json
│   └── translations/{en,ko}.json
├── tools/{decode_mibeacon.py,dump_gatt.py,probe_time.py,probe_units.py,probe_climate.py}
│                              # decode_mibeacon.py 는 이미 작성돼 있음 (§0.3)
├── tests/{conftest.py,fake_client.py,test_protocol.py,test_coordinator.py,
│          test_config_flow.py,test_entities.py,test_translations.py}
├── docs/{work-plan.md,protocol.md}
├── .github/workflows/{validate.yml,tests.yml}
├── .github/ISSUE_TEMPLATE/bug_report.yml
├── hacs.json, ruff.toml, requirements-test.txt, README.md, LICENSE, .gitignore
```

---

## 5. 의존 그래프

```
T0 (스캐폴딩) ──┬── T11 (테스트 하네스) ── T12 (CI)
                ├── T1 (Phase 0 실측 + 코어 실패 모드 판정)
                │        └── T2 (device 레이어) ──┬── T4 (coordinator/폴링) ── T5 (sensor)
                │                                 ├── T6 (button)
                │                                 └── T7 (select)   [T1-d 성공 시에만]
                └── T3 (manifest + config flow) ──┘

T8 (자동 동기화)   ← T6
T9 (프록시 repair) ← T3
T10 (진단 센서)    ← T6
T13 (README)       ← 마지막
T14 (이력)         ← Phase 3, 별도 판단
```

**권장 순서: T0 → T11 → T12 → T1 → T2 → T3 → T4 → T5 → T6 → T7 → T9 → T8 → T10 → T13.**

T11/T12를 앞에 두는 이유: 테스트와 린트가 먼저 돌아야 T2 이후 모든 태스크가 자기 검증을 갖는다.
**T5(sensor)가 이 통합의 새로운 MVP 기준선이다** — 초판에서는 T4(button)이었다.

---

# Phase 0 — 스캐폴딩과 프로토콜 확정

## T0 — 저장소 스캐폴딩

**목표.** 빈 디렉터리를 HACS 설치 가능한 최소 골격으로 만든다.

**변경.**

1. `git init` (기본 브랜치 `main`), `.gitignore` — `../hass-niimbot/.gitignore` 복사
   (`__pycache__/`, `.ruff_cache/`, `.pytest_cache/`, `.DS_Store` 포함 확인).
2. `LICENSE` — MIT, 저작권자 `eigger`.
3. `hacs.json`: `{ "name": "Xiaomi LYWSD", "homeassistant": "2025.1.0" }`
4. `ruff.toml` — `../hass-niimbot/ruff.toml` 주석까지 그대로 복사.
5. `manifest.json` — **`bluetooth` 매처는 T3에서 채우고 여기서는 빈 배열**:
   ```json
   {
     "domain": "xiaomi_lywsd",
     "name": "Xiaomi LYWSD",
     "bluetooth": [],
     "codeowners": ["@eigger"],
     "config_flow": true,
     "dependencies": ["bluetooth_adapters"],
     "documentation": "https://github.com/eigger/hass-lywsd02",
     "integration_type": "device",
     "iot_class": "local_polling",
     "issue_tracker": "https://github.com/eigger/hass-lywsd02/issues",
     "requirements": [],
     "version": "0.1.0"
   }
   ```
   `requirements`는 빈 배열이다. `bleak` / `bleak-retry-connector`는 HA 코어가 제공하므로
   선언하지 않는다 (niimbot/gicisky도 선언하지 않는다).
6. `const.py` — `DOMAIN = "xiaomi_lywsd"`, `LOCK = "lock"`, 옵션 키/기본값. 값은 T3/T4/T8에서
   추가하되 파일은 지금 만든다.
7. `types.py` — gicisky `types.py`와 같은 형태의 `LywsdConfigEntry` 별칭.
8. 빈 `strings.json` / `translations/{en,ko}.json` 골격.

**완료 기준.** manifest가 유효한 JSON. 초기 커밋 1개.

---

## T1 — 프로토콜 실측 + 코어 실패 모드 판정 `[HW]`

**목표.** §0.3/§0.4의 참조값을 실측으로 확정하고, `docs/protocol.md`를 만든다.
**이 문서가 이후 모든 프로토콜 구현의 유일한 근거다.**

**파일.** `tools/dump_gatt.py`, `tools/probe_time.py`, `tools/probe_units.py`,
`tools/probe_climate.py`, `docs/protocol.md`.

**변경.**

`tools/`는 **HA에 의존하지 않는 단독 asyncio 스크립트**다. `bleak`만 임포트하고 MAC을 `argv[1]`로
받는다. `custom_components/`에서 아무것도 임포트하지 않는다.

**실측 절차 (순서 지킬 것).**

- **a0. 광고 장시간 캡처 — 모드 A 확정.** §0.3에서 프레임 1개는 이미 디코딩했고
  (`object_include=0`, 비암호화, device_id `0x2542`), `tools/decode_mibeacon.py`도 이미 있다.
  남은 것은 **"한 번도 sensor 프레임을 안 보낸다"의 확인**뿐이다.
  - HA `configuration.yaml`에 `logger: logs: { homeassistant.components.bluetooth: debug,
    xiaomi_ble: debug }`를 넣고 재시작 후 **30~60분** 관찰.
  - 판정 비트: `service_data["0000fe95-…"][0] & 0x40`. 캡처된 모든 프레임에서 0이면 **모드 A
    확정** — 코어는 이 기기에서 구조적으로 센서를 만들 수 없다.
  - 한 번이라도 1이면 그 프레임을 `tools/decode_mibeacon.py`에 넣어 `is_encrypted`를 본다.
    1이면 모드 B(암호화)이고, README에 "bindkey를 구하면 코어로도 된다"를 추가해야 한다.
  - `frame_counter`가 계속 `0`으로 고정인지도 기록한다. 고정이라면 이 기기가 event 프레임을
    아예 만들지 않는다는 강한 방증이다.
  결과를 `docs/protocol.md` 최상단에 적는다. **어느 쪽이 나와도 이 통합의 설계는 바뀌지 않는다.**
- **a. `dump_gatt.py`** — 전체 service/characteristic 트리 + read 가능한 값 hex 덤프.
  결과를 `docs/protocol.md`에 그대로 붙인다.
- **b. 펌웨어 버전** — DIS `0x180A`의 `0x2A26`, 없으면 Mi Home 앱 화면.
  **"이 문서는 펌웨어 X.Y.Z, device_id 0xNNNN 1대에서 실측했다"**를 최상단에 명시.
- **c. `probe_climate.py`** — `EBE0CCC1` notify 구독 → 첫 notify까지 걸린 시간 측정 → 10건 수집 →
  간격 기록. **동시에 plain `read_gatt_char(EBE0CCC1)`도 시도해서 유효값이 나오는지 확인**한다
  (참조 구현은 notify만 쓴다. read가 되면 사이클이 더 짧아지므로 확인 가치가 있다).
  기록할 것: 첫 notify 지연(§3.1의 timeout 값을 여기서 정한다), notify 간격, 원시 3바이트,
  디코딩 결과가 화면 표시와 일치하는지.
- **d. `probe_time.py`** — read → write(now) → 재read 왕복. **음수 tz(예: -5)를 실제로 써서**
  `int8`인지 확인한다. 한국(UTC+9)만 테스트하면 부호 문제를 놓친다. `response=True`/`False`
  각각의 성공 여부도 기록.
- **e. `probe_units.py`** — **현재 값 read → 반대 코드 write → E-Ink 화면 육안 확인 → 원복.**
  `0xFF`=°C / `0x01`=°F 가설을 검증하고, 실측값으로 양쪽을 적는다.
- **f. 프록시 경유 재현.** ESPHome BLE 프록시(`active: true`)를 통해 c/d/e를 한 번 더 수행.
  직결 어댑터에서만 되는 동작이 있는지 확인하고 별도 절에 기록.
- **g. 배터리** — `EBE0CCC4` read 값이 Mi Home 앱 표시와 일치하는지.

**`docs/protocol.md` 구성:**
```
# LYWSD02(MMC) GATT 프로토콜 (실측)
## 0. 측정 환경 — 펌웨어, device_id(0x2542), 어댑터/프록시, 측정일, 기기 대수, 광고 캡처 결과
## 1. 서비스/characteristic 전체 트리 (dump 원문)
## 2. 온습도 notify — 첫 notify 지연, 간격, 인코딩, plain read 가능 여부
## 3. 시간 — 페이로드, 부호, response 요구, read-back 지연
## 4. 표시 단위 — °C 코드 / °F 코드, 화면 반영 지연
## 5. 배터리
## 6. 이력 (Phase 3 — 확인된 만큼만, 미확인은 "미검증" 표시)
## 7. 미해결 / 재현 안 된 항목
```

**완료 기준.**
- notify로 온습도가 실제로 수신되고, 값이 E-Ink 화면 표시와 일치.
- 시간 write 후 read-back이 ±2초 이내 일치.
- 단위 write 후 화면이 실제로 바뀌고 원복도 확인.
- 프록시 경유 결과가 문서에 있음.
- 추측이 "추측"으로 표시돼 확정값과 섞이지 않음.

**차단 조건.** e가 실패하면 T7(select)을 계획에서 **뺀다.** 동작하지 않는 기능을 엔티티로
노출하지 않는다. c가 실패하면 **이 통합의 근거가 무너지므로 즉시 중단하고 유지보수자에게 보고**한다.

---

# Phase 1 — MVP

## T2 — device 레이어 (`device/`)

**목표.** GATT 동작을 HA에서 완전히 분리한다. 이 레이어는 `homeassistant`를 임포트하지 않는다 —
그래야 T11의 테스트가 HA 없이 돈다.

**의존.** T1 완료 필수.

**변경.**

1. `device/base.py`:
   ```python
   class LywsdDeviceError(Exception): ...
   class LywsdVerifyError(LywsdDeviceError):
       """write는 성공했으나 read-back이 기대값과 다르다."""

   @dataclass
   class ClimateReading:
       temperature: float      # °C
       humidity: int           # %

   @dataclass
   class SyncResult:
       written_epoch: int
       read_back_epoch: int
       drift_seconds: float    # write 직전 기기 시각 - HA 시각

   class LywsdDevice(ABC):
       MODEL: ClassVar[str]
       async def read_climate(self, client, timeout: float) -> ClimateReading: ...
       async def get_battery(self, client) -> int | None: ...
       async def set_time(self, client, when: datetime, tz_offset_hours: int) -> SyncResult: ...
       async def get_units(self, client) -> str: ...        # "celsius" | "fahrenheit"
       async def set_units(self, client, units: str) -> None: ...
       async def read_history(self, client): raise NotImplementedError
   ```
   메서드는 **이미 연결된 `BleakClient`를 인자로 받는다.** 연결 수립·해제는 `async_execute`의
   책임이다. 그래야 한 연결로 여러 동작을 묶을 수 있다.

2. `device/lywsd02mmc.py` — `docs/protocol.md`의 확정값만 사용.
   - `read_climate`: `start_notify` → `asyncio.Event` → `wait_for(timeout)` → `stop_notify`.
     `finally`에서 `stop_notify`를 시도하되 실패는 `warning`만 (gicisky writer 패턴).
     타임아웃은 `LywsdDeviceError`.
   - `set_time`: write **전에** 현재 값을 read해서 `drift_seconds` 계산 → write → read-back →
     허용오차(2초) 밖이면 `LywsdVerifyError`.
   - `set_units`: write → read-back → 불일치 시 **원래 값으로 되돌리고** `LywsdVerifyError`.
   - 인코딩/디코딩은 `_encode_time` / `_decode_time` / `_decode_climate` 같은 **순수 함수**로
     빼서 BLE 없이 테스트 가능하게 한다.

3. `device/__init__.py` — dispatch 테이블:
   ```python
   _MODELS: dict[str, type[LywsdDevice]] = {"LYWSD02MMC": Lywsd02mmc}

   def device_for(local_name: str | None) -> type[LywsdDevice] | None: ...
   ```
   `LYWSD02`와 `LYWSD02MMC` 두 광고명을 같은 클래스로 매핑. 모델 추가가
   **파일 1개 + 테이블 1줄**로 끝나야 한다.

**테스트.** `tests/test_protocol.py`:
- `_decode_climate(b"\x1a\x09\x37")` → 23.30 °C / 55 % (경계·음수 온도 포함).
- 음수 온도: int16 signed 처리가 맞는지 (`b"\xf0\xff..."` → -0.16 °C).
- `_encode_time` 왕복: UTC+9 / UTC-5 / UTC+0 / UTC+14, int8 경계(-12, +14).
- `set_time` read-back 불일치 → `LywsdVerifyError`.
- `set_units` 실패 시 원래 값 복구 write가 실제로 발생.
- `read_climate` 타임아웃 시 `stop_notify`가 호출되고 `LywsdDeviceError`가 뜬다.
- `device_for("LYWSD02")`, `device_for("LYWSD02MMC")`, `device_for("LYWSD03MMC") is None`.

**완료 기준.** `grep -rn "homeassistant" custom_components/xiaomi_lywsd/device/`가 빈 결과.

---

## T3 — manifest 매처와 config flow

**목표.** 자동 발견 + 수동 MAC 입력으로 config entry를 만든다.

**변경.**

1. `manifest.json`:
   ```json
   "bluetooth": [
     { "local_name": "LYWSD02*", "connectable": true }
   ]
   ```
   `connectable: true`가 핵심 — write/notify에는 연결 가능한 스캐너가 필요하므로, 비연결
   프록시만 보이는 환경에서는 발견되지 않아야 한다.
   **MiBeacon 서비스 UUID(`0000fe95-…`) 단독 매처를 추가하지 않는다.** 모든 Xiaomi BLE 기기가 걸린다.

   §0.3의 캡처가 이 선택을 검증한다:
   - 광고의 `service_uuids`가 **비어 있다** → `service_uuid` 매처는 이 기기를 못 잡는다. 쓰지 말 것.
   - `local_name`(`LYWSD02MMC`)은 매 광고에 실린다 → `local_name` 매처가 동작한다.
   - 더 좁히고 싶으면 **한 dict 안에** 두 조건을 넣는다(AND 의미):
     `{"local_name": "LYWSD02*", "service_data_uuid": "0000fe95-0000-1000-8000-00805f9b34fb",
     "connectable": true}`. 선택 사항이며, 단순함을 위해 기본은 `local_name` + `connectable`로 간다.

2. `config_flow.py` — gicisky `config_flow.py`의 3단 구조를 이식하되, `DeviceData` 대신
   T2의 `device_for(discovery_info.name)`로 지원 판정.
   - `async_step_bluetooth` → `async_set_unique_id(address)` → `_abort_if_unique_id_configured()`
     → 미지원이면 `async_abort("not_supported")`.
   - `async_step_bluetooth_confirm` — gicisky와 동일 (`onboarding.async_is_onboarded` 포함).
   - `async_step_user` — 발견 목록에서 선택. **gicisky에 없는 분기 추가:** 목록이 비면
     `async_abort("no_devices_found")` 대신 `async_step_manual`로 보낸다.
   - `async_step_manual` (신규) — MAC 입력, `^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$` 검증,
     실패 시 `errors={"base": "invalid_mac"}`. 대문자 정규화 후 `async_set_unique_id`.
     기기가 범위 밖이어도 entry는 만든다.
   - `title = f"LYWSD02 {identifier}"`, `data`에 `CONF_ADDRESS` 명시 저장.

3. `OPTIONS_SCHEMA` (config flow와 options flow가 공유 — niimbot 관례):
   | 키 | 셀렉터 | 기본값 |
   | --- | --- | --- |
   | `CONF_SCAN_INTERVAL` | number, min 2 / max 60 / step 1, unit `min` | 30 |
   | `CONF_CLIMATE_SENSORS` | boolean | `False` |
   | `CONF_RETRY_COUNT` | number, min 1 / max 5 | 3 |
   `CONF_AUTO_SYNC_HOURS`는 T8에서 추가.
   `CONF_CLIMATE_SENSORS`의 `data_description`에 §3.3의 중복 설명을 쓴다.

4. `OptionsFlowHandler(OptionsFlowWithReload)` — gicisky 패턴 그대로.

**테스트.** `tests/test_config_flow.py`:
지원/미지원 local_name, 중복 주소 abort, 수동 MAC 유효/무효/소문자 정규화, 옵션 하한(120s) 검증.

**완료 기준.** hassfest가 매처 스키마를 통과한다.

---

## T4 — coordinator와 `async_execute`

**목표.** 연결 1회 = 수집 1사이클. 이 통합에서 BLE에 접근하는 **유일한 경로**를 만든다.

**의존.** T2, T3.

**변경.**

1. `__init__.py`의 `async_setup_entry` (niimbot 구조를 축소):
   ```python
   PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.SELECT]
   ```
   - 도메인 전역 `asyncio.Lock`을 `hass.data[DOMAIN][LOCK]`에 1회 생성.
   - `LywsdCoordinator` 생성 → `entry.runtime_data`에 저장 → `async_config_entry_first_refresh()`.
     **첫 갱신 실패로 setup을 실패시키지 않는다** — 기기가 잠시 범위 밖일 수 있다.
     `ConfigEntryNotReady`를 던지지 말고 로그만 남기고 계속한다(다음 주기에 복구).
   - 디바이스 레지스트리: `connections={(CONNECTION_BLUETOOTH, address)}`,
     `manufacturer="Xiaomi"`, `model="LYWSD02MMC"`, `name=f"LYWSD02 {identifier}"`.

2. **`async_execute` 헬퍼:**
   ```python
   async def async_execute(hass, entry, op: Callable[[BleakClient, LywsdDevice], Awaitable[T]]) -> T:
       """락 획득 → stale 정리 → 연결 → op → 반드시 disconnect."""
   ```
   - a. `async with hass.data[DOMAIN][LOCK]:`
   - b. `ble_device = async_ble_device_from_address(hass, address, connectable=True)`
     → `None`이면 `LywsdDeviceError` (호출자가 문맥에 맞게 변환).
   - c. `await close_stale_connections_by_address(address)`
   - d. `client = await establish_connection(BleakClient, ble_device, ble_device.address)`
   - e. `op(client, device)` 실행. `max_retries`만큼 재시도, 재시도 사이 1초,
     **재시도는 연결부터 다시** (gicisky `execute_write_core` 패턴).
   - f. `finally`: `client.is_connected`면 `disconnect()`. 실패는 `warning`만.

3. `coordinator.py`의 `_async_update_data` — §3.1의 7단계를 `async_execute` 안에서 수행.
   - 예외는 **`UpdateFailed`로만** 변환한다 (§2 규칙).
   - 성공 시 `failure_count = 0`, 실패 시 `+1`, `last_failure = now()`.
   - **이전 값을 보존한다**: 이번 사이클에서 배터리를 못 읽었어도 온습도가 성공했으면 배터리는
     직전 값을 유지한다 (niimbot `_apply_rfid_info`의 "실패 시 이전 값 유지"와 같은 정책).

**테스트.** `tests/test_coordinator.py`:
- 한 사이클이 notify 구독 → 배터리 read → disconnect 순으로 진행한다.
- notify 타임아웃 시 `UpdateFailed`가 뜨고 `disconnect`가 호출된다.
- 락이 두 동시 호출을 직렬화한다.
- 재시도 3회 후 실패 시 `failure_count`가 1 증가한다.
- 부분 실패 시 직전 값이 보존된다.
- `_async_update_data`가 `UpdateFailed` 외의 예외를 밖으로 내보내지 않는다.

---

## T5 — `sensor` 플랫폼 — **MVP 기준선**

**목표.** 온도/습도/배터리 엔티티. **이 통합의 새로운 핵심 가치가 이 태스크다.**

**의존.** T4.

**변경.**

- niimbot `sensor.py`의 `SensorEntityDescription` 테이블 패턴을 쓴다. `CoordinatorEntity` 상속.
- §3.5의 키/디바이스클래스 표를 그대로 따른다.
- 온도 `native_unit_of_measurement = UnitOfTemperature.CELSIUS` **고정**, `suggested_display_
  precision=1`, `state_class=MEASUREMENT`.
- `CONF_CLIMATE_SENSORS`가 `False`면 temperature/humidity/battery를 **만들지 않는다**
  (진단 센서는 T10에서 별도).
- `available` = `coordinator.last_update_success and coordinator.data.<value> is not None`.
- 값이 `None`인 사이클에 엔티티를 `unknown`으로 만들지 않는다 — 직전 값을 유지한다(T4의 보존 정책).

**테스트.** 옵션 off일 때 엔티티가 생성되지 않는다. 좌표계 값이 엔티티 상태에 반영된다.

**완료 기준 `[HW]`.** 실물에서 온습도 값이 E-Ink 화면 표시와 ±0.2 °C / ±2 % 이내로 일치하고,
스캔 주기마다 갱신된다. 12시간 연속 동작에서 미갱신 구간이 없다.

---

## T6 — `button` 플랫폼 (시간 동기화)

**의존.** T4.

**변경.**

- `LywsdSyncTimeButton`, `translation_key="sync_time"`, 아이콘 `mdi:clock-check-outline`.
- `async_press`:
  ```python
  result = await async_execute(self.hass, self._entry,
      lambda c, d: d.set_time(c, dt_util.now(), tz_offset_hours))
  ```
  `tz_offset_hours`는 **HA 설정 타임존에서 계산**한다 — 하드코딩 금지:
  `int(dt_util.now().utcoffset().total_seconds() // 3600)`.
  DST 타임존에서는 계절에 따라 값이 바뀌며 그게 맞는 동작이다.
- 성공 시 `coordinator.data.last_sync` / `last_drift_seconds`를 갱신하고
  `async_set_updated_data`로 T10의 진단 센서에 반영.
- 예외 매핑은 niimbot `_reraise_action_error` 형태: `LywsdVerifyError` → "기기가 시간 쓰기를
  확인하지 못했습니다", 그 외 일반 메시지. 모두 `HomeAssistantError`.
- `available`: `async_ble_device_from_address(..., connectable=True) is not None`.

**서비스.** `services.yaml`에 `sync_time` — 필드 `timezone_offset`(optional, number, -12~14).
미지정 시 HA 타임존. `target: { entity: { integration: xiaomi_lywsd } }`.
`__init__.py`에서 등록하고 `async_unload_entry`에서 **마지막 entry일 때만** 제거
(gicisky의 `len(...) == 1` 검사와 동일).

**테스트.** `set_time` 호출 확인, 실패 시 `HomeAssistantError`, `ble_device` 없을 때 연결 시도 없음.

**완료 기준 `[HW]`.** 버튼 1회 클릭 → E-Ink 시계 시각이 실제 교정됨 (직결 + 프록시 각 1회 육안 확인).

---

## T7 — `select` 플랫폼 (표시 단위)

**의존.** T4. **T1-e가 성공했을 때만 진행.**

**변경.**

- `LywsdDisplayUnitsSelect(RestoreEntity, SelectEntity)` — gicisky `switch.py` 패턴.
- `options = ["celsius", "fahrenheit"]`, `entity_category = CONFIG`.
- 상태 소스는 §3.4대로: 폴링 사이클에서 값을 모를 때만 읽고, write 성공 시 낙관적 갱신,
  재시작 시 `RestoreEntity`로 복원. 복원값이 없으면 `None`(Unknown) — 틀린 값을 보여주는 것보다 낫다.
- `async_select_option` → `async_execute(... d.set_units(c, option))`. 실패 시 이전 값 유지 +
  `HomeAssistantError`.
- `xiaomi_lywsd.read_state` 서비스(신규)로 강제 재읽기.
- **번역 문구에 §3.5의 주의를 명시**: 이 설정은 E-Ink 화면 표시만 바꾸며 HA 온도 센서 값에는
  영향이 없다.

**완료 기준 `[HW]`.** 화면 단위가 실제로 바뀌고, HA 재시작 후 select가 마지막 값을 표시.

---

# Phase 2 — 편의 기능

## T8 — 자동 시간 동기화 옵션

**의존.** T6.

**변경.**

- `CONF_AUTO_SYNC_HOURS`, `DEFAULT_AUTO_SYNC_HOURS = 0` (비활성; 옵션 24 / 168).
  셀렉터는 `select`로 `0 / 24 / 168` (비활성 / 매일 / 매주). **24시간 미만 옵션을 제공하지 않는다.**
- `async_track_time_interval` 등록, 취소 콜백을 `entry.async_on_unload()`에 전달.
- 자동 경로 실패는 **`HomeAssistantError`를 올리지 않는다.** `_LOGGER.debug`만, 연속 3회 실패부터
  `warning` 1회 (로그 스팸 방지).
- HA 시작 직후 실행하지 않는다. 첫 실행은 등록 후 1주기 뒤.
- 폴링 사이클과 동시에 걸리면 §3.1의 전역 락이 자연히 직렬화한다. 별도 조정 불필요.

**테스트.** 인터벌 0이면 미등록. 언로드 시 취소. 자동 경로 예외가 밖으로 새지 않는다.

---

## T9 — 프록시 active connection 미설정 감지 → repair issue

**의존.** T3.

**변경.**

- `async_setup_entry` 말미에서 판정:
  ```python
  connectable = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
  any_scanner = bluetooth.async_scanner_count(hass, connectable=True)
  ```
  - `any_scanner == 0` → issue `no_connectable_scanner`.
  - `any_scanner > 0`인데 비연결 스캐너로만 광고가 보임 → issue `proxy_not_active`.
- `issue_registry.async_create_issue(..., is_fixable=False, severity=WARNING,
  translation_key=...)`. 설명 본문에 YAML 예시:
  ```yaml
  esp32_ble_tracker:
  bluetooth_proxy:
    active: true
  ```
- **entry setup을 실패시키지 않는다.** 이후 성공적 연결이 일어나면 `async_delete_issue`로 해제.

> 이 통합은 광고를 전혀 쓰지 않으므로, **active connection 없이는 기능이 100 % 무효다.**
> 초판보다 이 태스크의 중요도가 높아졌다 — Phase 2가 아니라 T5 직후에 넣어도 된다.

---

## T10 — 진단 센서

**의존.** T6.

**변경.**

- `sensor.last_sync` — `device_class: timestamp`, `DIAGNOSTIC`.
- `sensor.clock_drift` — 마지막 동기화 직전 관측 오차(초). `state_class: measurement`, `s`,
  `DIAGNOSTIC`, `entity_registry_enabled_default = False`.
- 둘 다 `coordinator.data`를 읽는 `CoordinatorEntity`. 자체 BLE 접근 없음.
- `CONF_CLIMATE_SENSORS`와 무관하게 **항상 생성**한다 (시계 제어 전용으로 쓰는 사용자에게도 필요).

---

## T11 — 테스트 하네스

**변경.**

1. `tests/conftest.py` — `../hass-niimbot/tests/conftest.py`를 복사한 뒤 **이 통합이 실제로
   임포트하는 모듈만 남긴다.** 필요한 것: `homeassistant`, `.components`,
   `.components.bluetooth`, `.components.{sensor,button,select}`, `.config_entries`, `.const`,
   `.core`, `.helpers.*`(`update_coordinator`, `entity`, `entity_platform`, `device_registry`,
   `event`, `restore_state`, `issue_registry`, `selector`), `.exceptions`, `.util.dt`,
   `bleak`, `bleak.backends.device`, `bleak_retry_connector`, `voluptuous`.
   `MockHomeAssistantError`를 **실제 예외 클래스**로 두는 부분(그래야 `pytest.raises`가 동작)을
   반드시 유지한다. `UpdateFailed`도 같은 방식으로 실제 예외 클래스여야 한다.
2. `tests/fake_client.py`:
   ```python
   class FakeBleakClient:
       """write 기록 + read 재생 + notify 재생."""
       def __init__(self, initial: dict[str, bytes],
                    notifications: dict[str, list[bytes]] | None = None,
                    reject: set[str] | None = None): ...
       writes: list[tuple[str, bytes, bool]]
       async def read_gatt_char(self, uuid) -> bytes: ...
       async def write_gatt_char(self, uuid, data, response=False) -> None: ...
       async def start_notify(self, uuid, cb) -> None:   # 등록된 시퀀스를 순차 콜백
       async def stop_notify(self, uuid) -> None: ...
       async def disconnect(self) -> None: ...
   ```
   - write는 기본적으로 저장소를 갱신 → read-back 검증이 자연히 통과.
   - `reject={uuid}`로 갱신을 막아 검증 실패 시나리오를 만든다.
   - `notifications`가 비면 `start_notify` 후 아무 콜백도 오지 않아 **타임아웃 경로**를 테스트할 수
     있다. 이 경로가 실제 운영에서 가장 흔한 실패이므로 반드시 커버한다.
3. `requirements-test.txt`: `pytest`.

**완료 기준.** HA 미설치 환경에서 `python -m pytest tests/ -v` 통과.

---

## T12 — CI

`../hass-niimbot/.github/workflows/`의 두 파일을 복사 후 수정:
- `tests.yml`: manifest에서 requirements를 뽑는 단계는 이 통합의 `requirements`가 비어 있으므로
  **제거**하고 `pip install -r requirements-test.txt`로 대체. 매트릭스 `["3.12","3.13","3.14"]` 유지.
- lint: `python -m ruff check custom_components/ tests/ tools/`.
- `validate.yml`은 그대로 (HACS action + hassfest action).

**추가.** `tests/test_translations.py` — niimbot에 같은 이름의 테스트가 있다. `strings.json`과
`translations/{en,ko}.json`의 키 집합이 **정확히 일치**하는지 재귀 비교해 §2의 "번역 세 파일 세트"
규칙을 CI가 강제하게 만든다.

---

## T13 — README와 문서

**반드시 담을 것.**

- **이 통합이 존재하는 이유를 §0.3 근거로 설명한다.** "코어 `xiaomi_ble`는 LYWSD02의 광고에
  온습도 payload가 없어 센서를 만들지 못한다. 이 통합은 GATT 연결로 직접 읽는다."
  이 한 문단이 저장소의 존재 이유이자 사용자가 가장 먼저 확인할 내용이다.
- **코어 `xiaomi_ble`가 정상 동작하는 개체라면** `CONF_CLIMATE_SENSORS`를 끄고 시계 제어만
  쓰라는 안내.
- ESPHome 프록시 `active: true` **필수** + YAML 예시. 광고를 안 쓰므로 이게 없으면 아무것도 안 된다.
- 스캔 주기와 배터리의 트레이드오프. 장기 데이터가 아직 없다는 점을 솔직히 적는다.
- 초기 릴리스는 **beta**. 실물 1대에서만 검증됐다.
- `.github/ISSUE_TEMPLATE/bug_report.yml`에 **펌웨어 버전 + device_id(0x045B / 0x16E4 / 0x2542) +
  광고 원문 hex** 필드를 필수로 넣는다. 광고 hex 한 줄이면 `tools/decode_mibeacon.py`로
  그 개체의 실패 모드를 즉시 판정할 수 있다. §7 "실물 1대 검증" 리스크의 유일한 실질 완화책이다.
- **bindkey 관련 안내를 쓰지 않는다.** 캡처에서 `is_encrypted=0`이 확인됐으므로 이 기기에서
  bindkey는 무관하다. 잘못 언급하면 사용자를 Telink Flasher 삽질로 보내게 된다.
- 지원 모델: LYWSD02 / LYWSD02MMC (순정 펌웨어). LYWSD03MMC는 미지원 — pvvx/ATC 커스텀 펌웨어
  생태계를 안내.
- 한국어 README 1급 (niimbot README 구성 참고).

---

## T14 — 이력 데이터 읽기 (Phase 3, 착수 전 재평가)

**지금 시작하지 않는다.** T1~T13이 끝나고 실사용 피드백이 생긴 뒤 판단한다.

착수 시 선행 조건:
- `docs/protocol.md` §6이 "미검증"이 아니라 실측으로 채워져 있을 것. 참조 포맷은
  `EBE0CCBC` notify의 `<IIhBhB` (index, timestamp, max temp, max hum, min temp, min hum).
- 이력 전송은 수백 레코드의 notify 스트림이라 연결이 수 분 유지된다. §2의 "사이클 단위 연결"과
  충돌하므로 **명시적 서비스 호출로만 트리거**하고 자동 실행 경로를 만들지 않는다. 이력 읽는
  동안 정기 폴링은 전역 락에 의해 자연히 대기한다.
- statistics import는 `recorder.statistics.async_add_external_statistics`를 쓴다. T5의 실시간
  센서 히스토리와 섞이지 않도록 `xiaomi_lywsd:` 접두 statistic_id를 쓴다.

---

## 6. 결정 로그

### 6.1 개정판에서 뒤집힌 결정 (실측 근거)

| 항목 | 초판 | 개정판 | 근거 |
| --- | --- | --- | --- |
| 온습도 센서 | 만들지 않음 (코어와 중복 회피) | **만든다. 1차 기능** | §0.3 — 광고 캡처에서 `object_include=0` 확인. 코어가 구조적으로 값을 못 준다 |
| 배터리 센서 | 만들지 않음 | 만든다 | 같은 이유. `EBE0CCC4` 1바이트 read로 사이클에 얹으면 비용 거의 0 |
| 코디네이터 | 폴링 없음 (요청 시에만 연결) | **`DataUpdateCoordinator` + `scan_interval`** | notify 수집에 주기적 연결이 불가피 |
| 코어와의 연결 경합 | 최상위 리스크 | **리스크 아님** | `parser.py:2428` — 코어는 `0x2542`를 폴링하지 않는다 |
| MVP 기준선 | button (시간 동기화) | **sensor (온습도)** | 사용자에게 가장 부족한 것이 값 자체 |
| 프록시 active 미설정 | Phase 2 편의 기능 | 사실상 필수 전제 | 광고를 전혀 쓰지 않으므로 없으면 전면 무효 |
| 단위 코드값 | `0x00`=°C / `0xFF`=°F 추정 | **`0xFF`=°C / `0x01`=°F** | h4/lywsd02 참조 구현 (T1-e에서 실측 확인) |
| 실패 원인 진단 | 로그 관찰로 추정 | **광고 hex 디코딩으로 확정** | `tools/decode_mibeacon.py` 작성 완료. 이슈 대응에도 재사용 |
| tz offset 부호 | `int8`? `uint8`? 미정 | **`int8` (`struct 'Ib'`)** | 같은 참조 구현 (T1-d에서 음수로 확인) |

### 6.2 초판에서 유지되는 결정

| 항목 | 결정 | 사유 |
| --- | --- | --- |
| `select` 현재값 | `RestoreEntity` + 낙관적 갱신 | 사이클당 연결 시간을 늘리지 않기 위해 |
| `manifest.bluetooth` | `local_name: LYWSD02*` + `connectable: true`, MiBeacon UUID 매처 없음 | 비연결 환경 오탐과 Xiaomi 전 기종 발견 스팸 방지 |
| 수동 MAC 입력 | `async_step_manual` 단계 | gicisky에 없는 경로이므로 사양 필요 |
| 자동 동기화 주기 | 24h / 7d, 그 미만 금지 | 배터리 |
| `requirements` | 빈 배열 | bleak / bleak-retry-connector는 코어 제공 |
| 도메인 | `xiaomi_lywsd` | LYWSD03MMC / LYWSDCGQ까지 확장 여지 |

---

## 7. 리스크

| 리스크 | 영향 | 완화 |
| --- | --- | --- |
| 주기적 BLE 연결이 배터리를 소모 | 사용자 불만, 잦은 건전지 교체 | 기본 30분(CR2032), 하한 120초, `climate_sensors=False`면 폴링 정지. 사이클당 1회 notify만 수신 후 즉시 해제. README에 트레이드오프 명시 |
| 프록시 `active: false` | 기능 **전면** 무효 (광고를 전혀 쓰지 않으므로) | T9의 repair issue + README 최상단 안내. 유지보수자 환경은 이미 active 확인됨(§0.3) |
| notify 첫 수신 지연이 기기마다 다름 | 폴링이 매번 타임아웃 | T1-c에서 실측해 timeout 결정. 기본 15초, 실패는 `UpdateFailed`로만 |
| 펌웨어 리비전별 페이로드 차이 | 잘못된 write로 표시 깨짐 | write 후 read-back 검증, 실패 시 롤백 (T2) |
| 코어가 동작하는 개체에서 센서 중복 | 엔티티 2벌 | `CONF_CLIMATE_SENSORS` 옵션 (기본 on) |
| 실물 1대로만 검증 | 일반화 오류 | beta 표기 + 이슈 템플릿에 펌웨어/device_id/**광고 원문 hex** 필수 필드 (`decode_mibeacon.py`로 즉시 판정) |
| 다른 개체는 sensor 프레임을 보낼 수도 | 불필요한 GATT 폴링 | `CONF_CLIMATE_SENSORS`로 끌 수 있음. 이슈의 광고 hex로 판정 후 안내 |
| Mi Home 앱이 연결을 점유 | 폴링 실패 | 재시도 + `close_stale_connections_by_address`. 해결 안 되면 README에 "앱을 닫으라" 안내 |

---

## 8. 최종 완료 기준

- [ ] HACS 커스텀 저장소로 설치 → HA 재시작 후 기기 자동 발견
- [ ] **온도/습도 센서가 실제 값을 보여주고 스캔 주기마다 갱신됨** (E-Ink 화면과 ±0.2 °C / ±2 % 이내)
- [ ] 12시간 연속 동작에서 값 미갱신 구간 없음
- [ ] 버튼 1회 클릭으로 E-Ink 시계 시각이 교정됨 (직결 + 프록시 각 1회 육안 확인)
- [ ] 기기가 범위 밖일 때 통합이 죽지 않고, 복귀 후 다음 주기에 자동 회복
- [ ] `_async_update_data`가 `UpdateFailed` 외 예외를 밖으로 내보내지 않음 (테스트로 보장)
- [ ] `hassfest` / HACS validation 통과
- [ ] `ruff check custom_components/ tests/ tools/` 통과
- [ ] `pytest tests/ -v` 통과 (HA 미설치 환경)
- [ ] `strings.json` / `en.json` / `ko.json` 키 집합 일치 (테스트가 강제)
- [ ] `docs/protocol.md`가 실측값으로 채워지고 추측이 구분 표기됨

---

## 9. 참고 자료

- HA 코어 `xiaomi_ble` 소스 — `../core/homeassistant/components/xiaomi_ble/`
- `xiaomi-ble` 1.11.0 파서 — `~/.cache/uv/archive-v0/us02QQqBq1IBytmd/xiaomi_ble/`
  (`devices.py`의 device_id 테이블, `parser.py:2150` payload 검사, `parser.py:2428` poll 정책)
- [h4/lywsd02](https://github.com/h4/lywsd02) — GATT UUID·페이로드 참조 구현 (Python)
- [lhvo/LYWSD02MMC](https://github.com/lhvo/LYWSD02MMC) — notify 활성화(CCCD `0100`) 절차
- [alive-corpse/LYWSD02-LYWSD03MMC-MQTT](https://github.com/alive-corpse/LYWSD02-LYWSD03MMC-MQTT) — 대안 구현
- [ESPHome `xiaomi_ble`](https://esphome.io/components/sensor/xiaomi_ble/) — 광고 기반 구현과의 대조군
- `tools/decode_mibeacon.py` — 이 저장소에 포함된 MiBeacon 헤더 디코더. 사용자가 이슈에 붙인
  광고 hex 한 줄로 그 개체의 실패 모드(payload 없음 / 암호화 / 정상)를 즉시 판정한다
- `bleak-retry-connector` — ESP32 프록시 환경 연결 안정화
