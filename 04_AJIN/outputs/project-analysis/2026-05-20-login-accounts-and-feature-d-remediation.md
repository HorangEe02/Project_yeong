# 로그인 계정 정리 및 Feature D 차단 해결안

- 작성 시각: 2026-05-20 16:30 KST
- 기준 checkout: 현재 dirty worktree 그대로
- 계정 기준: backend `data/auth.db` 실제 로그인 API 대상과 frontend mock/demo seed를 분리
- 보안 기준: 실제 비밀번호 값, credential hash 값, 토큰, DB 접속 문자열, backend secret 값은 기록하지 않음. 대신 계정별 credential 상태와 비밀번호 운영 기준을 기록함

## 1. Executive Summary

- backend 실제 로그인 가능 계정은 활성 상태이며 credential hash가 존재하는 34개다.
- backend 로그인 차단 계정은 비활성 상태이면서 credential hash가 존재하는 1개다.
- frontend mock/demo seed는 mock backend 또는 데모 UI용이며 실제 backend 로그인 가능 계정으로 간주하지 않는다. 활성 mock seed 31개, 비활성 mock seed 1개가 있다.
- Feature D는 endpoint, flag, scheduler는 통과하지만 공식 출처 live probe가 release blocker로 남아 있다.
- crawler output source/citation 보정 후 citation policy는 fail에서 warning 수준으로 낮아졌고, 네트워크 허용 strict gate 기준 남은 자동 차단은 ECHA/UNECE HTTP 403과 필수 credential 주입이다.

## 2. Backend 실제 로그인 가능 계정

기준 쿼리는 `users.is_active=1`이고 credential hash가 비어 있지 않은 row다. 실제 비밀번호 값과 hash 값은 출력하지 않는다. 로컬 로그인 가능 여부는 `credential hash 존재`로 확인하고, 비밀번호를 모르는 운영자는 `/api/auth/reset-password` 또는 관리자 비밀번호 재설정 흐름으로 새 임시 비밀번호를 발급해야 한다.

### 2-1. 비밀번호 표기 기준

| 표기 | 의미 | 운영 처리 |
|---|---|---|
| `hash 존재 / 로그인 가능` | backend `data/auth.db`에 password hash가 있고 계정이 active 상태다 | 실제 비밀번호 값은 문서화하지 않고 로그인 smoke 또는 reset flow로 확인 |
| `hash 존재 / 비활성` | password hash는 있지만 계정이 inactive라 로그인 API에서 차단된다 | 운영에서는 비활성 유지 또는 승인 후 재활성화 |
| `mock seed 전용` | frontend mock/MSW 데모 계정이며 backend 실계정이 아니다 | 운영 로그인 계정으로 사용하지 않음 |

주의: 과거 데모 공통 비밀번호 seed가 존재하더라도 이 파일에는 값 자체를 쓰지 않는다. 공유 가능한 문서에는 credential status만 남기고, 실제 비밀번호는 password manager/Secret Manager 또는 관리자 reset 절차로 관리한다.

| 역할 | 레벨 | 계정 수 |
|---|---:|---:|
| SYS_ADMIN | 5 | 1 |
| HR_ADMIN | 4 | 1 |
| TEAM_LEAD | 3 | 4 |
| MANAGER | 2 | 6 |
| EMPLOYEE | 1 | 22 |

- 최초 비밀번호 변경 필요 계정: 20개
- 실패 횟수 1회 이상 계정: 1개
- 현재 잠금 표시 계정: 0개

