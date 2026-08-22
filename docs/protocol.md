# LYWSD02(MMC) GATT 프로토콜

> **상태: 미검증 (커뮤니티 가설).** 이 문서는 실물 실측(T1) 전에
> [h4/lywsd02](https://github.com/h4/lywsd02) 등 커뮤니티 리버스 엔지니어링을
> 정리한 작업용 초안이다. `tools/dump_gatt.py` / `probe_time.py` /
> `probe_units.py`로 실측한 뒤 이 문서를 덮어쓰고, 아래 "미검증" 표기를
> 제거한다. **추측과 확정값을 섞지 않는다.**

코드(`device/lywsd02mmc.py`)는 이 문서의 **작업용 가정**만 사용한다. 실측이
어긋나면 코드와 이 문서를 같은 변경에서 함께 고친다.

---

## 0. 측정 환경

| 항목 | 값 |
| --- | --- |
| 펌웨어 | **미측정** — `tools/dump_gatt.py` 또는 Mi Home에서 확인 후 기입 |
| 어댑터 | 미측정 |
| 측정일 | 미실시 |
| 기기 대수 | 0 (문서 작성 시점) |
| 근거 소스 | h4/lywsd02 `client.py` (커뮤니티) |

**이 문서는 펌웨어 미확인 상태에서 커뮤니티 가설로만 채워져 있다.**

---

## 1. 서비스/characteristic 전체 트리

`tools/dump_gatt.py <MAC>` 실행 결과를 아래에 그대로 붙인다.

```
(미실시 — dump 원문 대기)
```

알려진 커스텀 서비스 (커뮤니티):

- Service `ebe0ccb0-7a0a-4b0c-8a1a-6ff2997da3a6`

| UUID | 역할 (가설) | 속성 |
| --- | --- | --- |
| `ebe0ccb7-…` | Time | read, write |
| `ebe0ccbe-…` | Units | read, write |
| `ebe0ccc4-…` | Battery % | read |
| `ebe0ccc1-…` | Temp/Humidity notify | read, notify |
| `ebe0ccb9-…` | History count | read |
| `ebe0ccba-…` | History index | read, write |
| `ebe0ccbc-…` | History records | read, notify |

---

## 2. 온습도 notify

| 항목 | 값 | 상태 |
| --- | --- | --- |
| UUID | `ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6` | 커뮤니티 |
| 페이로드 | `<hB` — int16 LE °C×100 + uint8 습도 | 커뮤니티 |
| 수집 방식 | notify 1건 (plain read는 기기별 상이 — probe로 확인) | 미검증 |
| 타임아웃 기본 | 15초 | 작업용 |

`tools/probe_climate.py`로 첫 notify 지연·plain read 가능 여부를 실측한다.

---

## 3. 시간

| 항목 | 값 | 상태 |
| --- | --- | --- |
| UUID | `ebe0ccb7-7a0a-4b0c-8a1a-6ff2997da3a6` | 커뮤니티 |
| 페이로드 | `<Ib` — uint32 LE Unix epoch + **int8** tz offset (hours) | 미검증 |
| epoch 의미 | **UTC epoch** 가정 (h4/lywsd02). 로컬 epoch를 쓰는 펌웨어면 `drift_seconds`가 tz만큼 어긋남 → T1에서 확인 | 미검증 |
| 4바이트 only read | tz=0으로 취급 | 커뮤니티 |
| `response=` | `True` (withResponse) | 미검증 — False도 probe에서 확인 |
| read-back 허용오차 | ±2초 | 계획서 기준 |

음수 tz(예: -5) 왕복으로 int8 vs uint8을 판정해야 한다. 한국(+9)만 테스트하면
부호 문제를 놓친다. → `python tools/probe_time.py <MAC> -5`

---

## 4. 표시 단위

| 항목 | 값 | 상태 |
| --- | --- | --- |
| UUID | `ebe0ccbe-7a0a-4b0c-8a1a-6ff2997da3a6` | 커뮤니티 |
| °C 코드 (작업용) | `0xFF` | **미검증** — h4/lywsd02 `UNITS` dict |
| °F 코드 (작업용) | `0x01` | **미검증** — h4/lywsd02 `UNITS` dict |
| 화면 반영 지연 | 미측정 | |

**작업용 가정 (코드에 반영):** `0xFF` → celsius, `0x01` → fahrenheit.
실측에서 반대면 이 절과 `device/lywsd02mmc.py`를 함께 수정한다.
알 수 없는 바이트(예: `0x00`)는 추측 매핑하지 않고 `LywsdDeviceError`로 올린다.

절차: `python tools/probe_units.py <MAC>` → 화면 육안 → 원복 확인.

---

## 5. 배터리

| 항목 | 값 | 상태 |
| --- | --- | --- |
| UUID | `ebe0ccc4-7a0a-4b0c-8a1a-6ff2997da3a6` | 커뮤니티 |
| 스케일 | 1바이트 percent (0–100) | 미검증 |

폴링 사이클에서 GATT read로 수집한다. 광고 기반 코어 배터리는 이 기기에서
기대할 수 없다(§0.3).

---

## 6. 이력 (Phase 3)

미검증. Phase 3 착수 전까지 구현하지 않는다.

---

## 7. 미해결 / 재현 안 된 항목

- [ ] GATT 트리 실측 dump
- [ ] 펌웨어 버전 기록
- [ ] 온습도 첫 notify 지연 / plain read 가능 여부
- [ ] 시간 write `response=True/False` 실측
- [ ] tz int8 부호 실측 (음수 오프셋)
- [ ] 단위 코드 °C/°F 화면 육안 확정
- [ ] ESPHome 프록시(`active: true`) 경유 write/notify 성공/실패
- [ ] MMC vs 비-MMC 펌웨어 편차
