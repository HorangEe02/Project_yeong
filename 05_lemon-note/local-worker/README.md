# 로컬 데모 Worker (회의 녹음 앱 MVP)

비용 0으로 동작하는 데모용 MVP. 스마트폰/웹에서 녹음 → 로컬 Worker가 (stub) 전사·요약 →
회의록 조회, 발화 클릭 재생, 요약 편집, MD/TXT 내보내기, Slack 공유까지 전 과정을 시연한다.

- **금전 비용**: $0 (클라우드·API·유료 모델 없음)
- **의존성**: `fastapi`, `uvicorn`, `python-multipart` (3개뿐)
- **AI 처리**: 기본은 **stub**(모델 다운로드/설치 불필요). 어떤 Mac에서도 즉시 실행.
- **저장소**: SQLite(파일 1개) + 로컬 파일 시스템(`./data`)

## 빠른 실행

```bash
cd local-worker
./run.sh
# 또는 수동:
# python3 -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt
# uvicorn app.main:app --host 127.0.0.1 --port 8710 --reload
```

브라우저에서 <http://localhost:8710> 접속 → 회의 녹음/업로드 → 처리 완료 후 회의록 확인.

## 구조

```
local-worker/
  app/
    main.py            # FastAPI 앱 + 전체 엔드포인트 + 정적 프론트 서빙
    config.py          # 환경변수 설정
    db.py              # SQLite 스키마/헬퍼/요약 버전 저장
    models.py          # 요청 본문 검증(Pydantic)
    pipeline.py        # 백그라운드 처리 파이프라인
    textbuild.py       # 내보내기(MD/TXT)·Slack 텍스트 빌더
    providers/
      transcription.py # ASR: Stub / (선택) FasterWhisper
      summary.py       # 요약: Stub / (선택) Ollama
      storage.py       # 로컬 파일 저장
      slack.py         # Slack Webhook 전송
  web/                 # 바닐라 프론트엔드(HTML/CSS/JS)
  data/                # 런타임 생성(원본 음성/DB/내보내기) — .gitignore
```

## 처리 상태 흐름

`uploaded → normalizing_audio → transcribing → summarizing → ready_for_review` (실패 시 `failed`)

각 단계에서 `jobs.status`와 `meetings.status`를 함께 갱신한다(상태 이중 소스 불일치 방지).

## 실제 로컬 모델로 전환 (여전히 무료, 검증됨)

Provider 인터페이스만 바꾸면 앱 API·DB 스키마는 그대로다. Apple M4 Pro / 24GB에서 검증한 값 기준.

```bash
# 1) 전사(ASR): faster-whisper — 별도 ffmpeg 불필요(PyAV로 디코딩)
pip install faster-whisper          # requirements.txt 주석 해제해도 됨

# 2) 요약(LLM): Ollama
brew install ollama
ollama serve &                      # 백그라운드 구동
ollama pull gemma4:e4b              # 기본 ≈9.6GB (또는: ollama pull qwen3.5)

# 3) 실제 모델로 실행 (stub 지연 제거)
ASR_PROVIDER=faster_whisper SUMMARY_PROVIDER=ollama STUB_STAGE_DELAY=0 ./run.sh
```

요약 모델은 `OLLAMA_MODEL`로 교체한다(기본 `gemma4:e4b`). gemma4/qwen3.5 같은 **추론(thinking)
모델**은 `OLLAMA_THINK=false` 권장(요약 속도↑, JSON 안정). qwen2.5 등 비추론 모델은 `OLLAMA_THINK`를
빈 값으로 둔다. `<think>` 블록·코드펜스는 Provider가 자동 제거한다.

**검증 결과(48초 한국어 음성, M4 Pro/24GB):**

| 모델 | 전사 시간 | 한국어 품질 |
| --- | --- | --- |
| `small` | ≈8초 | 양호(오탈자 일부: 보존→보조나, 검토해서→검토에서) |
| `medium` (기본·권장) | ≈19초 | 오탈자 거의 없음, 문장 단위 분할·구두점 정확 |

전사+요약 전체 파이프라인 ≈33초에 `ready_for_review`. 요약(qwen2.5:7b)은 결정사항·할 일·
일정 후보·근거 세그먼트까지 구조화 JSON으로 생성.

| 항목 | 기본값 | 비고 |
| --- | --- | --- |
| `WHISPER_MODEL` | `medium` | 더 빠르게 `small`, 최상 품질 `large-v3`(느림) |
| `WHISPER_DEVICE` / `WHISPER_COMPUTE` | `cpu` / `int8` | Mac은 CPU(CTranslate2가 Metal 미지원) |
| `OLLAMA_MODEL` | `gemma4:e4b` | `qwen3.5`, `qwen2.5:7b`, `gemma2:9b` 등 |
| `OLLAMA_THINK` | `false` | 추론모델용. 비추론 모델(qwen2.5)은 빈 값 |

### 화자 구분(diarization)

두 가지 백엔드를 지원한다. `DIARIZER=auto`(기본)이면 모델이 있는 쪽을 자동 선택한다.

**① sherpa-onnx (권장, 오픈 모델·HF 토큰 불필요) — 검증됨**

```bash
pip install sherpa-onnx
./scripts/setup_diarization.sh     # 오픈 모델 2개(약 46MB) 다운로드
ASR_PROVIDER=faster_whisper SUMMARY_PROVIDER=ollama STUB_STAGE_DELAY=0 ./run.sh
```

3인 화자 합성음(48초)에서 검증: 발화 경계 정확, 화자 3명 분리(비슷한 TTS 목소리라 일부
병합, 실제 사람 목소리는 더 잘 갈림). 전사+화자구분+요약 전체 ≈31초.

