# 기능 구현 문서: 요약 검토 및 일정 후보

## 목표

Mac 로컬 LLM Provider가 전사 segment를 입력받아 회의 제목, 전체 요약, 결정사항, 할 일, 일정 후보를 구조화된 JSON으로 생성한다. 사용자는 AI 결과를 검토하고 수정한 뒤 최종 요약본으로 저장한다.

## 처리 파이프라인

```text
transcript_segments saved
  -> summarizing
  -> summary draft created
  -> ready_for_review
```

## 요약 입력

요약 Worker는 segment를 다음 규칙으로 입력한다.

- `corrected_text`가 있으면 원본 `text` 대신 사용한다.
- 표시 화자명은 `speaker_name`이 있으면 우선 사용한다.
- 너무 긴 회의는 timestamp 순서대로 chunk를 나누고, chunk 요약 후 최종 요약을 만든다.
- 일정 후보 추출을 위해 날짜, 시간, 참석자, 액션 동사를 보존한다.

## Summary JSON 스키마

```json
{
  "title": "제품 회의 요약",
  "summary": "이번 회의에서는 MVP 범위와 배포 일정을 논의했다.",
  "decisions": [
    {
      "text": "MVP는 녹음 완료 후 일괄 전사 방식으로 진행한다.",
      "source_segment_ids": ["seg_001", "seg_004"]
    }
  ],
  "action_items": [
    {
      "owner": "홍길동",
      "task": "Mac 로컬 Worker 프로토타입 구성",
      "due_date": "2026-07-22",
      "source_segment_ids": ["seg_012"],
      "confidence": 0.82
    }
  ],
  "calendar_candidates": [
    {
      "title": "MVP 진행 상황 점검",
      "start_at": "2026-07-22T10:00:00+09:00",
      "end_at": "2026-07-22T10:30:00+09:00",
      "attendees": ["team@example.com"],
      "source_segment_ids": ["seg_031", "seg_032"],
      "confidence": 0.76
    }
  ]
}
```

## 검토 UI

회의 상세에는 `전사`, `요약`, `할 일`, `일정 후보` 탭을 둔다.

- 요약 본문은 사용자가 직접 수정할 수 있다.
- 결정사항은 항목별 추가, 수정, 삭제가 가능하다.
- 할 일은 담당자, 작업, 마감일을 수정할 수 있다.
- 일정 후보는 제목, 시작/종료 시간, 참석자, 근거 발화를 표시한다.
- 사용자가 저장하면 새 `summary_versions` 레코드를 만든다.

## 버전 정책

- AI가 만든 최초 결과는 `version = 1`, `source = ai`로 저장한다.
- 사용자가 수정하면 `version = 2`, `source = user`로 저장한다.
- 이후 재생성은 현재 전사 기준 새 draft로 저장하되, 기존 사용자 수정본을 덮어쓰지 않는다.
- 공유와 내보내기는 기본적으로 최신 사용자 승인 버전을 사용한다.

## 일정 후보 승인

MVP에서는 일정 후보를 자동 등록하지 않는다.

1. 사용자가 일정 후보를 검토한다.
2. 필요하면 제목, 시간, 참석자를 수정한다.
3. 사용자가 등록 버튼을 누른다.
4. Web은 Google Calendar 또는 Outlook Calendar 생성 링크를 연다.
5. iOS/Android 네이티브 앱에서는 각각 EventKit, Calendar Intent로 사용자 확인 화면을 연다.

## LLM 실패 대응

- JSON parse 실패 시 한 번 재시도한다.
- 재시도 후에도 실패하면 원문 요약 텍스트를 `summary_raw_output`에 저장한다.
- UI에는 "요약 생성 실패" 상태와 재시도 버튼을 표시한다.
- 전사는 정상 표시되어야 한다.

## 완료 조건

- 전사 완료 후 요약 job이 실행된다.
- 요약, 결정사항, 할 일, 일정 후보가 구조화된 JSON으로 저장된다.
- 사용자가 요약과 각 항목을 수정할 수 있다.
- 수정본이 별도 버전으로 저장된다.
- 일정 후보는 근거 발화와 신뢰도를 함께 표시한다.