| 사번 | 이름 | 역할 | 레벨 | 부서 | 직책 | 비밀번호/credential 상태 | 변경필요 | 실패횟수 | 잠금 | 최근 로그인 | data_class | source_system |
|---|---|---:|---:|---|---|---|---:|---:|---|---|---|---|
| SYS-0001 | AJIN 운영관리자 | SYS_ADMIN | 5 | IT전략팀 | 시스템 관리자 | hash 존재 / 로그인 가능 | 1 | 1 | - | 2026-05-20T04:28:06.178893+00:00 | system | supabase_cutover |
| HR-0001 | 김인사 | HR_ADMIN | 4 | 총무인사팀 | 팀장 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-04-28T00:41:57.236456+00:00 | unknown | unknown |
| IT-0001 | 김민수 | TEAM_LEAD | 3 | IT전략팀 | 부장 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| PR-0200 | 박생산 | TEAM_LEAD | 3 | 생산관리팀 | 팀장 | hash 존재 / 로그인 가능 | 0 | 0 | - | - | unknown | unknown |
| QA-0100 | 이품질 | TEAM_LEAD | 3 | 품질보증팀 | 팀장 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-04-28T00:18:20.553784+00:00 | unknown | unknown |
| QM-0001 | 이지원 | TEAM_LEAD | 3 | 품질경영팀 | 차장 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| ES-0001 | 박성현 | MANAGER | 2 | ESG경영팀 | 과장 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| PT-0301 | 정기술 | MANAGER | 2 | 생산기술팀 | 과장 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-04-03T06:22:05.868517+00:00 | unknown | unknown |
| PU-0001 | 최민지 | MANAGER | 2 | 구매팀 | 과장 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| QA-0101 | 최품과 | MANAGER | 2 | 품질보증팀 | 과장 | hash 존재 / 로그인 가능 | 0 | 0 | - | - | unknown | unknown |
| RE-0001 | 황지윤 | MANAGER | 2 | 전장선행개발팀 | 과장 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| SL-0401 | 한영업 | MANAGER | 2 | 영업팀 | 과장 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-03-30T08:11:26.582659+00:00 | unknown | unknown |
| AT-0001 | 서은우 | EMPLOYEE | 1 | 자동화기술팀 | 사원 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| ED-0001 | 류민재 | EMPLOYEE | 1 | 기술교육원 | 사원 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| EX-0001 | 안서준 | EMPLOYEE | 1 | 경영지원 | 주임 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| GS-0001 | 정동현 | EMPLOYEE | 1 | 해외지원팀 | 대리 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| HR-0000 | 김노예 | EMPLOYEE | 1 | 총무인사팀 | 사원 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-03-27T07:36:25.735909+00:00 | unknown | unknown |
| HR-0002 | 송수아 | EMPLOYEE | 1 | 인사관리 | 사원 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| HR-9999 | 노예 | EMPLOYEE | 1 | 인사관리 | 사원 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-04-03T06:28:55.163298+00:00 | unknown | unknown |
| IT-0701 | 임아이 | EMPLOYEE | 1 | IT전략팀 | 사원 | hash 존재 / 로그인 가능 | 0 | 0 | - | - | unknown | unknown |
| MD-0001 | 한시우 | EMPLOYEE | 1 | 금형생산팀 | 사원 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| MF-0901 | 오금형 | EMPLOYEE | 1 | 금형생산팀 | 주임 | hash 존재 / 로그인 가능 | 0 | 0 | - | - | unknown | unknown |
| PD-0001 | 임다은 | EMPLOYEE | 1 | 부품개발팀 | 사원 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| PM-0001 | 윤지아 | EMPLOYEE | 1 | 생산관리팀 | 주임 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| PT-0001 | 오지유 | EMPLOYEE | 1 | 생산기술팀 | 사원 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| PU-0601 | 송구매 | EMPLOYEE | 1 | 구매팀 | 사원 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-04-02T23:54:18.574690+00:00 | unknown | unknown |
| QA-0001 | 강예은 | EMPLOYEE | 1 | 품질보증팀 | 대리 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| QA-0102 | 윤품대 | EMPLOYEE | 1 | 품질보증팀 | 대리 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-04-28T03:20:23.023653+00:00 | unknown | unknown |
| RB-0001 | 권유준 | EMPLOYEE | 1 | 바디선행개발팀 | 대리 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| RD-0801 | 강연구 | EMPLOYEE | 1 | 바디선행개발팀 | 사원 | hash 존재 / 로그인 가능 | 0 | 0 | - | - | unknown | unknown |
| SF-0001 | 조승우 | EMPLOYEE | 1 | 안전보건팀 | 대리 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| SF-0501 | 장안전 | EMPLOYEE | 1 | 안전보건팀 | 대리 | hash 존재 / 로그인 가능 | 0 | 0 | - | 2026-03-31T09:53:31.691434+00:00 | unknown | unknown |
| SL-0001 | 장태현 | EMPLOYEE | 1 | 영업팀 | 주임 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |
| VR-0001 | 신하린 | EMPLOYEE | 1 | 비전연구팀 | 사원 | hash 존재 / 로그인 가능 | 1 | 0 | - | - | unknown | unknown |

