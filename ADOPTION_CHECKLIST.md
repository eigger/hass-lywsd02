# 공통 규칙 적용 체크리스트

중앙 템플릿을 사용한 최초 채택 기록입니다. 아래 PASS는 실제 실행 근거가 확보된 항목에만 기록하며 미검증 항목은 TODO로 남깁니다. [사용법과 판정 기준](https://github.com/eigger/hass-repo-standards/blob/648dad941a118c80325f44c7a13cb5b5b9c1c788/docs/checklist.md)을 읽고, 아래 규칙은 `STANDARDS.md`에 기록한 표준 커밋에서 확인합니다. 태그·릴리스 대신 `main`의 검토 커밋을 기준으로 하며, 위 사용법 링크의 `main`은 채택 시 검토한 커밋 SHA로 바꿉니다.

## 검토 대상

| 항목 | 값 |
|---|---|
| 통합 리포 / 실제 기본 브랜치 | eigger/hass-lywsd02 / main |
| domain / 구현 경로 | xiaomi_lywsd / custom_components/xiaomi_lywsd/ |
| 검토 대상 통합 커밋 / 채택 PR | 구현1dcdbf75f5857066b7488146d1c2a6dcd76b9e48 / [PR #10](https://github.com/eigger/hass-lywsd02/pull/10) |
| 검토한 표준 전체 커밋 SHA | 648dad941a118c80325f44c7a13cb5b5b9c1c788 |
| 검토일 / 조율 담당 | 2026-10-20 (Asia/Seoul) / root(lywsd02-adoption) |
| 구현 서브 에이전트 / 독립 리뷰·검증 서브 에이전트 | implementation·docs / review |
| 중앙 현황표 반영일 / 기록 | 2026-10-20 중앙 로컬 checkout 자기 행 갱신; 원격 미반영 |
| 변경 전 지원 최소 HA / 근거 파일(hacs.json·manifest·README) | hacs.json homeassistant=2025.1.0; manifest/기존 README 별도 최소 선언 없음 |
| 유지·변경할 지원 최소 / 변경 시 실제 비호환 근거·명시적 승인 | 2025.1.0 유지 |
| current 테스트 HA / 호환 Python·플러그인 | 2026.10.2 / 3.14 / 0.13.373; 실제 결과 아래 기록 |
| 최소 테스트 HA / 호환 Python·플러그인 | 2025.1.0 / 3.13 / 0.13.201; 실제 결과 아래 기록 |
| profile / 테스트 경로 | integration / ha; tests/components/xiaomi_lywsd/ |
| 이전 검토 기록 | 공통 규칙 최초 채택 |
| 채택 판정 | 이관 진행 중; 원격 CI·기본 브랜치 반영 전 |

상태: `TODO` = 미확인·미충족, `PASS` = 근거로 확인, `EXCEPTION` = 적용 대상의 기록된 예외, `N/A` = 적용 조건에 해당 없음. 모든 항목은 미확인으로 시작합니다. `TODO`를 해당 없음으로 처리하지 않습니다. 묶은 규칙의 결과가 다르면 행을 나눕니다. 권장 항목은 별도로 표시했으며 미채택 이유를 기록합니다.

## 채택·구조·사용자 데이터

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| GOV-01, GOV-02 | `STANDARDS.md`에 표준 SHA·profile·실제 기본 브랜치·예외 기록, workflow/action은 검토 SHA로 고정 | PASS | STANDARDS.md에 검토 원격 main full SHA·profile·작업 tree 기록; caller는 동일 SHA로 고정 |
| GOV-03 | 새 표준 채택 변경의 영향·이관 방법과 명시적 채택 PR 확인. 규칙 자체를 변경하면 공통 CHANGELOG 기록 | PASS | 명시적 채택 [PR #10](https://github.com/eigger/hass-lywsd02/pull/10); 변경 영향·지원범위 및 사용자 승인 기록 확인 |
| GOV-04 | 중앙 표에 작업 시작·단계 변경·종료 상태, 담당·적용 내용·검증/리뷰 근거·남은 작업 갱신, 타 리포 기록 보존 | TODO | 중앙 로컬 checkout 해당 행 시작·구현·최종 검증 상태 갱신 완료. 다른 세션 행 보존; 원격 반영은 아직 미실행 |
| GOV-05 | 구현과 독립 리뷰·검증을 별도 서브 에이전트에게 위임, 지적 수정·재검증 및 결과 취합 | PASS | 구현 implementation/docs 및 독립 review. 최소 options import·setup 실패/취소 누수·실제 service/options 회귀·문서포맷 지적 수정 후 전체 양HA146 PASS 독립 재실행 |
| HA-01, HA-13 | `custom_components/<domain>/`와 domain 일치, 필요한 모듈·공개 API·생명주기는 Core 대응 구조 | PASS | custom_components/xiaomi_lywsd에 config flow/coordinator/플랫폼/typed entry·device 프로토콜 경계 유지. 실제 HA entry 로딩 검증 |
| HA-02 | manifest 필드·정렬·동작 선언, 실제 제품 categories 1–3개·주 분류 순서·공식 slug·선택 근거·categories_review 일치 또는 entity/system/virtual 키 생략 이유, 공식 품질 등급 자가 표기 없음 | PASS | manifest domain/name 이후 키 정렬, device/local_polling·온습도계 제품 분류 확인; config categories_review 일치; 실제 Hassfest 1 integration/0 invalid |
| HA-03 (권장) | 공통 상수·설정·갱신·플랫폼 역할 및 프로토콜 경계에 맞게 모듈 구성 | PASS | const/config_flow/coordinator 및 device/ 프로토콜 경계 기존 구조 유지; 불필요한 빈 모듈 없음 |
| HA-04, HA-08 | UI 설정·중복·안정적 식별 및 기능별 options/reauth/reconfigure, entity 의미·registry 영향 확인 | TODO | UI manual/Bluetooth/중복/options/migration·안정 unique ID·단위 검증. 기존 manual flow는 MAC 저장만 하고 실제 BLE 연결 확인이 없어 HA-04 전체 충족은 후속. 인증/reauth는 기능 없음 |
| HA-01, HA-04, HA-08, REL-01, REL-03 | domain·unique ID·entry schema·상태/통계 계약 변경 시 migration 테스트와 사용자 조치 안내 | PASS | domain·unique ID·entry schema/버전·센서 단위 변경 없음. 기존 v1 migration 테스트 보존 |
| HA-05, HA-06 | setup 실패 구분, unload/reload·부분 실패의 task/listener/연결 정리, async·timeout·취소 처리 | PASS | OptionsFlow+listener로 최소호환 reload 수정. forwarding 실패/CancelledError 시 auto-sync idempotent cleanup 후 재raise. 실제 setup/unload/options/service·실패/취소 회귀 양HA 통과. BLE op/실물 상세 미검증은 HA-09 TODO로 구분 |
| HA-07 | 중복 polling·property I/O 방지, push 보존, unavailable/unknown·실패 후 복구 | PASS | coordinator 단일 climate poll·순수 state property. 실제 loaded HA unavailable→BLE 복구 테스트; 기존값 보존 회귀 유지 |
| HA-11, HA-12 | 번역·action/schema 일치, 로그/diagnostics/fixture 비식별화와 제공 시 redaction 테스트 | TODO | 번역 key parity·services.yaml/Hassfest는 PASS. 기존 button/select/service 하드코딩 예외는 translation key 전환 필요. runtime warning 전체MAC/오류문자열 및 매 retry warning은 마스킹/중복억제 후속; diagnostics 미제공·토큰인증 없음 |

## 실제 HA 테스트·호환성·의존성

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| TEST-08 | `tests/components/<domain>/`에 구현과 대응하는 테스트·domain fixture 배치, discovery·CI 경로 일치 | PASS | 기존 회귀를 tests/components/xiaomi_lywsd/로 이동; pytest.ini 및 caller domain 경로 일치 |
| TEST-02, TEST-03, DEP-07 | 실제 HA·호환 플러그인과 `hass`/`enable_custom_integrations` fixture 사용, HA core stub/복사본/`--no-deps`로 대체하지 않음 | PASS | 루트 conftest 중앙 원본 및 실제 HA 플러그인 사용, sys.modules core stub 삭제; current/minimum 별도 환경 설치 |
| TEST-09 | 실제 loader·config entry manager로 setup/플랫폼 로딩, HA 상태·registry·service/action으로 결과 검증 | PASS | test_init.py에서 실제 config manager setup·4개 플랫폼/registry/상태/unload; options reload 및 등록 서비스 device target 경로 실행 |
| TEST-01, TEST-06, TEST-07 | 구현 기능별 성공·실패·중복·migration·unload·복구 회귀 검증, 외부 통신 경계만 mock, skip 사유 | PASS | 기존 regression 보존, 가짜 HA 모듈 제거. 실제 flow/setup/platform/service/action/options/unload/실패복구/취소 검증. 양HA 각각146 PASS, skip 없음. 순수 protocol 단위와 내부계산 회귀는 보조로 유지 |
| TEST-04, HACS-01 | 변경 전 지원 최소·current·각 Python/플러그인 분리, 선언한 정확한 최소 검증, 상향 시 비호환 근거·명시적 승인 확인 | PASS | hacs.json 2025.1.0 유지. 정확한 current2026.10.2와 minimum2025.1.0을 별도 Python/플러그인 환경으로 검증 |
| TEST-05, HA-10, DEP-02, DEP-05 | imagespec·blesession 등 최소/현재 라이브러리 별도 환경, 실제 HA 테스트·정확한 설치값·API 경계 검증 | N/A | manifest requirements=[]; imagespec/blesession 직접 import 없음. Bleak/connector는 HA bluetooth component 환경에서 설치 |
| DEP-01, DEP-06 | Python runtime은 manifest requirements, HA domain은 dependencies/after_dependencies, 테스트·린트 requirements는 별도 | PASS | 런타임 requirements=[] 유지. 테스트 current/minimum와 Ruff 전용 requirements 분리; HA component requirements는 공용 environment에서 설치 |
| DEP-07, CI-06 | 실제 사용하는 HA 구성요소의 requirements·필수 재귀 의존성·선택 로딩 경로 설치, resolver·`pip check` 통과 | PASS | 각 HA 실제 component manifest에서 bluetooth usb requirements 재귀 설치; 독립 두 환경 pip check 정상 |
| DEP-02, DEP-03, DEP-08 | 의존성 추가/변경의 버전·extras·marker·선언 위치·지원 플랫폼·라이선스 검토, 실제 HA 테스트와 문서 갱신 | PASS | runtime 외부 requirement 추가 없음. 테스트 전용 HA/plugin exact pin current·minimum 분리, 실제 resolver 및 pip check 정상. 최소 환경 dependabot 제외 |

독립 리뷰는 변경 전후 지원 최소와 current를 비교하고, 봇 PR이 과거 최소 requirements·constraints까지 갱신하거나 expected-ha-version·Python을 누락하지 않았는지 확인합니다. 최신 테스트 실패는 호환 수정 대상으로 처리합니다.

환경마다 아래 행을 복사합니다. 최소 HA와 최소 라이브러리 검증을 혼동하지 않고, marker가 활성인 환경에서 대상 패키지 설치값을 확인합니다. 실행하지 않은 조합은 `TODO` 또는 근거가 있는 `EXCEPTION`으로 남깁니다.

| 검증 축 / 상태 | 통합 커밋 | Python / HA / 플러그인 실제 버전 | 대상 패키지 실제 버전·extras·marker | 명령·테스트 결과·pip check / CI run·job | skip·제외·미검증 범위 |
|---|---|---|---|---|---|
| 현재 환경 / PASS | baseline4adac9e + 최종 작업 tree | 3.14.5 / 2026.10.2 / 0.13.373 | bleak3.0.2 / connector4.7.1 (HA component requirements) | 독립 pytest146 passed(1.98s)·uv pip check PASS | skip 없음; 실물 BLE 미검증 |
| 정확한 최소 HA / PASS | baseline4adac9e + 최종 작업 tree | 3.13.14 / 2025.1.0 / 0.13.201 | bleak0.22.3 / connector3.6.0 (HA component requirements) | 독립 pytest146 passed(2.39s)·uv pip check PASS | skip 없음; 실물 BLE 미검증 |
| 정확한 최소 라이브러리 / N/A | 작업 tree | 해당 없음 | manifest requirements=[] | updater/최소 라이브러리 matrix 생성 대상 아님 | 없음 |

## HACS·CI·의존성 업데이트

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| HACS-01, HACS-02 | 루트 README/LICENSE/hacs.json, 검증한 최소 HA, 실제 배포 구조와 필요한 옵션 일치 | PASS | 루트 README/LICENSE/hacs.json 유지, custom_components/xiaomi_lywsd 배포; 최소2025.1.0 보존 |
| HACS-03, HACS-05 | Default 여부는 목록 근거로 확인, [로컬 brand/icon.png 또는 원격 brands 근거](https://github.com/eigger/hass-repo-standards/blob/648dad941a118c80325f44c7a13cb5b5b9c1c788/docs/hacs.md)와 HACS/Hassfest 실제 실행, ignore는 이유·해제 조건 기록 | PASS | 공식목록 등재·기존 brand/icon.png 공식원본 일치. 구현1dcdbf75 [Validate](https://github.com/eigger/hass-lywsd02/actions/runs/39426664954): HACS·공식Core ec18d8 Hassfest 모두 PASS, ignore 없음 |
| HACS-06 (권장) | description·topics·issue 경로·brands 및 사용하는 HACS 필드 지원 확인 | PASS | 원격 issues/discussions 활성 확인. 로컬 brands icon 256x256·고해상도512x512 기존 파일 보존; 공식 core_brands/xiaomi 출처 |
| CI-01, CI-02 | Validate/Tests 공통화, 확장 job 유지, 공용 파일명·표시 이름·PR 대상 제한 없는 기본 이벤트·실제 기본 브랜치 push·dispatch·기존 schedule, 전용 CI 명명 형식 | PASS | 공용 Validate/Tests 및 정확한 중앙SHA 사용. 사용자2026-10-20 승인으로 main/master·daily를 중앙main·weekly로 변경. updater는 외부 requirements 없어 N/A |
| CI-03, CI-05, CI-08 | 최소 권한·checkout 자격증명 비보존·timeout·concurrency, full SHA·갱신 관리, 비신뢰 입력·secrets 경계 | PASS | contents:read, checkout persist-credentials:false, 공용timeout/concurrency·Actions full SHA·dependabot 설정; actionlint 독립PASS |
| CI-04, CI-07, CI-12 | 실패를 숨기지 않는 실제 `ha` 필수 테스트, 버전별 환경·cache·Ruff 설정과 required checks 이름 확인 | PASS | 구현1dcdbf75 [Tests](https://github.com/eigger/hass-lywsd02/actions/runs/39426665033): current/minimum HA 각146 PASS 및 양lint PASS. 브랜치 보호 API404(비보호) 확인, required checks 강제설정 없음·설정변경 미실행 |
| DEP-03, DEP-04, CI-09 | updater의 선택 package·연산자/extras/marker 보존, 안정 버전·major 정책, 실제 기본 브랜치·단일 bot branch·PR만 제안 | N/A | manifest에 updater 대상 외부 Python 패키지 없음; updater workflow를 만들지 않음 |
| CI-09, CI-10, DEP-08 | 변경 tree의 새 하한·실제 HA 검증 후 PR 동기화, 실패 시 중단·변경 없음 시 기존 PR 정리, 후속 required checks 충족 방식 확인 | N/A | manifest updater 없음; 테스트 의존성 Dependabot 갱신은 별도 |

## README·Bluetooth·유지보수

| 규칙 ID | 확인 항목 | 상태 | 근거 / 남은 작업 |
|---|---|---|---|
| DOC-01, DOC-02, DOC-06 | 중앙 header/support/related-projects/license 관리 영역의 정확한 형식, 기존 공통 내용·고지 보존, 영역 밖 순서·제목·본문 유지, 양언어 같은 구조·내용·상호 링크, 독립 번역 의미·누락 리뷰, 실제 활성 지원 링크·실제 라이선스 | PASS | 중앙 관리 README header/support/related/license·양언어 본문 보존. 독립 review 번역 의미/기능/예제 누락 없음; 실제 MIT License |
| DOC-03, DOC-04, DOC-05 | 언어 링크 다음 중첩 배지 관리 블록, flat·Release/HACS/HA minimum/Tests/Validate/License/HACS Downloads(Default) 또는 Usage(Custom) 순서·실제 조건·고유 배지 보존, 실제 기본 브랜치·상태별 필수 동적 집계 배지·양언어 설치 절의 실제 저장소 My HACS 배지·미집계와 0 설치 구분 | PASS | 공식목록 근거 Default/HACS Downloads 및 양언어 My HACS, 중앙배지 렌더러 사용. 독립 actionlint·배지검사PASS |
| HA-09, HA-10 | BLE 사용 시 HA Bluetooth API·라이브러리 공개 경계, 지원한 proxy 경로·재연결·취소·서비스 변경 검증 | TODO | HA Bluetooth/connector 공개API·disconnect/retry 회귀 확인. 실물 proxy 경로·service change·BLE op 취소 검증 미실행. 기존 MAC unique_id 사용은 바꾸지 않음. imagespec/blesession 미사용 |
| DOC-07 | blesession 사용 여부(manifest requirement extras·operator·marker/실제 import) 확인. 사용 통합은 중앙 양언어 docs/troubleshooting 템플릿의 고정 제목·순서·증상 표·실제 진단/로그·기존 Issues 연결, README와 로컬 문서의 언어별 상호/공통 blesession 원본 링크·placeholder 제거·공용 Validate 검사. 기존 본문/기기안내 보존, 새 제보 양식 금지. 프록시만 지원하면 기존 기기 조건·사용자 안내를 수동 확인 | PASS | blesession requirement/import 없음. 프록시 사용자 가이드 양언어 연결 및 기존 active:true YAML/기기 준비 조건 보존. DOC-07 고정 troubleshooting 템플릿은 blesession 미사용으로 N/A |
| DOC-08 | imagespec 사용 여부·양언어 docs/payload 여섯 절·언어별 README/공통 원본/상호 링크·실제 액션/대상/전체 YAML·기기 출력/지원/제한·기존 예제/본문 보존·기존 지원 연결, 모든 로컬 연결 예제의 payload.examples 등록·실제 경로/payload_format(list 또는 yaml)/크기/모델 색상 | N/A | manifest requirements=[] 및 실제 소스에 imagespec import 없음; 이미지 payload/action 기능 없음 |
| DOC-08, TEST-02, TEST-05, TEST-09 | 정확한 중앙 test_payload_examples scaffold·실제 HA entry/등록 action schema·production 준비 context/함수·기기 전송 없는 installed imagespec.validate/render 비교·각 예제 크기/색상, current/정확한 하한 실제 버전·pip check·명령/CI 결과, exact pin 재사용 근거·독립 adapter 리뷰 | N/A | imagespec 미사용; payload scaffold/adapter를 생성하지 않음 |
| DOC-08, CI-05, CI-07, DEP-08 | 공용 Tests/updater의 standards-ref와 reusable full SHA 일치·caller checkout 보존·도구 별도 checkout·resolver 후 패키지 변경 없음·지원 최소 보존·미실행/skip/xfail/deselect를 PASS로 처리하지 않음 | N/A | imagespec 미사용. 일반 Tests의 standards-ref는 reusable SHA와 일치 |
| DOC-07, HA-12 | 기기별 깨우기·인증·타 앱 연결·전송 제약, 실제 검증 경로와 미검증 범위, 공개 문제 로그 비식별화 | TODO | 기존 기기/펌웨어·proxy active:true 조건 및 미확정 프로토콜 고지 보존. 실물 확인 미실행, 위 runtime 식별정보 로그의 비식별화 후속 필요 |
| HACS-04, REL-01, REL-02, REL-03, CI-11 | 통합 릴리스 시 같은 검증 commit/tag·manifest 버전·산출물·권한, 사용자 영향·지원 변경·제한 안내 | N/A | 이번 작업은 릴리스 생성 아님. manifest0.3.1 보존; 기존 공식 v0.3.1 정식 release 확인. 신규 tag/release 생성 미실행 |
| REL-04 | 이전/중단 시 README 상단 경로·유지보수 상태·재등록 여부, 자동 이전으로 오인하지 않는 안내 | N/A | 이전·중단·domain 변경 없음 |
| REL-05 (권장) | 의존성/HA API 변경과 기능 변경 분리, 표준 변경은 명시적 채택 PR로 반영 | PASS | 표준 채택을 문서화하며 version 0.3.1·지원 최소 2025.1.0 보존; 릴리스 별도 |

## 예외와 남은 작업

예외 원본은 `STANDARDS.md`입니다. 아래에 해당 위치를 연결하고, 예외가 실제 없음을 확인한 뒤에만 `없음`으로 바꿉니다.

| 규칙 ID | 예외 위치 / 이유 | 담당자 | 재검토 조건 |
|---|---|---|---|
| 없음 | 승인된 예외 없음 | root | 새 예외 필요 시 재검토 |

| 규칙 ID / TODO | 남은 작업 / issue·PR | 담당자 | 완료 근거 |
|---|---|---|---|
| HA-04/09/11/12 | 기존 manual 연결확인·BLE proxy/service-change 검증·오류 번역키·MAC 로그 마스킹/중복warning 억제 | 유지보수자 | 해당 변경 및 실제 회귀/실물 검증 |
| GOV-04 | 중앙 원격의 해당 리포 현황 갱신 | 유지보수자 | 중앙 로컬 자기행 갱신 완료; 다른 세션 수정과 함께 게시하지 않음 |

최종 검토 시 적용 대상 필수 `TODO`와 `EXCEPTION`, 이유가 있는 `N/A`, 권장 미채택을 구분해 적습니다. CI 성공만으로 실물 기기 검증을 주장하지 않습니다. 실물 검증을 수행했다면 모델·펌웨어·어댑터/proxy·연결 경로와 결과를 별도로 기록합니다.

중앙 보고는 [적용 현황표](https://github.com/eigger/hass-repo-standards/blob/648dad941a118c80325f44c7a13cb5b5b9c1c788/docs/adoption-status.md)의 자기 리포 행에 반영합니다. 리뷰 지적·수정·재검증 결과와 중앙 갱신 실패 사유가 있으면 남은 작업에도 기록합니다.

## 중앙 템플릿 검증

- `python /Volumes/HDD/GitHub/hass-repo-standards/scripts/check_integration.py /Volumes/HDD/GitHub/hass-lywsd02`: 최종 작업 tree PASS(exit0). 기준 SHA는 STANDARDS.md와 동일
- 세 빈 init·정확한 루트 conftest·domain mock_config_entry/mock_client·실제 HA 로딩·기존 회귀 범위 보존: PASS — 중앙검사 및 독립 원본대조/양HA 전체실행 확인
- 공통 fixture의 오류 무시·네트워크 일괄 허용·로딩 생략 금지, 개별 허용 범위·사유: PASS — 루트 중앙 fixture 그대로; 실제 lifecycle/action은 BLE transport만 대체. forwarding 실패 주입은 실패정리 회귀에 한정
- 양언어 본문 보존·의미 일치·기존 고지·고유 배지 독립 리뷰: PASS — review가 기능/진단/옵션/이관/모든 예제 대조, 누락 없음. 기존 clock_drift 과거 이관 문구의 모순은 원문 보존하고 후속 검토
- 공용 CI 이름·파일명·기존 실행 조건과 전용 CI 명명 형식: PASS — 사용자 승인으로 중앙 main/주간 이벤트 적용; actionlint1.7.12 정상
- 승인 예외 실제 사용자 근거·일자·경로·범위 및 설정과 STANDARDS.md 대조: 예외 없음. 이벤트 변경은 2026-10-20 사용자 본 채팅 승인, 중앙 템플릿 그대로 사용

## imagespec payload 예제 검증 환경 — 해당 시

imagespec 미사용이면 실제 requirement/import 확인 근거와 N/A를 기록합니다. 사용 통합은 모든 등록 예제와 각 검증 환경을 기록하고, 이 표의 미확인 값을 PASS로 취급하지 않습니다.

| 환경 / 대상 커밋 | Python / 실제 HA / 플러그인 | 실제 imagespec / current·정확한 하한 근거 | 예제 경로 / 실제 HA schema·준비 경로 | 기대/실제 출력 크기·허용 색상 | pip check·명령·결과·CI 링크 |
|---|---|---|---|---|---|
| N/A | 이 작업 tree | imagespec 미사용 | requirements/import 없음 | payload 기능 없음 | 계약 실행 대상 아님 |

- 중앙 계약 완료·등록 예제 전체 실행·skip/xfail/deselect 없음: N/A — imagespec 미사용
- adapter가 production 준비 함수를 호출하고 실제 context/정규화 payload를 쓰는 독립 검토: N/A — imagespec 미사용
- 템플릿·폰트·이미지·history 실제 지원 context와 외부 통신만 mock한 근거: N/A — imagespec 미사용
- 공통 원본 실제 기본 브랜치 공개 URL 확인 / 중앙 규칙 반영 순서: N/A — imagespec 미사용

- DOC-08 matrix별 imagespec marker 활성/비활성 근거·비활성 N/A와 버전 coverage 없음·일반 HA 회귀 지속·다른 활성 환경의 current/정확한 하한 결과: N/A — imagespec 미사용
- YAML 문자열/목록 액션 입력과 실제 HA 스키마 정규화 후 payload_format 일치·기존 API 보존: N/A — imagespec 미사용

## HA-02 제품 분류 검토 근거

| 항목 | 실제 판단 / 근거 |
|---|---|
| manifest integration_type | device (기존 선언 유지) |
| categories (주 분류 먼저) | sensors.temperature_humidity |
| 주/보조 분류 선택 또는 제외 이유·출처 | 실제 LYWSD02/LYWSD02MMC E-Ink 온습도계 제품. README Supported Models·온도/습도 GATT 기능 근거. docs 구현·review 독립 검토(2026-10-20) |
| categories_review와 manifest의 값/순서/유형 일치 | device / [sensors.temperature_humidity]; config와 manifest 비교 |
| taxonomy snapshot·HACS warning/실패·실제 실행 결과 | 중앙 Core ec18d8b25d1ee39aa8b85a72a170e42bee33228c taxonomy·Hassfest 0 invalid 확인. baseline HACS categories 누락 warning과 변경 tree 신규 HACS 미실행 구분 |

## 실행 증거 (2026-10-20 최종 작업 tree)

구현과 독립 검증은 별도 환경에서 실행했습니다. 최초 로컬 검증 이후 구현을1dcdbf75로 커밋·push하고 PR #10을 생성했습니다. 아래 로컬 결과는 구현 tree 기준이며 원격 결과는 다음 절에 별도 기록합니다.

- 구현: `/tmp/lywsd-ha-current/bin/python -m pytest tests/components/xiaomi_lywsd/ -q` 및 `/tmp/lywsd-ha-minimum/bin/python -m pytest tests/components/xiaomi_lywsd/ -q`: 각각146 passed. 각 `uv pip check --python <환경>/bin/python`: 정상.
- 독립: `/private/tmp/lywsd-independent-review-current/bin/python -m pytest tests/components/xiaomi_lywsd/ -q`, `/private/tmp/lywsd-independent-review-minimum/bin/python -m pytest tests/components/xiaomi_lywsd/ -q`: 각각146 passed. 각 `uv pip check --python <환경>/bin/python`: 정상.
- 독립 설치는 검토 중앙의 `actions/python-environment/install.py`로 실제 HA 및 `bluetooth usb` component 요구사항을 설치. minimum의 정확한 HA requirement인 `aiohasupervisor==0.2.2b5`는 `uv --prerelease=allow`로 해석했으며 HA 요구사항을 완화/교체하지 않음.
- `/private/tmp/lywsd-independent-review-current/bin/ruff check .` 및 `ruff format --check .`: Ruff0.17.1 PASS, 52 files formatted. `/private/tmp/hass-standards-actionlint/actionlint`:1.7.12 PASS. `git diff --check`: PASS.
- `sync_badges.py --check` 및 중앙 `check_integration.py`: PASS. 루트에서도 최종 재확인(exit0).
- `docker run --rm --volume /Volumes/HDD/GitHub/hass-lywsd02:/github/workspace minibig-hassfest:ec18d8`: 공식 Core source `ec18d8b25d1ee39aa8b85a72a170e42bee33228c`의 Dockerfile로 기존 생성된 이미지. entrypoint/manifest validator와 source 파일 SHA256 동일성 확인. 최종 독립 재실행 exit0, Integrations1 / Invalid integrations0.
- HACS 공식 action image `ghcr.io/hacs/action` digest `187499a09c5d…`, linux/amd64: 공개 baseline `4adac9e3903efe58d8746bd5551ba7e36b1aadd8`만10 checks passed. 기존 categories 미선언 WARNING1건. 원본 action이 GitHub에서 ref를 내려받으므로 로컬 미게시 변경을 검증했다고 기록하지 않음.
- 독립 로그: `/private/tmp/lywsd-independent-current-final-tests.log`, `/private/tmp/lywsd-independent-minimum-final-tests.log`, `/private/tmp/lywsd-independent-hassfest-final.log`, `/private/tmp/lywsd-independent-hacs-baseline.log`.

판정: 요청한 공용 CI·문서·HACS Default 적용 및 로컬 검증 완료. 전체 표준 채택은 기존 HA-04/09/11/12와 중앙원격 반영 TODO 때문에 진행 중입니다. 실물 기기 확인·브랜치 보호 설정 변경·신규 release는 수행하지 않았습니다.

## PR 원격 검증

- [PR #10](https://github.com/eigger/hass-lywsd02/pull/10), 구현 head `1dcdbf75f5857066b7488146d1c2a6dcd76b9e48`.
- [Tests](https://github.com/eigger/hass-lywsd02/actions/runs/39426665033): current/minimum 각146 passed 및 각 Ruff lint PASS.
- [Validate](https://github.com/eigger/hass-lywsd02/actions/runs/39426664954): HACS, Hassfest, Central template compliance 모두 PASS. baseline 검사와 구분되는 이번 구현의 원격 검증입니다.
- 독립 review가 해당 구현 커밋 전체 diff 및 실제 양환경146개 재실행 결과를 확인했고 신규 머지 차단 문제 없음.
- `gh api repos/eigger/hass-lywsd02/branches/main/protection`: HTTP404 Branch not protected. 보호 규칙을 추가하거나 검사 우회 옵션을 사용하지 않음.
- 사용자 2026-10-20 본 채팅에서 PR 생성 및 문제없으면 squash merge 승인. 문서 증거 갱신 후 최종 head의 필수 CI를 다시 확인하고 머지합니다.

## 2026-10-23 Downloads 배지 부분 검증

- 기준: 중앙 `b54ac48102d6e326c6929071fdc02ba8fade794e`의 DOC-03/05·배지 생성기와 Validate 형식 검사기만 부분 채택. 대상 시작 SHA `3bfa1d69c1d09df54f02cd7b507d3fad34bc0619`. 기존 전체 채택 결과·예외는 유지하며 이번 변경으로 전체 재채택 완료를 주장하지 않습니다.
- 계획/자체 리뷰: 양언어 관리 블록을 같은 중앙 렌더러로 생성, 잘못된 HACS 데이터 조회 배지를 Downloads로 교체, 집계 의미와 소스 파일 설치 제외를 양언어로 명시. GOV-02에 따라 중앙 호출 pin과 standards-ref를 같은 SHA로 맞춥니다. 이전 기준과 새 기준의 공용 workflow/action 파일은 동일하며 실행 설정·지원 최소·ZIP 배포 설정을 보존합니다.
- 검증 명령·결과와 최종 head SHA·원격 CI 링크는 이 PR 본문에 기록합니다. 문서·배지·형식 검사기 pin만 변경하므로 로컬 HA 환경을 재구축하지 않으며 실제 기기·HA UI·사용자 다운로드 집계는 미검증입니다.
- 실행 결과: WSL Ubuntu Python 3.14.4/PyYAML 6.0.3/packaging 26.0에서 중앙 `scripts/sync_badges.py <repo> --check`, `scripts/check_integration.py <repo>` 및 actionlint 1.7.12의 전체 caller workflow 검사 PASS. Windows Git의 `git diff --check` PASS. 양언어 배지 외 기존 본문은 집계 설명의 정정·추가만 허용하고 보존했습니다.
- 초기 검사 실패 기록: 단일 기준 SHA 계약에 맞지 않는 검사기 pin만의 갱신은 GOV-02에서 거부되어 모든 중앙 pin을 동일 SHA로 정합화했습니다. Windows 중앙 템플릿 CRLF 비교는 실패하여 LF 중앙 snapshot의 Linux 검사로 재검증했습니다. WSL Git은 Windows worktree gitdir 경로를 해석하지 못해 diff 검사를 실패했고 동일 변경의 Windows Git 검사로 대체했습니다. 실패를 PASS로 소급하지 않습니다.

## 2026-10-23 ZIP 릴리스 적용 검증

- 기준 `0c1592977591ecba077a4666d699840062711201` / 대상 시작 `7cabc151c0025579bee80856ed7d41608e3d88eb`. HACS-04/CI-11 부분 갱신이며 기존 전체 채택 이력·예외는 유지합니다.
- 계획: hacs.json에 zip_release:true, filename:xiaomi_lywsd.zip을 추가하고 중앙 release.yml을 같은 SHA로 생성합니다. 기존 caller는 중앙 pin/standards-ref만 변경합니다. 지원 최소·통합 버전·의존성·구현·README 본문을 보존합니다.
- 검증: 중앙 생성기/정적 검사·actionlint·실제 packager로 추적된 통합 파일의 ZIP 루트·manifest/번역/brand 등 런타임 자료 포함과 저장소 메타데이터 제외를 확인합니다. CLI 검증 명령·실제 버전·최종 head SHA·ZIP 결과·독립 리뷰·원격 CI 링크는 이 PR 본문에서 한 번 기록합니다.
- 중앙 실행 로직은 독립 zip_release_review 리뷰에서 지적 수정 후 추가 지적 없음. 대상 caller/메타데이터/ZIP도 별도 독립 리뷰합니다. 로컬 HA 환경 재구축·새 릴리스 발행·asset 업로드·기기 설치는 수행하지 않으며 미실행을 PASS로 기록하지 않습니다. immutable-releases는 enabled:false로 확인했습니다.


## 2026-10-25 중앙 검사기 부분 갱신 검증

- 검토한 중앙 SHA: `1863343638014adb8a4001afc8fddc1a27dc500f`; 적용 시작 커밋: `32d25681ba40a0ae6d7a805029c3ba989f1817bd`.
- 범위: 중앙 pin·standards-ref·검토 기준 기록 정합화. HA 구현·요구 버전은 유지합니다.
- 로컬: Python 3.14.5 / PyYAML 6.0.3, `python scripts/check_integration.py <target>` (검토한 중앙 source에서 실행): PASS.
- actionlint: PASS. PR CI·독립 리뷰 결과는 PR 링크와 check 결과를 확인합니다. 이 로컬 결과만으로 전체 채택 완료를 주장하지 않습니다.
- 독립 리뷰: 별도 review_checker_rollout 담당자가 19개 리포의 workflow 69개·기존 job 100개를 구조 비교했습니다. 새 CI 회귀 지적 없음. 기존 job ID·입력·권한·지원 최소와 통합 코드 보존 및 새 standards job의 중앙 템플릿 일치 확인. 실행 변경 없는 이 기록 추가 전 작업 트리를 검토했습니다.
