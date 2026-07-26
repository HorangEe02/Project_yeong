# 경합 조건 · 부분 쓰기 — 확인된 결함과 수정

동시 요청 상황에서 데이터가 유실되거나 상태가 고착되는 문제를 감사하고 수정한 기록.
재현 하니스가 `local-worker/scripts/repro_races.py` 에 함께 들어 있어, 수정이 되돌아가면
바로 잡힌다.

## 왜 문제가 되는가

이 앱은 **인증 없는 공개 데모이고 계정이 하나**다. `AUTH_ENABLED=false` 라 모든 방문자가
같은 `user_id` 로 같은 행을 읽고 쓴다. 즉 "동시 사용자 두 명"은 예외 상황이 아니라
기본 상황이다.

그리고 `WRITE_PROTECTED=1` 이 모든 쓰기를 막지는 않는다. `require_write` 가 걸린 라우트만 401 이다.
아래 결함은 전부 게이트가 없던 경로를 통해 실제로 도달했다.

### 게이트 정리 (완료)

변경 라우트 26개를 전수 열거해 **게이트 없는 4개**를 찾아 정책에 맞춰 채웠다.
정책은 `config.py` 에 이미 문서화돼 있던 것을 그대로 따랐다 — *"0 이면 읽기·업로드만 열리고
수정·삭제는 401"*.

| 라우트 | 이전 | 이후 | 근거 |
|---|---|---|---|
| `POST /v1/jobs` | 없음 | `require_user` | 업로드는 정책상 열린 예외. `require_write` 를 달면 **공개 데모에서 회의 생성 자체가 401** 이 되어 앱의 존재 이유가 사라진다 |
| `POST /v1/uploads/presign` | 없음 | `require_user` | `jobs` 와 한 쌍인 대용량 업로드 경로 — 게이트가 달라지면 경로가 반쪽이 된다 |
| `POST /v1/meetings/{id}/exports` | 없음 | `require_user` | 회의를 바꾸지 않는 파생 산출물이고 프런트 내보내기 버튼이 프로덕션에서 쓴다 |
| `POST /v1/meetings/{id}/retry` | 없음 | **`require_write`** | 기존 전사·요약을 **삭제하고** 다시 만드는 파괴적 조작. 프런트는 호출하지 않는다 |

`require_user` 는 `AUTH_ENABLED=false` 인 지금은 통과하지만(데모 동작 불변) 토큰이 설정되면
인증을 요구하고 사용자 신원도 토큰에서 온다. 즉 지금 당장의 차단이 아니라 **신원 개념을 붙이는**
변경이다. 실제 차단이 걸린 건 `retry` 하나다.

`GET /v1/shared/{token}` 은 공유 링크의 목적 자체가 공개 열람이라 그대로 둔다(비밀번호 시도
상한은 아래 3번에서 고쳤다).

실측(`WRITE_PROTECTED=1`): `jobs` 422 `audio_required` · `presign` 201 · `exports` 201 ·
`retry` **401 `write_disabled`** · (대조군) `DELETE /meetings/{id}`·`PATCH .../summary` 401.

## 수정한 결함

### 1. 파이프라인 실패가 자기 자신을 숨겨 상태가 영구 고착 (Postgres 전용)

같은 회의에 파이프라인이 두 번 돌면 `transcript_segments` 의
`UNIQUE(meeting_id, segment_index)` 를 위반한다. **Postgres 는 문장 하나가 실패하면
트랜잭션 전체가 aborted 로 바뀌어 이후 모든 쿼리가 거부된다.** 그래서 `except` 절에서
실패를 기록하려는 시도(`_set_status('failed')`, `db.audit('pipeline_failed')`) 가
둘 다 죽고, 그 예외가 다시 `except: pass` 에 삼켜졌다.

실측 결과 (하니스):

| | 수정 전 Postgres | 수정 전 SQLite | 수정 후 (양쪽) |
|---|---|---|---|
| 2차 실행 후 status | **`transcribing`** | `failed` | `failed` |
| `error_code` | **`null`** | `pipeline_error` | `pipeline_error` |
| `pipeline_failed` 알림 | **0건** | 1건 | 1건 |

이미 완료된 회의(`ready_for_review`)가 `transcribing` 으로 **되돌아가 그대로 멈췄다.**
전사와 요약은 DB 에 남아 있는데 status 만 '처리 중' 이라 **사용자가 검토 화면에
영원히 도달할 수 없고**, 오류 표시도 알림도 생기지 않았다.

**SQLite 에서는 재현되지 않는다** — 로컬 검증만으로는 절대 잡히지 않는 종류의 결함이다.

수정: `_PgConn` 에 `rollback()` 을 추가하고(`sqlite3.Connection` 에는 원래 있다),
파이프라인 `except` 진입 직후 롤백해 실패 기록이 실행될 수 있게 했다. 커밋 안 된
부분 전사도 함께 버려진다.

### 2. 동시 재처리로 파이프라인 두 개가 같은 회의에 붙음

`POST /retry` 에 잠금도 상태 검사도 없어, 두 번 연달아 호출하면 파이프라인 2개가
같은 회의에 세그먼트를 넣다가 위 1번으로 이어졌다.

수정: 삭제보다 **먼저** job 을 원자적으로 선점한다. `attempts` 를 compare-and-swap
조건으로 쓰고(`WHERE id=? AND attempts=?`) 진행 중 상태를 제외해, 동시 요청 중
하나만 200 이고 나머지는 **409 `job_busy`** 를 받는다. `jobs_status_check` 제약 때문에
새 상태값을 만들 수 없어 `attempts` 를 잠금 토큰으로 썼다.

