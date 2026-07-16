# 자체 회의 녹음 앱 구현 가능성 및 설계안

작성일: 2026-07-15

실제 구현 착수용으로 분할한 문서 세트는 `docs/README.md`에서 확인한다.

## 1. 결론

해당 요구사항은 구현 가능하다. 다만 MVP 단계에서는 스마트폰 안에서 VibeVoice-ASR 또는 로컬 LLM을 직접 실행하지 않고, 스마트폰/노트북은 녹음과 업로드, 재생, 편집 UI를 담당하며, AI 처리는 사용자의 Mac에서 먼저 실행하는 구조가 가장 현실적이다.

초기 구조는 다음과 같이 잡는다.

```text
iOS / Android / Web 녹음 클라이언트
        ↓
Mac 로컬 API 또는 파일 업로드 폴더
        ↓
Mac 로컬 Worker
  - VibeVoice-ASR 전사
  - 화자 구분
  - 타임스탬프 생성
  - 로컬 LLM 요약 및 일정 추출
        ↓
Supabase / 로컬 DB / 파일 저장
        ↓
앱에서 회의록 조회, 문장 클릭 재생, 요약 수정, Slack 공유
```

서버가 준비된 이후에는 Mac 로컬 Worker를 서버 Worker로 교체한다. 앱과 백엔드는 동일한 API 계약을 유지하고, 실행 위치만 `local_mac`에서 `server_gpu`로 바꾸는 방식으로 확장한다.

## 2. 핵심 요구사항 반영

### 2.1 녹음 장치

녹음은 다음 장치를 대상으로 한다.

- iPhone 내장 마이크
- Galaxy 등 Android 스마트폰 내장 마이크
- MacBook, Windows 노트북 내장 마이크
- AirPods, Galaxy Buds 등 블루투스 이어폰 마이크

초기 MVP에서는 iOS/Android 앱 또는 모바일 웹에서 녹음한 파일을 Mac으로 업로드하는 방식으로 시작한다. 노트북 마이크 녹음은 웹 앱 또는 데스크톱 앱에서 처리할 수 있다.

권장 녹음 포맷은 다음과 같다.

- 모바일 저장 원본: `m4a` 또는 `aac`
- ASR 처리용 변환본: `wav`, 16kHz 또는 모델 권장 샘플레이트
- 사용자 내보내기: `mp3`, `m4a`, `wav`

### 2.2 화자 구분 회의록

VibeVoice-ASR은 장문 음성에 대해 화자, 타임스탬프, 발화 내용을 구조화해서 생성하는 모델이므로 회의록 앱의 기본 요구사항과 잘 맞는다.

회의록 데이터는 문장 또는 발화 단위로 저장한다.

```json
{
  "meeting_id": "meeting_001",
  "segments": [
    {
      "id": "seg_001",
      "speaker": "Speaker 1",
      "start_ms": 12000,
      "end_ms": 18500,
      "text": "이번 분기 일정부터 확인하겠습니다."
    }
  ]
}
```

앱에서는 사용자가 특정 발화 텍스트를 클릭하면 `start_ms` 위치로 오디오 플레이어를 이동시켜 해당 음성을 바로 재생한다.

### 2.3 저장 구조

저장은 원본 보존을 기본 원칙으로 한다.

- 원본 음성 파일은 수정하지 않는다.
- 전사 결과는 별도 테이블로 저장한다.
- 요약본은 사용자가 수정할 수 있도록 별도 버전으로 저장한다.
- 수정된 요약본이 원본 전사나 원본 음성을 덮어쓰지 않도록 한다.

권장 저장 구조는 다음과 같다.

```text
Storage
  /users/{user_id}/meetings/{meeting_id}/original.m4a
  /users/{user_id}/meetings/{meeting_id}/normalized.wav
  /users/{user_id}/meetings/{meeting_id}/exports/summary.md
  /users/{user_id}/meetings/{meeting_id}/exports/transcript.txt

Postgres
  users
  meetings
  recording_files
  transcript_segments
  summaries
  action_items
  calendar_candidates
  share_logs

Vector DB
  transcript segment embedding
  summary embedding
  action item embedding
```

Supabase를 사용할 경우 음성 파일과 내보내기 파일은 Supabase Storage에 저장하고, 회의 메타데이터와 발화 단위 전사 결과는 Postgres에 저장한다. 검색과 RAG를 위해 transcript segment 단위로 embedding을 만들어 pgvector 또는 Supabase Vector Buckets에 저장한다.

## 3. Mac 로컬 처리 우선 설계

### 3.1 초기 MVP 처리 흐름

서버가 없는 초기 단계에서는 사용자의 Mac을 AI 처리 머신으로 사용한다.

