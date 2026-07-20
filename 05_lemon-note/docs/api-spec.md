# API 스펙

## 기본 원칙

- Base URL: `http://localhost:8710/v1`
- 응답은 JSON을 기본으로 한다.
- 파일 업로드는 `multipart/form-data`를 사용한다.
- MVP 로컬 모드에서는 `Authorization: Bearer {LOCAL_API_TOKEN}`을 사용한다.
- 서버 이전 후에도 endpoint, 상태값, 주요 response schema를 유지한다.

## 공통 오류 응답

```json
{
  "error": {
    "code": "unsupported_media_type",
    "message": "지원하지 않는 녹음 파일입니다.",
    "details": {}
  }
}
```

## POST /jobs

녹음 파일을 업로드하고 처리 job을 생성한다.

Request: `multipart/form-data`

| 필드 | 타입 | 필수 | 설명 |
| --- | --- | --- | --- |
| `audio_file` | file | 예 | 원본 녹음 파일 |
| `title` | string | 아니오 | 회의 제목 |
| `recorded_at` | string | 예 | ISO 8601 |
| `duration_ms` | number | 아니오 | 클라이언트 측정 길이 |
| `source_device` | string | 아니오 | 녹음 장치 |
| `language` | string | 아니오 | 기본값 `ko` |
| `hotwords` | string[] | 아니오 | ASR 힌트 |

Response `201`

```json
{
  "job_id": "job_01",
  "meeting_id": "meeting_01",
  "status": "uploaded",
  "created_at": "2026-07-15T10:00:00+09:00"
}
```

## GET /jobs/{job_id}

처리 상태를 조회한다.

Response `200`

```json
{
  "job_id": "job_01",
  "meeting_id": "meeting_01",
  "status": "transcribing",
  "progress": 0.45,
  "error_code": null,
  "error_message": null,
  "updated_at": "2026-07-15T10:02:00+09:00"
}
```

## GET /meetings

회의 목록을 조회한다.

Query:

| 이름 | 설명 |
| --- | --- |
| `status` | job 또는 meeting 상태 필터 |
| `q` | 제목/전사 텍스트 검색 |
| `limit` | 기본 20 |
| `cursor` | 다음 페이지 cursor |

Response `200`

```json
{
  "items": [
    {
      "meeting_id": "meeting_01",
      "title": "제품 MVP 회의",
      "recorded_at": "2026-07-15T10:00:00+09:00",
      "duration_ms": 1830000,
      "status": "ready_for_review",
      "has_summary": true,
      "shared_count": 1
    }
  ],
  "next_cursor": null
}
```

## GET /meetings/{meeting_id}

회의 상세를 조회한다.

Response `200`

```json
{
  "meeting_id": "meeting_01",
  "title": "제품 MVP 회의",
  "recorded_at": "2026-07-15T10:00:00+09:00",
  "duration_ms": 1830000,
  "status": "ready_for_review",
  "audio": {
    "recording_file_id": "file_01",
    "stream_url": "/v1/recording-files/file_01/stream"
  },
  "summary_version_id": "summary_02"
}
```

## PATCH /meetings/{meeting_id}

회의 제목 등 메타데이터를 수정한다.

Request:

```json
{
  "title": "제품 MVP 킥오프"
}
```

## GET /meetings/{meeting_id}/segments

전사 segment 목록을 조회한다.

Response `200`

```json
{
  "items": [
    {
      "segment_id": "seg_001",
      "speaker_label": "Speaker 1",
      "speaker_name": "김민수",
      "start_ms": 12000,
      "end_ms": 18500,
      "text": "이번 분기 일정부터 확인하겠습니다.",
      "corrected_text": null,
      "bookmarked": false
    }
  ]
}
```

## PATCH /meetings/{meeting_id}/segments/{segment_id}

전사 텍스트 보정 또는 북마크를 저장한다.

Request:

```json
{
  "corrected_text": "이번 분기 일정을 먼저 확인하겠습니다.",
  "bookmarked": true
}
```

## PATCH /meetings/{meeting_id}/speakers/{speaker_label}

회의 안의 화자 표시명을 수정한다.

Request:

```json
{
  "speaker_name": "김민수"
}
```

## GET /meetings/{meeting_id}/summary

최신 요약 버전을 조회한다.

Response `200`

```json
{
  "summary_version_id": "summary_02",
  "version": 2,
  "source": "user",
  "title": "제품 회의 요약",
  "summary": "MVP 범위와 배포 일정을 논의했다.",
  "decisions": [],
  "action_items": [],
  "calendar_candidates": []
}
```

## PATCH /meetings/{meeting_id}/summary

사용자 수정 요약 버전을 저장한다.

Request:

```json
{
  "title": "제품 회의 요약",
  "summary": "MVP 범위와 배포 일정을 논의했다.",
  "decisions": [
    {
      "text": "MVP는 녹음 완료 후 일괄 전사 방식으로 진행한다.",
      "source_segment_ids": ["seg_001"]
    }
  ],
  "action_items": [],
  "calendar_candidates": []
}
```

Response `200`

```json
{
  "summary_version_id": "summary_03",
  "version": 3,
  "source": "user"
}
```

## POST /meetings/{meeting_id}/exports

회의록 파일을 생성한다.

Request:

```json
{
  "format": "md",
  "include_transcript": true,
  "summary_version_id": "summary_03"
}
```

Response `201`

```json
{
  "export_id": "export_01",
  "format": "md",
  "status": "ready",
  "download_url": "/v1/exports/export_01/download"
}
```

## POST /meetings/{meeting_id}/share/slack

Slack Incoming Webhook으로 회의 요약을 공유한다.

Request:

```json
{
  "summary_version_id": "summary_03",
  "channel_label": "#product",
  "message_override": null
}
```

Response `200`

```json
{
  "share_log_id": "share_01",
  "provider": "slack_webhook",
  "status": "sent",
  "sent_at": "2026-07-15T10:30:00+09:00"
}
```

## GET /recording-files/{recording_file_id}/stream

인증된 사용자에게 음성 스트림을 제공한다. Range request를 지원해야 발화 클릭 재생과 seek가 안정적으로 동작한다.

## POST /meetings/{meeting_id}/retry

실패한 job을 재시도한다.

Request:

```json
{
  "from_stage": "transcribing"
}
```