## 3. Backend 로그인 차단 계정

비활성 계정은 credential이 있더라도 `/api/auth/login`에서 403으로 차단되는 계정이다.

| 사번 | 이름 | 역할 | 레벨 | 부서 | 직책 | 비밀번호/credential 상태 | 변경필요 | 실패횟수 | 잠금 | 최근 로그인 | data_class | source_system |
|---|---|---:|---:|---|---|---|---:|---:|---|---|---|---|
| admin | 시스템관리자 | INACTIVE |  |  |  | hash 존재 / 비활성 | 1 | 0 | - | 2026-04-28T03:50:45.570550+00:00 | system | bootstrap_admin |

## 4. Frontend mock/demo seed 계정

frontend seed는 mock API/MSW 또는 데모 UI 기준이다. 공통 데모 비밀번호 seed를 사용하지만, 이 문서에는 값을 쓰지 않는다. frontend seed 계정의 `비밀번호/credential 상태`는 `mock seed 전용`이다.

| 역할 | seed 수 | 용도 |
|---|---:|---|
| SYS_ADMIN | 2 | 시스템 관리 데모, 전역 설정/관리 화면 진입 |
| HR_ADMIN | 3 | 인사/사용자 관리 데모 |
| TEAM_LEAD | 8 | 본부장/팀장 권한 및 본부 통계 데모 |
| MANAGER | 7 | 부서 관리자 권한 데모 |
| EMPLOYEE | 11 | 일반 직원 검색, 문서 작성, 온보딩 데모 |
| INACTIVE | 1 | 비활성 접근 차단 데모 |

주요 mock 부서 분포:

| 부서 | seed 수 |
|---|---:|
| 품질보증팀 | 4 |
| 인사팀 | 3 |
| 환경안전팀 | 3 |
| 시스템관리팀 | 2 |
| 품질관리팀 | 2 |
| 생산기술팀 | 2 |
| 해외영업팀 | 2 |
| 법무팀 | 2 |
| 검사팀 | 1 |
| 금형팀 | 1 |
| 정비팀 | 1 |
| 프레스팀 | 1 |
| 국내영업팀 | 1 |
| 영업기획팀 | 1 |
| 연구개발팀 | 1 |
| 설계팀 | 1 |
| 시작팀 | 1 |
| 구매팀 | 1 |
| 재무팀 | 1 |
| 시설관리팀 | 1 |

## 5. Feature D 차단 원인

| Gate | 현재 판정 | 원인 | release 영향 |
|---|---|---|---|
| endpoint surface | pass | compliance 19개, notifications 6개, feature flag endpoint 존재 | 차단 아님 |
| D2-D5 flag posture | pass | D1 기본 활성, D2-D5 기본 비활성 | 차단 아님 |
| notification scheduler | pass | outbox dispatcher, adapter posture, Celery schedule 연결 | 차단 아님 |
| official source live probes | fail | ECHA Candidate List HTTP 403, UNECE WP.29 HTTP 403, `LAW_GO_KR_OC`/`CUSTOMS_API_KEY` 미주입 | release blocker |
| citation/source policy | warn | MSDS current output item 0건 warning만 남음 | blocker 아님, 운영 검토 필요 |

차단을 네 가지로 분해한다.