```text
1. 스마트폰 또는 노트북에서 회의 녹음
2. 녹음 파일을 Mac 로컬 API 또는 업로드 폴더로 전달
3. Mac에서 VibeVoice-ASR 실행
4. 전사 결과를 speaker / timestamp / text 구조로 저장
5. Mac에서 로컬 LLM 실행
6. 요약, 결정사항, 할 일, 일정 후보 추출
7. 앱 또는 웹 대시보드에서 사용자가 요약본 검토 및 수정
8. Slack 공유 또는 캘린더 등록
```

### 3.2 Mac 로컬 Worker 구성

Mac에는 다음 컴포넌트를 둔다.

```text
local-worker/
  api/
    POST /jobs
    GET /jobs/{job_id}
    GET /meetings/{meeting_id}
  workers/
    asr_worker
    summary_worker
    export_worker
    slack_worker
  providers/
    transcription_provider
    llm_provider
    storage_provider
```

처리 위치를 바꾸기 쉽도록 provider 인터페이스를 분리한다.

```text
TranscriptionProvider
  - transcribe(audio_path, hotwords) -> TranscriptResult

SummaryProvider
  - summarize(transcript) -> SummaryResult

StorageProvider
  - save_audio(file)
  - save_transcript(segments)
  - save_summary(summary)
```

초기에는 다음과 같이 연결한다.

```text
TranscriptionProvider = LocalVibeVoiceProvider
SummaryProvider = LocalGemmaProvider
StorageProvider = SupabaseStorageProvider 또는 LocalFileStorageProvider
```

서버 전환 후에는 다음과 같이 바꾼다.

```text
TranscriptionProvider = ServerVibeVoiceProvider
SummaryProvider = ServerLLMProvider
StorageProvider = SupabaseStorageProvider
```

앱 입장에서는 API가 동일하므로 처리 위치 변경에 영향을 적게 받는다.

### 3.3 Mac에서 실행할 LLM

요약 및 일정 추출은 로컬 LLM으로 처리한다. 후보 모델은 Gemma 4 계열, 또는 Mac에서 실행 가능한 양자화 모델을 우선 검토한다.

요약 결과는 자유 문장만 만들지 않고 구조화된 JSON으로 생성한다.

```json
{
  "title": "제품 회의 요약",
  "summary": "이번 회의에서는 MVP 범위와 배포 일정을 논의했다.",
  "decisions": [
    "MVP는 녹음 완료 후 일괄 전사 방식으로 진행한다."
  ],
  "action_items": [
    {
      "owner": "홍길동",
      "task": "Mac 로컬 Worker 프로토타입 구성",
      "due_date": "2026-07-22"
    }
  ],
  "calendar_candidates": [
    {
      "title": "MVP 진행 상황 점검",
      "start_at": "2026-07-22T10:00:00+09:00",
      "end_at": "2026-07-22T10:30:00+09:00",
      "attendees": ["team@example.com"],
      "confidence": 0.82
    }
  ]
}
```

사용자는 이 요약본과 일정 후보만 수정한다. 원본 음성과 원본 전사 결과는 보존한다.

## 4. 서버 전환 설계

서버가 준비되면 Mac 로컬 Worker에서 하던 작업을 서버 Worker로 이전한다.

```text
Before
  App -> Mac Local API -> Local VibeVoice-ASR -> Local LLM

After
  App -> Backend API -> Queue -> GPU ASR Worker -> LLM Worker
```

서버 전환 시 유지해야 할 원칙은 다음과 같다.

- 앱의 업로드 API는 유지한다.
- job 상태값은 동일하게 유지한다.
- transcript segment 스키마는 변경하지 않는다.
- summary JSON 스키마는 변경하지 않는다.
- provider 구현체만 교체한다.

권장 job 상태값은 다음과 같다.

```text
uploaded
normalizing_audio
transcribing
summarizing
ready_for_review
failed
```

## 5. 앱 기능 설계

### 5.1 회의 목록

- 회의 제목
- 녹음 날짜
- 녹음 길이
- 처리 상태
- 요약 여부
- 공유 여부

### 5.2 회의 상세

- 상단 오디오 플레이어
- 화자별 발화 목록
- 발화 클릭 시 해당 구간 재생
- 화자명 수정
- 검색
- 중요 발화 북마크

### 5.3 요약 편집

- 원본 전사 보기
- AI 요약 보기
- 사용자가 요약본 수정
- 결정사항 수정
- 할 일 수정
- 일정 후보 수정
- 수정 이력 저장

### 5.4 내보내기

지원할 내보내기 형식은 다음과 같다.

- 음성: `mp3`, `m4a`, `wav`
- 텍스트: `txt`, `md`, `docx`
- 선택 구간 음성 클립
- 전체 회의록
- 요약본만 내보내기

## 6. Slack 공유

Slack 공유는 두 단계로 나누어 구현한다.

