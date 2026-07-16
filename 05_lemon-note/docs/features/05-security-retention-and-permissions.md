# 기능 구현 문서: 보안, 권한, 보존 정책

## 목표

회의 녹음 앱은 개인정보, 회사 기밀, 음성 생체정보를 다룰 수 있으므로 MVP부터 동의, 접근 제어, 원본 보존, 삭제 정책, 공유 로그를 구현한다.

## 녹음 동의

녹음 시작 전 사용자에게 다음 내용을 확인시킨다.

- 회의 참석자의 동의를 받고 녹음해야 한다.
- 녹음 파일은 전사와 요약 생성을 위해 저장된다.
- Slack 공유나 내보내기는 사용자의 명시적 실행으로만 수행된다.

MVP에서는 체크박스 기반 동의 확인을 저장한다.

```text
recording_consent_confirmed = true
recording_consent_confirmed_at = 2026-07-15T10:00:00+09:00
```

## 접근 권한

MVP의 기본 권한 모델은 단순하게 시작한다.

- 회의를 생성한 사용자는 owner이다.
- owner만 회의 상세, 원본 음성, 전사, 요약에 접근한다.
- 공유는 Slack 메시지 또는 export 파일 단위로 별도 기록한다.
- 조직 단위 권한은 2차 MVP에서 `organizations`와 membership으로 확장한다.

## 데이터 분리

Storage 경로는 사용자와 회의 단위로 분리한다.

```text
/users/{user_id}/meetings/{meeting_id}/original.{ext}
/users/{user_id}/meetings/{meeting_id}/normalized.wav
/users/{user_id}/meetings/{meeting_id}/exports/{export_id}.{ext}
```

DB 레코드는 모든 주요 테이블에 `user_id` 또는 `meeting_id`를 포함해 접근 범위를 추적한다.

## 암호화

- 전송 구간은 HTTPS를 사용한다.
- Supabase Storage 사용 시 비공개 bucket을 사용한다.
- 다운로드는 signed URL 또는 인증된 streaming endpoint를 사용한다.
- 로컬 MVP 파일 저장 시 OS 계정 권한 밖으로 노출하지 않는다.
- 별도 키 관리 기반 파일 암호화는 2차 단계에서 검토한다.

## 감사 로그

다음 이벤트는 감사 로그 또는 전용 로그 테이블에 남긴다.

- 회의 생성
- 원본 파일 업로드
- 전사 완료
- 요약 생성
- 요약 수정
- export 생성
- Slack 공유
- 원본 또는 회의 삭제

## 보존 및 삭제

MVP에서는 사용자가 회의를 직접 삭제할 수 있어야 한다.

삭제 정책:

1. `meetings.deleted_at`을 먼저 기록한다.
2. UI 목록에서 제외한다.
3. 원본 음성, normalized 파일, exports 파일을 삭제 queue에 넣는다.
4. 삭제 성공 여부를 감사 로그에 남긴다.
5. 전사와 요약은 기본적으로 함께 soft delete한다.

조직용 제품으로 확장할 때는 보존 기간, legal hold, 관리자 삭제 정책을 별도로 둔다.

## 민감정보 처리

MVP에서는 자동 탐지보다 사용자 확인을 우선한다.

- Slack 공유 전 미리보기 필수
- 외부 공유 시 경고 표시
- export 파일 다운로드 이력 저장
- 2차 단계에서 주민등록번호, 전화번호, 이메일, 계좌번호 등 패턴 기반 마스킹 추가

## 완료 조건

- 녹음 시작 전 동의 확인이 저장된다.
- owner만 회의 데이터에 접근한다.
- 원본 파일과 export 파일이 사용자/회의 경로로 분리된다.
- Slack 공유와 export 생성 이력이 남는다.
- 회의 삭제 시 DB soft delete와 파일 삭제 작업이 실행된다.