| 분류 | 내용 | 우선순위 |
|---|---|---:|
| credential 미준비 | 국가법령정보, UNI-PASS 관세율 API credential이 strict gate에 없다 | P0 |
| 공식 source HTTP posture | ECHA Candidate List와 UNECE WP.29가 현재 verifier HTTP posture에서 403을 반환한다 | P0 |
| crawler output schema 불일치 | 과거 단일 JSON 일부에 source_type/source_reason이 없었다. 현재 보정 완료 | 완료 |
| citation 누락 | APQP/OEM/ESG/통상 일부 item에 공식 URL이 없었다. 현재 보정 완료 | 완료 |

## 6. 상세 구현 및 수정, 보완 방안

### P0 - Credential 및 live probe 운영화

1. `LAW_GO_KR_OC`와 `CUSTOMS_API_KEY`를 release secret으로 준비한다.
2. local/CI에서는 secret 값을 출력하지 않고 존재 여부만 verifier report에 기록한다.
3. official source live probe를 외부 네트워크가 허용된 release runner에서 실행한다.
4. 실패 시 HTTP status, method, ETag, Last-Modified, redacted URL만 report에 남긴다.

### P0 - HTTP probe 방식 보완

1. AIAG APQP/OEM quality probe는 HEAD 400을 피하기 위해 공식 landing URL과 GET-first probe를 사용한다.
2. ECHA/UNECE처럼 403 또는 bot posture가 발생하는 공식 사이트는 crawler 공통 User-Agent, retry, GET fallback을 verifier와 공유하고, 필요하면 공식 대체 endpoint 또는 published static data endpoint를 별도 probe로 둔다.
3. 네트워크 차단과 credential 누락을 같은 fail로 뭉개지 않고 `credential_missing`과 `official_source_http_posture`로 분류한다.
4. official site가 공개 웹 접근을 제한하면 crawler는 curated fallback을 유지하되 strict release에서는 live probe 실패를 blocker로 남긴다.

### P1 - Crawler output contract 고정

1. 모든 `data/crawled/*.json` current output은 top-level `source_type`, `source`, `crawled_at`, `source_reason` 또는 `errors`를 가져야 한다.
2. item 단위에는 `reference_url` 또는 `url`을 두고, verifier whitelist 공식 도메인만 통과시킨다.
3. BaseCrawler 기반 crawler는 기존 source_type을 유지하고, non-Base crawler(APQP/OEM)는 저장 시 curated baseline metadata를 명시한다.
4. MSDS는 item 0건 warning을 남기되, ECHA live fetch 또는 curated seed를 보강해 release 전 warning을 제거한다.

### P1 - 테스트 및 회귀

1. source metadata 누락, citation 누락, 비공식 citation, credential 누락 fixture를 모두 fail로 검증한다.
2. AIAG GET-first probe는 HEAD reject 사이트에 대해 GET만으로 pass 가능한지 unit test로 고정한다.
3. `make feature-d-release-check`는 credential/network가 없는 개발 환경에서 fail이 정상이며, release runner에서는 P0 secret과 네트워크를 준비한 뒤 pass를 목표로 한다.

## 7. 공식 근거

- 국가법령정보 Open API: https://open.law.go.kr/LSO/openApi/guideList.do
- ECHA Candidate List: https://www.echa.europa.eu/candidate-list-table
- EUR-Lex reuse/API context: https://eur-lex.europa.eu/content/help/data-reuse/reuse-contents-eurlex-details.html?locale=en
- AIAG APQP/Control Plan: https://go.aiag.org/apqp-cp
- UNECE WP.29: https://unece.org/wp29-introduction
- OpenDART API guide: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002
- Celery periodic tasks: https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html

## 8. 완료 기준

- backend 실제 로그인 가능 계정과 frontend mock seed가 혼동 없이 분리되어 있다.
- 문서와 verifier report에 secret 값이 노출되지 않는다.
- Feature D citation/source policy는 fail 없이 pass 또는 warning 이하로 유지된다.
- release runner에서 official live probe가 credential과 네트워크를 갖춘 상태로 pass해야 Feature D blocker를 제거할 수 있다.