### 6.1 MVP

Incoming Webhook을 사용해 지정된 채널로 요약과 일정 후보를 전송한다.

공유 예시는 다음과 같다.

```text
[회의 요약] 제품 MVP 회의

요약:
- MVP는 녹음 완료 후 일괄 전사 방식으로 진행
- Mac 로컬 Worker로 초기 처리
- 서버 준비 후 Worker 이전

결정사항:
- 원본 음성은 보존
- 요약본만 사용자 수정 가능

일정 후보:
- 2026-07-22 10:00 MVP 진행 상황 점검
```

### 6.2 고도화

Slack OAuth와 Web API를 사용한다.

- 사용자별 Slack 워크스페이스 연결
- 채널 선택
- 특정 동료, 상사, 후배에게 DM 공유
- 회의록 링크 공유
- 일정 후보 승인 버튼
- Slack thread에 후속 논의 기록

## 7. 캘린더 연동

일정 후보는 LLM이 자동 등록하지 않고 사용자의 검토 후 등록한다.

초기에는 다음 방식이 안전하다.

- Android: Calendar Intent로 사용자가 확인 후 등록
- iOS: EventKit 기반 등록
- Web: Google Calendar / Outlook Calendar 링크 또는 OAuth 연동

일정 후보에는 반드시 신뢰도와 근거 발화를 함께 표시한다.

```json
{
  "title": "계약서 검토 회의",
  "start_at": "2026-07-24T14:00:00+09:00",
  "source_segment_ids": ["seg_031", "seg_032"],
  "confidence": 0.76
}
```

## 8. 보안 및 권한

회의 녹음 앱은 개인정보와 회사 기밀을 다룰 가능성이 높으므로 다음 항목을 필수로 설계한다.

- 녹음 전 동의 안내
- 사용자별 접근 권한
- 조직별 데이터 분리
- 원본 음성 암호화 저장
- 전송 구간 HTTPS
- 다운로드 권한 제한
- Slack 공유 로그 저장
- 요약본 수정 이력 저장
- 원본 삭제 정책과 보존 기간 설정

## 9. MVP 범위

1차 MVP는 다음 범위로 잡는다.

- 모바일 또는 웹에서 녹음 파일 생성
- Mac 로컬 업로드
- Mac에서 VibeVoice-ASR 전사 실행
- 화자, 타임스탬프, 텍스트 저장
- 문장 클릭 시 해당 음성 재생
- Mac 로컬 LLM으로 요약 및 일정 후보 추출
- 요약본 사용자 수정
- Markdown 또는 TXT 내보내기
- Slack Webhook 공유

2차 MVP는 다음 범위로 확장한다.

- iOS/Android 네이티브 앱
- Supabase Auth 연동
- Supabase Storage 및 Postgres 저장
- Vector 검색
- 캘린더 등록
- Slack OAuth
- 서버 Worker 이전

## 10. 주요 리스크

- VibeVoice-ASR의 한국어 회의 음성 정확도 검증 필요
- 여러 사람이 동시에 말하는 회의에서 화자 구분 오류 가능
- Mac 로컬에서 9B급 ASR 모델 실행 시 성능 및 메모리 제약 가능
- 긴 회의 녹음 처리 시간 증가
- 회사 보안 정책에 따른 외부 저장소 사용 제한 가능
- Slack 공유 시 민감정보 유출 방지 필요
- 캘린더 자동 등록은 사용자 승인 흐름이 필요

## 11. 권장 다음 단계

1. 10분 내외 한국어 회의 샘플 3개를 준비한다.
2. Mac에서 VibeVoice-ASR 처리 가능 여부와 처리 시간을 측정한다.
3. transcript segment JSON 스키마를 확정한다.
4. 로컬 LLM으로 요약 JSON 품질을 테스트한다.
5. 간단한 웹 UI로 오디오 플레이어와 발화 클릭 재생을 구현한다.
6. Slack Webhook으로 요약본 공유를 검증한다.
7. 이후 모바일 앱과 서버 Worker로 확장한다.

## 12. 참고 링크

- VibeVoice-ASR Hugging Face: https://huggingface.co/microsoft/VibeVoice-ASR
- Microsoft VibeVoice GitHub: https://github.com/microsoft/VibeVoice
- Android MediaRecorder: https://developer.android.com/media/platform/mediarecorder
- Android Calendar Provider: https://developer.android.com/identity/providers/calendar-provider
- Supabase Storage: https://supabase.com/docs/guides/storage
- Supabase Vector columns: https://supabase.com/docs/guides/ai/vector-columns
- Slack Incoming Webhooks: https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/
- Slack chat.postMessage: https://docs.slack.dev/reference/methods/chat.postMessage/
- Google Gemma docs: https://ai.google.dev/gemma/docs
