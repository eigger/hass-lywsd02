# 적용한 공통 규칙

- 표준: https://github.com/eigger/hass-repo-standards/tree/648dad941a118c80325f44c7a13cb5b5b9c1c788
- 참조 커밋 SHA: `648dad941a118c80325f44c7a13cb5b5b9c1c788`
- 검토일: 2026-10-20 (Asia/Seoul)
- profile: integration / ha
- 적용 점검표: [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md)
- 중앙 현황표: https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md
- 담당: 조율 root(lywsd02-adoption), 구현 implementation/tests/runtime 및 docs/README/CI, 독립 리뷰 review
- 중앙 현황 갱신일: 2026-10-20, 중앙 로컬 checkout의 해당 행만 수정; 원격 미반영
- 실제 기본 브랜치: `main`
- 검토 대상: `4adac9e3903efe58d8746bd5551ba7e36b1aadd8` + 작업 tree (commit/push/PR 미실행)
- 테스트 경로: `tests/components/xiaomi_lywsd/`
- 변경 전·후 지원 최소 HA: `2025.1.0` (`hacs.json`); 지원 최소 상향 없음
- CI 이벤트 변경 승인: 사용자 2026-10-20 본 채팅에서 “중앙 템플릿대로 main / 주 1회로 변경 승인”. 기존 main/master·daily에서 main·월요일 03:23 UTC(한국 12:23)로 변경. 승인된 템플릿 적용이므로 CI-02 예외 없음
- current 테스트 환경: HA 2026.10.2 / Python 3.14.5 / pytest-homeassistant-custom-component 0.13.373; 실제 테스트 결과는 체크리스트에 기록
- 최소 HA 검증 환경: HA 2025.1.0 / Python 3.13.14 / pytest-homeassistant-custom-component 0.13.201; 실제 테스트 결과는 체크리스트에 기록
- 최소 package 검증: manifest `requirements: []`; imagespec/blesession 미사용으로 해당 없음
- imagespec DOC-08 및 updater: 해당 없음. 런타임 외부 패키지 선언이 없어 manifest updater를 추가하지 않음
- HACS Default: 2026-10-20 공식 [integration 목록](https://github.com/hacs/default/blob/master/integration)의 `eigger/hass-lywsd02` 등재 확인. Default/Downloads와 설치 배지 반영
- 분류: 실제 LYWSD02/LYWSD02MMC 온습도계 제품에 `sensors.temperature_humidity` 선택. taxonomy 및 독립 검토는 체크리스트 참조
- Hassfest: categories 지원을 포함한 공식 Core full SHA `ec18d8b25d1ee39aa8b85a72a170e42bee33228c`를 공용 validator 입력으로 사용. published stable 이미지의 스키마 지연 대응이며 HA 지원 최소는 그대로 유지. 실제 실행 결과는 체크리스트 참조

## 예외

승인된 예외 없음. 미검증·미충족 항목은 `ADOPTION_CHECKLIST.md`의 TODO로 관리하며 채택 완료로 표시하지 않습니다.

## 동작 호환 수정

실제 최소 HA 테스트에서 `OptionsFlowWithReload` import가 실패했습니다. 최소 HA를 유지하기 위해 `OptionsFlow`와 config entry update listener로 변경하고, 실제 HA options flow를 통한 reload를 검증합니다. domain·unique ID·entry schema·버전·기기 프로토콜은 유지합니다.

## 최종 검증과 남은 범위

독립 current/minimum 실제 HA 테스트 각각146 passed, pip check·Ruff0.17.1·actionlint1.7.12·중앙검사·최종 Hassfest 통과. setup forwarding 실패와 취소 시 auto-sync timer 정리도 양환경 검증했습니다. 기존 manual 연결확인·BLE proxy/service-change·오류 번역키·MAC 로그 마스킹/중복warning 억제, 게시 후 HACS/원격CI·중앙원격 반영은 체크리스트 TODO입니다. 공용화와 Default 반영 완료를 전체 표준 채택 완료로 표현하지 않습니다.
