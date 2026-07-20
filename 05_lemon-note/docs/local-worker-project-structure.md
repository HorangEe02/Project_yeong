# Mac 로컬 Worker 프로젝트 구조

## 기술 선택

MVP Worker는 Python 기반 FastAPI 서비스로 시작한다.

- API: FastAPI
- 실행: Uvicorn
- 오디오 변환: `ffmpeg`
- ASR: `TranscriptionProvider` 인터페이스 뒤의 VibeVoice-ASR 구현체
- 요약: `SummaryProvider` 인터페이스 뒤의 로컬 LLM 구현체
- 저장소: Local file storage 또는 Supabase Storage Provider
- DB: Supabase Postgres 우선, 로컬 개발은 SQLite/Postgres 대체 가능

## 디렉터리 구조

```text
local-worker/
  README.md
  pyproject.toml
  .env.example
  app/
    main.py
    config.py
    api/
      routes_jobs.py
      routes_meetings.py
      routes_segments.py
      routes_summary.py
      routes_exports.py
      routes_share.py
    core/
      errors.py
      logging.py
      security.py
      time.py
    db/
      session.py
      repositories/
        jobs.py
        meetings.py
        recording_files.py
        transcript_segments.py
        summaries.py
        exports.py
        share_logs.py
    domain/
      models.py
      schemas.py
      statuses.py
    providers/
      transcription/
        base.py
        local_vibevoice.py
        stub.py
      summary/
        base.py
        local_llm.py
        stub.py
      storage/
        base.py
        local_files.py
        supabase_storage.py
      slack/
        webhook.py
    workers/
      pipeline.py
      normalize_audio.py
      asr_worker.py
      summary_worker.py
      export_worker.py
      slack_worker.py
    services/
      job_service.py
      meeting_service.py
      transcript_service.py
      summary_service.py
      export_service.py
      share_service.py
    templates/
      export_summary.md.j2
      export_summary.txt.j2
  tests/
    unit/
    integration/
  samples/
    README.md
```

## Provider 인터페이스

### TranscriptionProvider

```python
class TranscriptionProvider(Protocol):
    def transcribe(
        self,
        audio_path: str,
        language: str = "ko",
        hotwords: list[str] | None = None,
    ) -> TranscriptResult:
        ...
```

반환값은 `speaker_label`, `start_ms`, `end_ms`, `text`, `confidence`를 포함해야 한다.

### SummaryProvider

```python
class SummaryProvider(Protocol):
    def summarize(
        self,
        segments: list[TranscriptSegment],
        language: str = "ko",
    ) -> SummaryResult:
        ...
```

반환값은 `title`, `summary`, `decisions`, `action_items`, `calendar_candidates`를 포함하는 JSON 호환 객체여야 한다.

### StorageProvider

```python
class StorageProvider(Protocol):
    def save_original(self, meeting_id: str, file_name: str, content: BinaryIO) -> StoredFile:
        ...

    def save_normalized(self, meeting_id: str, local_path: str) -> StoredFile:
        ...

    def save_export(self, meeting_id: str, export_id: str, local_path: str) -> StoredFile:
        ...
```

## Job 파이프라인

```text
POST /v1/jobs
  -> JobService.create_job
  -> StorageProvider.save_original
  -> jobs.status = uploaded
  -> Pipeline.enqueue(job_id)

Pipeline.run(job_id)
  -> NormalizeAudioWorker
  -> ASRWorker
  -> SummaryWorker
  -> status = ready_for_review
```

MVP에서는 단일 프로세스 background task로 시작할 수 있다. 단, job 상태와 중간 산출물은 DB에 저장해 프로세스가 죽어도 재시도할 수 있게 한다. 처리량이 필요해지면 queue를 Redis/RQ, Celery, 또는 서버 queue로 교체한다.

## 환경변수

```text
LOCAL_API_TOKEN=
WORKER_BASE_URL=http://localhost:8710
LOCAL_STORAGE_ROOT=./data
DATABASE_URL=
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
SLACK_WEBHOOK_URL=
ASR_PROVIDER=stub
SUMMARY_PROVIDER=stub
FFMPEG_PATH=ffmpeg
```

## 로컬 파일 저장 구조

```text
local-worker/data/
  users/
    {user_id}/
      meetings/
        {meeting_id}/
          original.m4a
          normalized.wav
          exports/
            {export_id}.md
```

## API 모듈 책임

| 모듈 | 책임 |
| --- | --- |
| `routes_jobs.py` | 파일 업로드, job 생성, 상태 조회, 재시도 |
| `routes_meetings.py` | 회의 목록/상세/메타데이터 수정 |
| `routes_segments.py` | segment 조회, 텍스트 보정, 화자명 변경, 북마크 |
| `routes_summary.py` | 요약 조회, 사용자 수정 버전 저장 |
| `routes_exports.py` | Markdown/TXT export 생성 및 다운로드 |
| `routes_share.py` | Slack Webhook 공유 |

## 서버 이전 전략

서버 Worker로 이전할 때 바뀌는 것은 Provider와 queue 실행 위치이다.

| 영역 | MVP | 서버 이전 후 |
| --- | --- | --- |
| ASR | `LocalVibeVoiceProvider` | `ServerVibeVoiceProvider` 또는 GPU Worker |
| 요약 | `LocalLLMProvider` | 서버 LLM Worker |
| 파일 저장 | Local/Supabase | Supabase Storage |
| Queue | local background task | managed queue |
| API 계약 | 유지 | 유지 |

## 테스트 기준

- `POST /v1/jobs`는 stub provider로 end-to-end 테스트한다.
- `NormalizeAudioWorker`는 샘플 파일에서 `normalized.wav` 생성 여부를 검증한다.
- `ASRWorker`는 provider 결과를 segment schema로 정규화하는 단위 테스트를 둔다.
- `SummaryWorker`는 invalid JSON 재시도와 실패 상태 저장을 검증한다.
- `ExportWorker`는 Markdown/TXT snapshot 테스트를 둔다.
- Slack 공유는 실제 Webhook 대신 mock HTTP 서버로 검증한다.
