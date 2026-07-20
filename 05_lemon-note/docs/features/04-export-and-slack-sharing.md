# 기능 구현 문서: 내보내기 및 Slack 공유

## 목표

사용자가 검토한 회의록을 Markdown 또는 TXT로 내보내고, MVP에서는 Slack Incoming Webhook으로 지정 채널에 요약본을 공유한다. 원본 음성 전체 또는 선택 구간 음성 클립 내보내기는 2차 단계로 확장한다.

## 내보내기 범위

| 형식 | MVP | 설명 |
| --- | --- | --- |
| `md` | 예 | 요약, 결정사항, 할 일, 일정 후보, 전체 전사 |
| `txt` | 예 | 메신저나 이메일 붙여넣기용 plain text |
| `docx` | 아니오 | 2차 단계에서 템플릿 기반 생성 |
| `mp3`, `m4a`, `wav` | 아니오 | 2차 단계에서 원본 또는 선택 구간 클립 생성 |

## Markdown 템플릿

```md
# {meeting_title}

- 녹음 일시: {recorded_at}
- 회의 길이: {duration}
- 처리 상태: {status}

## 요약

{summary}

## 결정사항

- {decision}

## 할 일

| 담당자 | 작업 | 마감일 |
| --- | --- | --- |
| {owner} | {task} | {due_date} |

## 일정 후보

| 제목 | 시작 | 종료 | 신뢰도 |
| --- | --- | --- | --- |
| {title} | {start_at} | {end_at} | {confidence} |

## 전체 전사

[{start} - {end}] {speaker}: {text}
```

## Export API 흐름

1. 사용자가 내보내기 형식을 선택한다.
2. 클라이언트가 `POST /v1/meetings/{meeting_id}/exports`를 호출한다.
3. Worker가 최신 승인 요약 버전과 segment를 읽는다.
4. 파일을 생성해 Storage exports 경로에 저장한다.
5. `exports` 레코드를 만들고 다운로드 URL을 반환한다.

## Slack MVP 공유

MVP는 Incoming Webhook URL을 환경변수 또는 사용자 설정에 저장한다.

공유 대상은 최신 승인 요약 버전이다. 공유 전 UI에서 미리보기를 보여주고 사용자가 전송을 눌러야 한다.

Slack 메시지 구성:

```text
[회의 요약] {meeting_title}

요약:
- {summary bullet}

결정사항:
- {decision}

할 일:
- {owner}: {task} ({due_date})

일정 후보:
- {start_at} {title}
```

## Slack 보안 기준

- Webhook URL은 클라이언트에 노출하지 않는다.
- 공유 전 사용자가 채널과 내용을 확인한다.
- 공유 성공/실패 결과를 `share_logs`에 저장한다.
- 민감정보 자동 마스킹은 2차 단계로 두되, MVP에서도 공유 전 확인 화면은 필수이다.

## 실패 처리

| 오류 | 처리 |
| --- | --- |
| 내보내기 대상 요약 없음 | 전사만 내보내기 또는 요약 생성 요청 |
| 파일 생성 실패 | `exports.status = failed` 저장 후 재시도 버튼 표시 |
| Slack Webhook 실패 | HTTP 응답 코드와 응답 본문 일부를 `share_logs`에 저장 |
| Webhook 미설정 | 설정 화면으로 안내 |

## 완료 조건

- 최신 요약과 전사를 Markdown/TXT로 내보낼 수 있다.
- 내보낸 파일 경로와 생성 이력이 저장된다.
- Slack 공유 전 미리보기를 표시한다.
- Slack Webhook 전송 성공/실패가 기록된다.
- 공유된 내용이 원본 전사나 요약 버전을 변경하지 않는다.
