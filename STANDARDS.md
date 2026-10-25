# 적용한 공통 규칙
- 표준: https://github.com/eigger/hass-repo-standards/tree/v1.0.0
- 참조 커밋 SHA: 44349ee5621eea5d80e5c427f7a2435d2c2491bb
- Standards release: v1.0.0
- Resolved standards SHA: 44349ee5621eea5d80e5c427f7a2435d2c2491bb
- 검토일: 2026-10-20 (Asia/Seoul)
- profile: integration / ha
- 적용 점검표: [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md)
- 중앙 현황표: https://github.com/eigger/hass-repo-standards/blob/main/docs/adoption-status.md
- 담당: 조율 root(lywsd02-adoption), 구현 implementation/tests/runtime 및 docs/README/CI, 독립 리뷰 review
- 중앙 현황 갱신일: 2026-10-20, 중앙 로컬 checkout의 해당 행만 수정; 원격 미반영
- 실제 기본 브랜치: `main`
- 검토 대상: 최초 로컬 검증 baseline `4adac9e3903efe58d8746bd5551ba7e36b1aadd8`; 구현 `1dcdbf75f5857066b7488146d1c2a6dcd76b9e48` ([PR #10](https://github.com/eigger/hass-lywsd02/pull/10))
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

독립 current/minimum 실제 HA 테스트 각각146 passed, pip check·Ruff0.17.1·actionlint1.7.12·중앙검사·최종 Hassfest 통과. setup forwarding 실패와 취소 시 auto-sync timer 정리도 양환경 검증했습니다. 기존 manual 연결확인·BLE proxy/service-change·오류 번역키·MAC 로그 마스킹/중복warning 억제, PR #10의 [Tests](https://github.com/eigger/hass-lywsd02/actions/runs/39426665033)·[Validate](https://github.com/eigger/hass-lywsd02/actions/runs/39426664954)가 구현 커밋에서 모두 통과했습니다. 중앙원격 반영은 아직 미실행입니다. 공용화와 Default 반영 완료를 전체 표준 채택 완료로 표현하지 않습니다.

## 2026-10-23 다운로드 배지 부분 갱신

- 배지·DOC-03/05와 Validate 형식 검사기만 중앙 [`b54ac48102d6e326c6929071fdc02ba8fade794e`](https://github.com/eigger/hass-repo-standards/tree/b54ac48102d6e326c6929071fdc02ba8fade794e)를 채택합니다. 이전 기준 SHA `648dad941a118c80325f44c7a13cb5b5b9c1c788`의 채택 이력·예외는 보존합니다. 모든 중앙 workflow/action pin과 standards-ref는 GOV-02의 단일 기준 SHA 계약에 맞춰 갱신합니다. 중앙 diff에서 공용 workflow/action 실행 파일은 이전 기준과 동일함을 확인했습니다.
- 대상 기본 브랜치 커밋: `3bfa1d69c1d09df54f02cd7b507d3fad34bc0619`. 주 에이전트 직접 구현·자체 리뷰(GOV-05의 배지/생성물 변경 범위), 검증은 [ADOPTION_CHECKLIST.md](ADOPTION_CHECKLIST.md#2026-10-23-downloads-배지-부분-검증)에 기록합니다.
- Downloads는 모든 릴리스 첨부 asset 다운로드 합계입니다. 사용자 지시에 따라 ZIP 배포를 도입하지 않으며 현재 HACS 소스 파일 설치는 이 수치에 집계되지 않습니다. 통합 코드·의존성·지원 최소·기존 설치 안내는 변경하지 않습니다.

## 2026-10-23 ZIP 릴리스 배포

- 기준 중앙 SHA: `0c1592977591ecba077a4666d699840062711201` ([중앙 PR15](https://github.com/eigger/hass-repo-standards/pull/15) 스쿼시 머지). 이전 `b54ac48102d6e326c6929071fdc02ba8fade794e` 채택 이력·예외를 보존하며 HACS-04·CI-11의 ZIP 배포 계약을 추가합니다.
- 대상 시작 SHA: `7cabc151c0025579bee80856ed7d41608e3d88eb`. hacs.json의 zip_release/filename과 중앙 release caller를 함께 적용합니다. archive 파일명은 `xiaomi_lywsd.zip`, ZIP 루트는 해당 통합 파일입니다.
- 중앙 workflow/action pin과 standards-ref는 단일 SHA로 정합화합니다. release:published에서 기존 해당 릴리스에 ZIP만 첨부하며 소스 버전·태그·릴리스 발행은 자동 변경하지 않습니다. 기존 asset 덮어쓰기를 거부합니다.
- 기존 지원 최소 HA `2025.1.0`와 통합 버전 `0.3.2` 및 의존성·구현은 보존합니다. 기존 태그의 hacs.json은 소급 수정하지 않으므로 다음 릴리스부터 ZIP 설치로 전환됩니다.
- immutable-releases 설정은 enabled=false/enforced_by_owner=false로 확인했습니다. 업로드 지연·실패 및 기존 asset 복구는 중앙 [릴리스 계약](https://github.com/eigger/hass-repo-standards/blob/0c1592977591ecba077a4666d699840062711201/docs/releases.md#zip-릴리스-첨부)을 따릅니다. 실제 새 릴리스 발행·설치·기기 검증은 이번 작업에 포함하지 않습니다.

## 2026-10-25 중앙 검사기 갱신

- 검토한 중앙 main: `1863343638014adb8a4001afc8fddc1a27dc500f` (git ls-remote 확인). 이전 기본 기준 `0c1592977591ecba077a4666d699840062711201`의 채택 이력은 위 기록을 보존합니다.
- 모든 중앙 workflow/action pin과 reusable workflow의 standards-ref를 같은 검토 SHA로 맞춥니다. HACS-04는 actions/*의 full SHA 고정을 유지하면서 SHA 값 차이를 허용합니다.
- 통합 코드·런타임 의존성·지원 최소·배포 버전은 이번 변경 대상이 아닙니다. 기존 채택 범위를 전체 완료로 바꾸지 않으며 실제 검증 결과와 남은 항목은 ADOPTION_CHECKLIST.md의 같은 날짜 기록을 참조합니다.


### 2026-10-25 Standards 파일·표시 이름 분리

- 기존 Validate의 중앙 검사 job을 `standards.yml`로 옮기고 workflow/job 표시 이름을 `Standards`로 줄였습니다. Validate의 HACS/Hassfest, 검사 항목·통과 기준·실행 단계·조건·권한은 유지합니다.
- 위치 인식과 중앙 명명 안내를 맞춘 검토 소스: `ca740d88b32fa5dcbc94c41fce2908450c76ed50` ([중앙 PR #24](https://github.com/eigger/hass-repo-standards/pull/24), 현재 이 PR의 의존 변경). 이전 기준 `1863343638014adb8a4001afc8fddc1a27dc500f`의 검증 이력은 앞 기록으로 보존합니다. 모든 중앙 pin·standards-ref는 같은 새 검토 소스로 맞춥니다.
