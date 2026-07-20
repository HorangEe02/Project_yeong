# MVP 작업 단위

## MVP 정의

1차 MVP는 사용자가 웹 또는 모바일 웹에서 회의를 녹음하거나 파일을 업로드하고, Mac 로컬 Worker가 전사와 요약을 처리한 뒤, 앱에서 회의록을 검토하고 Markdown/TXT 내보내기와 Slack Webhook 공유까지 수행하는 범위이다.

## 에픽 0: 프로젝트 골격

| 작업 | 산출물 | 완료 조건 |
| --- | --- | --- |
| 저장소 구조 생성 | `apps/web`, `local-worker`, `docs` | 로컬 실행 README와 환경변수 예시 존재 |
| 공통 타입 정의 | `Meeting`, `Job`, `TranscriptSegment`, `SummaryVersion` | API 응답과 UI 타입이 동일한 필드명 사용 |
| 로컬 개발 설정 | `.env.example`, 실행 스크립트 | 웹과 Worker가 로컬에서 동시에 실행됨 |

## 에픽 1: 녹음 및 업로드

| 작업 | 우선순위 | 완료 조건 |
| --- | --- | --- |
| 웹 녹음 UI | P0 | 시작, 일시정지, 재개, 종료가 가능함 |
| 파일 업로드 fallback | P0 | 브라우저 녹음 미지원 시 파일 업로드 가능 |
| `POST /v1/jobs` | P0 | 원본 파일 저장 후 job 생성 |
| job 상태 조회 | P0 | `GET /v1/jobs/{job_id}`가 상태와 오류를 반환 |
| 업로드 검증 | P1 | MIME, 크기, 길이 오류를 구분 |

## 에픽 2: 오디오 정규화 및 전사

| 작업 | 우선순위 | 완료 조건 |
| --- | --- | --- |
| `ffmpeg` 정규화 | P0 | `normalized.wav` 생성 |
| ASR Provider 인터페이스 | P0 | stub과 실제 구현체를 교체 가능 |
| VibeVoice-ASR 호출 | P0 | 샘플 음성에서 segment JSON 생성 |
| segment 저장 | P0 | speaker, start_ms, end_ms, text 저장 |
| 전사 실패 처리 | P1 | 실패 상태와 재시도 가능 |

## 에픽 3: 회의 상세 및 발화 재생

| 작업 | 우선순위 | 완료 조건 |
| --- | --- | --- |
| 회의 목록 | P0 | 제목, 날짜, 길이, 상태 표시 |
| 회의 상세 | P0 | 오디오 플레이어와 segment 목록 표시 |
| 발화 클릭 재생 | P0 | 클릭한 segment의 `start_ms`부터 재생 |
| 화자명 수정 | P1 | 같은 speaker label 전체에 반영 |
| 전사 텍스트 보정 | P1 | 원본 보존, 수정본 별도 저장 |
| 검색/북마크 | P2 | 텍스트 검색과 중요 발화 표시 |

## 에픽 4: 요약 및 검토

| 작업 | 우선순위 | 완료 조건 |
| --- | --- | --- |
| Summary Provider 인터페이스 | P0 | 로컬 LLM과 stub을 교체 가능 |
| 요약 JSON 생성 | P0 | summary, decisions, action_items, calendar_candidates 생성 |
| 요약 편집 UI | P0 | 사용자가 요약과 항목을 수정 가능 |
| 요약 버전 저장 | P0 | AI draft와 사용자 수정본이 별도 버전 |
| 일정 후보 표시 | P1 | 신뢰도와 근거 발화를 함께 표시 |

## 에픽 5: 내보내기 및 Slack 공유

| 작업 | 우선순위 | 완료 조건 |
| --- | --- | --- |
| Markdown export | P0 | 최신 승인 요약과 전사 포함 |
| TXT export | P1 | plain text 파일 생성 |
| Slack Webhook 공유 | P0 | 미리보기 후 지정 채널로 전송 |
| 공유 로그 | P0 | 성공/실패, 요청 시각, 응답 상태 저장 |
| 선택 구간 음성 클립 | P2 | 2차 MVP로 이월 |

## 에픽 6: 보안 및 운영

| 작업 | 우선순위 | 완료 조건 |
| --- | --- | --- |
| 녹음 동의 확인 | P0 | 동의 여부와 시각 저장 |
| 비공개 파일 저장 | P0 | 원본 음성 URL이 공개 노출되지 않음 |
| 회의 삭제 | P1 | soft delete와 파일 삭제 queue 처리 |
| 감사 로그 | P1 | 생성, 수정, 공유, 삭제 이벤트 기록 |
| 샘플 데이터/테스트 | P1 | 10분 내외 한국어 샘플 3개 처리 결과 기록 |

## MVP 검증 시나리오

1. 모바일 웹에서 3분 이상 녹음한다.
2. 녹음 파일을 업로드한다.
3. job 상태가 `uploaded`, `normalizing_audio`, `transcribing`, `summarizing`, `ready_for_review` 순서로 진행된다.
4. 회의 상세에서 segment가 표시된다.
5. 특정 발화를 클릭하면 해당 음성이 재생된다.
6. 요약을 수정하고 저장한다.
7. Markdown 파일을 내보낸다.
8. Slack Webhook으로 요약을 공유한다.
9. 공유 로그와 export 이력이 DB에 남는다.