**② pyannote.audio (HF 토큰 필요)**

```bash
pip install pyannote.audio
# huggingface.co 에서 pyannote/speaker-diarization-3.1 약관 동의 + read 토큰 발급
HF_TOKEN=hf_xxx DIARIZER=pyannote ASR_PROVIDER=faster_whisper ... ./run.sh
```

둘 다 없으면(`DIARIZER=none` 또는 모델/토큰 부재) 전사는 정상 동작하되 모든 발화가 `Speaker 1`로
표기된다. 화자 수를 알면 `DIAR_NUM_SPEAKERS=3`, 자동 분리 민감도는 `DIAR_THRESHOLD`(기본 0.5)로 조정.

## API 요약 (Base: `http://localhost:8710/v1`)

| 메서드 | 경로 | 설명 |
| --- | --- | --- |
| POST | `/jobs` | 녹음 업로드 + 처리 job 생성 |
| GET | `/jobs/{id}` | 처리 상태 폴링 |
| GET | `/meetings` | 회의 목록(status/q/limit/cursor) |
| GET | `/meetings/{id}` | 회의 상세 |
| PATCH | `/meetings/{id}` | 제목 수정 |
| DELETE | `/meetings/{id}` | soft delete |
| GET | `/meetings/{id}/segments` | 전사 세그먼트 |
| PATCH | `/meetings/{id}/segments/{sid}` | 텍스트 보정/북마크 |
| PATCH | `/meetings/{id}/speakers/{label}` | 화자명 일괄 변경 |
| GET/PATCH | `/meetings/{id}/summary` | 요약 조회/사용자 수정 버전 저장 |
| POST | `/meetings/{id}/exports` | MD/TXT 내보내기 |
| GET | `/exports/{id}/download` | 내보내기 다운로드 |
| POST | `/meetings/{id}/share/slack` | Slack Webhook 공유 |
| GET | `/recording-files/{id}/stream` | 음성 스트림(Range 지원) |
| POST | `/meetings/{id}/retry` | 재처리 |

## 데모 편의를 위해 반영한 설계 결정 (문서 검토 findings)

- 단일 로컬 사용자(`local-user-0001`) 시드 → `user_id` 출처 문제 해소(#1)
- 업로드 시 녹음 동의 저장(#2), `hotwords` 영속화(#4)
- `jobs.status`/`meetings.status` write-through(#5)
- 화자명 변경 시 alias + 세그먼트 write-through(#10)
- Slack `channel_label`은 표시용 라벨(Webhook 한계, #11) — 미설정 시 시뮬레이션
- soft-delete·audit_logs 기록 포함(#6, #16)

전체 검토 결과는 `../docs/design-review-findings.md` 참고.

## Supabase 연결

프로젝트 **Lemon-note** (`YOUR-PROJECT-REF`, ap-northeast-1)에 회의록 스키마를 생성해 두었다.

- 13개 테이블(profiles/meetings/jobs/recording_files/transcript_segments/… /audit_logs) + 인덱스
- **모든 테이블 RLS 활성화(정책 없음)** → 현재는 `service_role` 만 접근 가능한 안전한 잠금 상태.
  Supabase Auth 연동 시 `meeting_id → meetings.user_id = auth.uid()` 정책을 추가한다(db-schema.md의 RLS 방향).
- 연결값은 `.env`(gitignore)에 있음: `SUPABASE_URL`, `SUPABASE_ANON_KEY`(공개). config가 `.env`를 자동 로드한다.

```bash
./scripts/check_supabase.sh      # REST 도달성 점검(200 = 연결 정상)
curl -s localhost:8710/v1/health # supabase_configured / supabase_url 확인
```

스키마는 앱의 실제 데이터 형태(uuid PK, `text[]` hotwords/attendees, `uuid[]` source_segment_ids,
`jsonb` raw_json, 모든 CHECK/FK 제약)를 담을 수 있음을 실제 데이터 그래프 삽입으로 검증했다.

### 직접 Postgres 연결 (DATABASE_URL)

비밀번호는 **본인만** 입력한다(도구가 대신 넣지 않음).

```bash
# 1) .env 의 DATABASE_URL 에서 [YOUR-PASSWORD] 를 본인 DB 비밀번호로 교체
#    (특수문자 percent-encode: ! -> %21). Shared Pooler, host ...pooler.supabase.com, port 6543
#    postgresql://postgres.YOUR-PROJECT-REF:[YOUR-PASSWORD]@aws-0-ap-northeast-1.pooler.supabase.com:6543/postgres
# 2) 연결 검증
./.venv/bin/pip install 'psycopg[binary]'
./.venv/bin/python scripts/verify_supabase_db.py     # public 테이블·행수 출력하면 연결 성공
```

**현재 상태**: worker 실행 DB는 로컬 MVP용 **SQLite** 그대로다(`db_backend: sqlite`). 위 연결은 스키마·연결
검증까지 완료된 상태이며, **worker의 읽기/쓰기를 Supabase Postgres로 전환**하려면 `db.py`(SQLite 전용 SQL)를
psycopg 기반 Postgres 백엔드로 확장하고 `providers/storage.py`에 SupabaseStorageProvider(음성/내보내기 파일)를
붙이면 된다. API·스키마 변경 없이 저장 위치만 이전된다(문서의 local_mac → server_gpu 전략). 이는 별도 구현 단계다.

> 참고: RLS가 켜져 있고 정책이 없으므로 anon/publishable 키로는 데이터가 보이지 않는다(service_role 또는
> DATABASE_URL 직접 연결만 접근). 사용자별 접근을 열려면 Supabase Auth 연동 + `auth.uid()` 기반 정책을 추가한다.