프런트엔드는 이 엔드포인트를 호출하지 않으므로(재시도 버튼은 새 회의 화면으로 이동만 한다)
화면 영향은 없다.

### 3. 공유 링크 비밀번호 잠금을 병렬 요청으로 우회

시도 횟수 상한(10회) 검사가 **먼저 읽어둔 스냅샷**을 보고 있어, 병렬 요청이 전부
검사를 통과했다. 카운터 증가 자체는 원자적이라 무한은 아니지만 상한을 넘겼다.

실측 (상한 10, 9회 소진 후 병렬 버스트):

| 버스트 | 비밀번호 판정을 받은 요청 | 총 시도 | 수정 후 |
|---|---|---|---|
| 60 | 11 | 20 | 1 (총 10) |
| 200 | 14 | 23 | 1 (총 10) |
| 400 | 14 | 23 | 1 (총 10) |

한 인스턴스에서는 ~14회에서 평탄해진다(스레드풀 + pbkdf2 100k회의 CPU 경합).
다만 서버리스는 수평 확장하므로 인스턴스마다 자기 스냅샷을 갖는다.

수정: 비밀번호를 검증하기 **전에** 조건부 UPDATE
(`WHERE failed_attempts < 상한`)로 시도 슬롯을 선점하고, 영향 행이 0이면 429.
비밀번호가 맞았으면 선점한 슬롯을 되돌린다.

### 4. 설정 동시 저장에서 갱신 유실

`PATCH /v1/me/settings` 가 값을 읽어 파이썬에서 병합한 뒤 `settings` 컬럼을 **통째로**
되썼다(`settings = excluded.settings`). 두 방문자가 서로 다른 항목을 같은 시각에
저장하면 나중에 커밋한 쪽이 앞 쪽 변경을 지웠다.

수정: 요청에 담긴 키만 보내고 병합을 DB 가 원자적으로 하게 했다.
Postgres 는 jsonb `||`, SQLite 는 `json_patch()`. 응답도 실제 저장 결과를 되읽어 돌려준다.

### 5. 요약 버전 채번이 비원자적

`SELECT MAX(version)+1` 과 `INSERT` 가 따로여서 동시 저장이 같은 번호를 받아
`UNIQUE(meeting_id, version)` 위반으로 터졌다(그리고 Postgres 에서는 그 예외가 1번을
촉발했다). 함수 주석은 "원자적으로 채번한다"고 **잘못** 적혀 있었다.

수정: `INSERT ... SELECT COALESCE(MAX(version),0)+1` 단일 문장. 커밋 전인 동시 INSERT 가
같은 번호를 계산하는 잔여 창은 UNIQUE 제약이 예외로 잡는다 — 조용한 유실은 없다.

### 6. 내보내기 실패 시 고아 파일

파일을 먼저 저장하고 DB 행을 나중에 넣어서, INSERT 가 실패하면(예: 동시 `retry` 가
`summary_versions` 를 지워 FK 위반) 파일만 남았다. `_purge_meeting` 은 `exports` 행을
뒤져 파일을 지우므로 **행 없는 파일은 어떤 경로로도 회수되지 않았다.**

수정: INSERT 실패 시 방금 쓴 파일을 지우고 예외를 다시 올린다.

## 재현 하니스 사용법

로컬 전용이다. 안전장치가 비로컬 DB 를 거부한다 — `local-worker/.env` 에 프로덕션
접속 정보가 들어 있을 수 있어서다.

```bash
cd local-worker

# 1) 로컬 Postgres (1번 결함은 Postgres 에서만 재현된다)
docker run -d --name lemon-race-pg -e POSTGRES_PASSWORD=postgres \
    -e POSTGRES_DB=lemonrace -p 55432:5432 postgres:16
./.venv/bin/python scripts/repro_races.py init-schema \
    --pg-dsn postgresql://postgres:postgres@127.0.0.1:55432/lemonrace

# 2) 전체 검사
./.venv/bin/python scripts/repro_races.py all \
    --pg-dsn postgresql://postgres:postgres@127.0.0.1:55432/lemonrace
```

종료 코드: `0` 경합 미검출 · `1` 재현됨(결함 존재) · `2` 오류 또는 안전장치 거부.
CI 회귀 게이트로 그대로 쓸 수 있다.

검사 항목: `abort-swallow`(1번, 두 백엔드 대조) · `retry-lock`(2번) ·
`share-lockout`(3번) · `settings-merge`(4번) · `smoke`(5·6번 및 정상 경로 회귀) ·
`gates`(게이트 정리 — `WRITE_PROTECTED=1` 로 띄워 열려야 할 것과 401 이어야 할 것을 실측).

정리: `docker rm -f lemon-race-pg`

## 아직 수정하지 않은 것

- `_purge_meeting` / `empty_trash` 가 스토리지 파일을 DB 커밋보다 먼저 지운다 →
  중간 실패 시 파일만 사라진다. `require_write` 라 현재 프로덕션에서는 401 이다.
- `share_slack` 이 외부 전송을 먼저 하고 기록을 나중에 커밋한다.
- 프런트엔드 쪽 경합(요청 순서 토큰 부재, in-flight 잠금 부재, 요약 저장 낙관적 잠금
  부재 등)은 별도 작업으로 남겨 두었다.
- 폴더 이동 사이클 검사와 공유 링크 개수 상한의 검사-후-사용.
