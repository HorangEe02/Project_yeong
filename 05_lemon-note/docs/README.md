# 회의 녹음 앱 실제 구현 문서

작성일: 2026-07-15

이 문서 세트는 루트의 `meeting-recorder-implementation-plan.md`를 실제 구현 착수용 문서로 분할한 것이다. MVP는 스마트폰 또는 웹에서 녹음 파일을 만들고, 사용자의 Mac 로컬 Worker가 전사와 요약을 처리한 뒤, 앱에서 회의록 조회, 발화 클릭 재생, 요약 편집, 내보내기, Slack 공유를 제공하는 범위로 정의한다.

## 구현 기준

- 원본 음성 파일은 절대 덮어쓰지 않는다.
- 전사 결과와 요약 결과는 별도 버전으로 저장한다.
- 사용자가 수정할 수 있는 대상은 화자명, 발화 텍스트 보정값, 요약본, 결정사항, 할 일, 일정 후보이다.
- MVP에서는 AI 처리를 Mac 로컬 Worker에서 실행한다.
- 서버 이전 시 앱 API, job 상태값, transcript segment 스키마, summary JSON 스키마를 유지한다.
- 캘린더 일정은 자동 등록하지 않고 사용자의 승인 후 등록한다.

## 문서 구성

| 문서 | 목적 |
| --- | --- |
| [features/01-recording-and-upload.md](features/01-recording-and-upload.md) | 녹음, 파일 검증, 업로드, job 생성 흐름 |
| [features/02-transcription-and-playback.md](features/02-transcription-and-playback.md) | VibeVoice-ASR 전사, 화자 구분, 발화 클릭 재생 |
| [features/03-summary-review-and-calendar.md](features/03-summary-review-and-calendar.md) | 로컬 LLM 요약, 결정사항, 할 일, 일정 후보 검토 |
| [features/04-export-and-slack-sharing.md](features/04-export-and-slack-sharing.md) | Markdown/TXT 내보내기, 음성 클립, Slack Webhook 공유 |
| [features/05-security-retention-and-permissions.md](features/05-security-retention-and-permissions.md) | 녹음 동의, 권한, 보존/삭제, 감사 로그 |
| [mvp-work-breakdown.md](mvp-work-breakdown.md) | MVP 에픽, 작업 단위, 완료 조건 |
| [api-spec.md](api-spec.md) | 로컬 Worker와 향후 서버가 유지해야 할 REST API 계약 |
| [db-schema.md](db-schema.md) | Supabase/Postgres 기준 데이터 모델과 저장 경로 |
| [local-worker-project-structure.md](local-worker-project-structure.md) | Mac 로컬 Worker 프로젝트 구조와 Provider 인터페이스 |

## MVP 시스템 흐름

```text
Web 또는 모바일 녹음 클라이언트
  -> POST /v1/jobs multipart upload
  -> Mac Local Worker
     -> normalize audio
     -> transcribe with LocalVibeVoiceProvider
     -> summarize with LocalLLMProvider
     -> persist transcript, summary, action items, calendar candidates
  -> 앱에서 회의 상세 조회
  -> 발화 클릭 재생, 요약 수정, 내보내기, Slack 공유
```

## 공통 상태값

Job 상태값은 API, DB, UI에서 동일한 문자열을 사용한다.

| 상태 | 의미 |
| --- | --- |
| `uploaded` | 원본 파일이 저장되고 job이 생성됨 |
| `normalizing_audio` | ASR 입력용 오디오 변환 중 |
| `transcribing` | 전사 및 화자/타임스탬프 추출 중 |
| `summarizing` | 요약, 결정사항, 할 일, 일정 후보 생성 중 |
| `ready_for_review` | 사용자가 검토할 수 있는 상태 |
| `failed` | 처리 실패, `error_code`와 `error_message` 확인 필요 |

## 다음 구현 순서

1. `local-worker` 골격과 `POST /v1/jobs`, `GET /v1/jobs/{job_id}`를 만든다.
2. 로컬 파일 저장소와 `jobs`, `meetings`, `recording_files` 저장을 연결한다.
3. 오디오 정규화와 ASR Provider stub을 먼저 붙이고, 실제 VibeVoice-ASR 호출은 교체 가능한 구현체로 추가한다.
4. 전사 segment 저장 후 웹 UI에서 발화 클릭 재생을 구현한다.
5. 요약 Provider와 요약 편집 저장을 붙인다.
6. Markdown/TXT export와 Slack Webhook 공유를 붙인다.
