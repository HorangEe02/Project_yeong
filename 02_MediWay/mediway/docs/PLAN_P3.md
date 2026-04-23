# Phase 3 구현 계획 — 고수요 편의 기능 (v2 조정판)

> **상태**: 계획 (2026-04-23)
> **브랜치**: `mediway/plusultra/p3` (착수 시 `mediway/develop`에서 분기)
> **타깃 병합지**: `mediway/develop`
> **기반**: P1 + P2 완료 (`mediway/develop @ 34ca2b9`)
> **예상 기간**: 3~4주 (1인 풀타임)
> **참조**: `GUIDE_v2/plusultra_v2.md §Phase 3` + `GUIDE_v2/PlusUltra#3.md` (v2 덮어쓰기 블록)

---

## 0. 목표

P2 대시보드 위에 **고수요 편의 기능**을 얹어 "파일럿 병원 계약 가능" 수준으로 완성. 시장 경쟁 평균을 따라잡되 **MediWay의 MOAT(가족 대리·검사결과 무기한)는 P4·P5 유지**.

### 성공의 정의

1. 환자가 접수 후 홈에서 **실시간 대기 순번** 확인 (똑닥 동등)
2. 의료진 "다음 환자 호출" → 환자 Push + 화면 알림 수신
3. **카카오페이**로 진료비 결제 성공 (샌드박스 → 실결제)
4. **대리결제 링크** → 보호자 카카오톡 공유 → 결제 완료 (MOAT 씨앗)
5. **알림톡**으로 예약 확인·결제 영수증 발송 (템플릿 심사 후)
6. **AI 증상 triage**가 홈에서 증상 → 진료과 추천 (v2 신규)
7. 진료 완료 후 **처방전 PDF 다운로드** (약국 QR은 Drop per v2)
8. 주차 할인 **어댑터 인터페이스** 정의 (파일럿별 구현)

---

## 1. 스코프 (v2 반영)

### IN

| 영역 | v2 기준 내용 |
|---|---|
| F1 실시간 대기 순번 | `/wait_queue/{hid}/{dept}/{date}/{number}` + RTDB onValue + FCM Push |
| F6 처방전 (**축소**) | PDF 업로드 + 환자 다운로드만. 약국 QR / 즐겨찾기 Drop (v2 §3.2) |
| F8 카카오페이 | Ready → Approve → Webhook; Functions + Secret Manager |
| F9 대리결제 | JWT 결제 링크 → 카카오톡 공유 → 보호자 웹 결제 |
| F5 알림톡 | 카카오 비즈메시지 + FCM + SMS 3중 fallback |
| F5 FCM Push | 브라우저 Push (기존 SW 재활용) + Android/iOS |
| **F19 AI triage** (신규) | OpenAI/Claude API 호출 → 상위 3개 진료과 추천 + "진단 아님" 고지 |
| 주차 할인 | **어댑터 인터페이스** (`src/services/parking/adapter.ts`) + 파일럿별 구현은 Drop |
| 입원·검진 실내용 | 담당 의료진 카드 · 면회 예약 · 검진 예약 최소 폼 |

### OUT (후속)

- iOS Live Activity (P3 Rich Push로 대체 — Capacitor 래퍼는 P4 후반)
- 검사결과 무기한 (P5 MOAT)
- 가족 대리 (P4 MOAT)
- 디지털 문진 (P5)
- 주차 파일럿별 실 구현 (파일럿 병원 계약 후)

### v2 특이사항

- **F6은 MVP 축소** — v1의 약국 QR·즐겨찾기 제거. 2026 전자처방전 표준 확정 후 재도입.
- **F19 AI triage 신규 도입** — v1 없음. 2025-2026 주요 병원 파일럿 수준 기본 기능.
- Live Activity는 **TIG** (차별화 ❌, 본전)로 관점 이동 (v2 시장 재평가).
- **대리결제를 MOAT 축**으로 영업 메시지화 (MyChart 미지원 격차).

---

## 2. 선행 조건

- [x] P2 merge to develop (`34ca2b9`)
- [x] `features.appointments=true` on demo
- [ ] 카카오 개발자 앱 등록 + 결제·비즈메시지 승인 대기 (영업·계약 병행)
- [ ] AI triage API 벤더 결정 (OpenAI GPT-4o-mini vs Anthropic Claude Haiku vs Gemini)
- [ ] Firebase Secret Manager 활성화 (`KAKAO_*`, `LLM_API_KEY` 저장소)
- [ ] 법무 검토 — PG·알림톡·AI triage "진단 아님" 고지 UI

---

## 3. 작업 순서 — 12 논리 단위 (Commit 단위)

리스크 체크포인트: **C2 (RTDB 규칙 확장)**, **C6 (결제 Functions · Webhook 서명)**, **C9 (알림톡 템플릿 외부 심사)**, **C10 (AI triage 응답 오용 리스크)**.

### Commit 1 — 대기 순번 스키마 + 서비스

- `src/types/wait-queue.ts` — `WaitEntry`, `QueueStatus`
- `src/services/waitQueue.ts` — `enqueue`, `subscribeByPatient`, `subscribeByDept`, `callNext`, `complete`
- RTDB: `/hospitals/{hid}/wait_queue/{dept}/{date}/{number}`
- 단위 테스트

### Commit 2 — RTDB 규칙 확장 (wait_queue)

- 환자는 자기 entry 읽기 · 의료진은 부서 전체 · 타 부서 차단
- `scripts/test-rules.mjs` +4~5 시나리오
- 배포는 C4 이후 일괄

**리스크 ★★** — P1·P2와 동일 게이트 (Emulator → dry-run → deploy)

### Commit 3 — 대기 순번 UI

- `WaitQueueWidget` 실데이터 연동 (P2 placeholder 대체)
- `AppointmentsTab`에 "접수" 버튼 추가 (예약 → queue enqueue)
- 상태 전이: `waiting` → `called` → `in-progress` → `completed`

### Commit 4 — 의료진 콘솔 "다음 환자 호출"

- `src/pages/staff/StaffQueuePage.tsx` — 부서별 대기 리스트 + Call Next 버튼
- 호출 시 `callNext()` → queue status 변경 + FCM push trigger

### Commit 5 — FCM Push 연동

- 기존 `firebase-messaging-sw.js` 재활용
- `src/hooks/useFcmToken.ts` — 토큰 등록·사용자 매핑
- Cloud Function `onQueueCall` — 환자 FCM 전송

### Commit 6 — 처방전 (축소 MVP)

- `src/services/prescription.ts` — PDF 업로드(Storage) + 다운로드 URL
- 의료진 콘솔 "처방전 업로드" UI
- 환자 홈 "처방전 보기" 링크
- 약국 QR 제거 (v2 §3.2)

### Commit 7 — 카카오페이 Cloud Functions

**리스크 ★★★** — 결제 서명/금액 서버 권위 + 멱등성 키 필수

- `functions/src/payment/kakaoPay.ts` — Ready/Approve/Cancel + Webhook HMAC
- Secret Manager: `KAKAO_ADMIN_KEY`, `KAKAO_CID`
- 단위 테스트: mock axios, HMAC 검증 케이스 5+

### Commit 8 — 결제 UI + 이력

- `src/services/payment.ts` — 클라이언트 Ready 호출 + approve redirect
- `src/components/hospital/tabs/AppointmentsTab.tsx`에 "결제" 버튼
- `src/pages/payment/PaymentHistoryPage.tsx` — `/account/payments`
- Idempotency key 발급·검증

### Commit 9 — 대리결제 (F9, MOAT 씨앗)

- JWT 일회용 토큰 생성 → 링크 `/pay/guard/:token`
- 공유 UX (카카오톡 공유 deep link · 복사 버튼)
- 보호자 전용 결제 페이지 (로그인 불필요)
- **법무 확인**: 대리결제 합법 범위 (사전 승인 + 금액 명시)

### Commit 10 — AI 증상 triage (F19 신규)

**리스크 ★★★** — 오진단 시 브랜드 훼손. "진단 아님" 고지 필수

- `functions/src/triage.ts` — LLM API 호출 + 진료과 매핑
- Secret: `LLM_API_KEY`
- `src/components/hospital/widgets/SymptomTriageWidget.tsx` — 홈 선택 슬롯 (병원별 flag)
- 저장 금지 (증상 텍스트 파기)
- audit log + 사용량 rate limit

### Commit 11 — 알림톡 + SMS/FCM fallback

- `functions/src/notifications/alimtalk.ts` — 카카오 비즈메시지 API
- 3중 fallback: 알림톡 → FCM → SMS
- 템플릿 5종 사전 심사 (진료 확인·호출·결제·취소·리마인더)
- `src/components/account/NotificationSettings.tsx` — 채널별 on/off

### Commit 12 — 주차 할인 어댑터 + 입원/검진 실내용

- `src/services/parking/adapter.ts` — 인터페이스 정의
- `src/services/parking/mock.ts` — 데모용 stub
- `InpatientTab`·`CheckupTab` 스켈레톤 → 담당 의료진·면회 예약·검진 예약 간이 폼

---

## 4. 데이터 모델

### 4.1 `/hospitals/{hid}/wait_queue/{dept}/{date}/{number}`

```typescript
interface WaitEntry {
  id: string;            // {number}
  hospitalId: string;
  department: string;
  date: string;          // YYYY-MM-DD
  number: number;        // 대기 번호
  patientUid: string;
  appointmentId?: string;
  status: 'waiting' | 'called' | 'in-progress' | 'completed' | 'cancelled';
  calledAt?: number;
  startedAt?: number;
  completedAt?: number;
  createdAt: number;
}
```

### 4.2 `/hospitals/{hid}/prescriptions/{id}`

```typescript
interface Prescription {
  id: string;
  hospitalId: string;
  patientUid: string;
  appointmentId?: string;
  pdfUrl: string;        // Firebase Storage path
  issuedAt: number;
  issuedByStaffUid: string;
  expiresAt?: number;    // 기본 30일
}
```

### 4.3 `/payments/{paymentId}`

```typescript
interface Payment {
  paymentId: string;      // idempotencyKey = firestore auto
  hospitalId: string;
  patientUid: string;
  payerUid?: string;      // 대리결제 시 보호자
  amount: number;
  currency: 'KRW';
  pgProvider: 'kakao' | 'toss' | 'naver';
  pgTxId?: string;
  status: 'ready' | 'approved' | 'failed' | 'cancelled' | 'refunded';
  context: { type: 'appointment' | 'checkup' | 'other'; refId?: string };
  createdAt: number;
  approvedAt?: number;
}
```

### 4.4 `/user_fcm_tokens/{uid}/{tokenId}`

FCM 토큰 등록 맵 (기기별).

### 4.5 `/notification_logs/{id}`

알림 발송 이력 (채널·성공/실패).

---

## 5. 보안 규칙 확장

- `wait_queue`: 환자 자기 entry RW, 의료진 부서 전체, 교차 차단
- `prescriptions`: 환자 자기 · 의료진 병원 내
- `payments`: 환자 자기 + 플랫폼 관리자
- `user_fcm_tokens/{uid}`: 본인만
- Emulator 시나리오: P2 18 → **P3 28+ 목표**

---

## 6. 테스트 전략

### 단위 테스트 (vitest)
- waitQueue service CRUD + callNext
- prescription service
- payment service + idempotency
- alimtalk service (mocked)
- triage service (mock LLM response)

### Cloud Function 테스트 (vitest + firebase-admin mock)
- kakaoPay Ready/Approve/Webhook
- onQueueCall FCM dispatch
- triage LLM routing

### Emulator 규칙 테스트
- `scripts/test-rules.mjs` 확장 18 → 28+

### E2E 페이지
- `public/e2e-wait-queue.html`
- `public/e2e-payment-sandbox.html`

### 수동 QA (10+ 시나리오)
- 접수 → 대기 확인 → 호출 → FCM 수신 (실기기)
- 카카오페이 샌드박스 결제
- 대리결제 링크 카카오톡 공유 → 결제
- 알림톡 수신 (심사 후)
- AI triage 증상 입력 → 진료과 추천
- 처방전 업로드 → 다운로드

---

## 7. 리스크 레지스터

| 리스크 | 확률 | 영향 | 완화 |
|---|---|---|---|
| 카카오페이 심사 지연 | 중 | 높 | P3 초반 서류 제출, 샌드박스 우선 개발 |
| 알림톡 템플릿 반려 | 높 | 중 | FCM+SMS 3중 fallback, 템플릿 5종 병행 제출 |
| Webhook 서명 우회 | 낮 | 크리티컬 | HMAC SHA-256 + nonce 재사용 차단 |
| 금액 조작 공격 | 낮 | 크리티컬 | 서버 재조회 필수, client amount 무시 |
| AI triage 오진단 브랜드 훼손 | 중 | 높 | "진단 아님" 고지 + 진료과 추천만 + audit + rate limit |
| AI triage API 비용 폭증 | 낮 | 중 | 월 호출 상한 + 병원별 플랜 |
| FCM iOS Safari 미지원 | 중 | 중 | `isSupported()` 가드 + 알림톡/SMS fallback |
| 대리결제 법적 경계 | 중 | 높 | 법무 검토 선행 (대상 한정, 금액 명시) |
| 처방전 PDF 변조 | 낮 | 중 | Storage 서명 URL + expiresAt |
| 대기 순번 stale state | 중 | 중 | 전이별 timestamp + 스크립트 자동 만료 |

---

## 8. 배포 전략

1. Commit 1-3 (대기 순번 + 호출): rules 배포 → hosting
2. Commit 4-5 (FCM): functions 배포 필수
3. Commit 6 (처방전): Storage rules 추가, hosting
4. Commit 7-8 (결제): Secret Manager 세팅, functions, hosting
5. Commit 9 (대리결제): 법무 게이트
6. Commit 10 (AI triage): API key 세팅, functions, hosting
7. Commit 11 (알림톡): 템플릿 승인 후 활성 (feature flag 대기)
8. Commit 12 (주차·입원/검진): hosting만

각 단계에서 P1·P2 패턴 유지: **Emulator rules 테스트 통과 → dry-run → deploy**.

---

## 9. 완료 기준

- [ ] 대기 순번 실시간 반영 (환자·의료진 양쪽)
- [ ] FCM Push로 호출 알림 수신
- [ ] 카카오페이 샌드박스 결제 성공
- [ ] 대리결제 링크 보호자 결제 완료
- [ ] 알림톡 수신 (심사 후)
- [ ] AI triage 3개 진료과 추천 (정확도 80%+)
- [ ] 처방전 PDF 업로드·다운로드
- [ ] 주차 어댑터 인터페이스 정의 (mock 구현 포함)
- [ ] 입원 탭 담당 의료진 카드 · 면회 예약 폼
- [ ] 검진 탭 간이 예약 폼
- [ ] `npx tsc --noEmit` + `npm run build` + `npx vitest run` 통과
- [ ] Emulator rules 테스트 28+개 통과
- [ ] PR 생성 → develop 병합

---

## 10. 일정 (Day-level)

| Day | 작업 |
|---|---|
| 1-2 | C1-C2 (wait queue schema + rules) |
| 3 | C3 (대기 순번 UI) |
| 4 | C4 (의료진 "다음 환자" 콘솔) |
| 5 | C5 (FCM Push) |
| 6 | C6 (처방전 MVP) |
| 7-8 | C7 (카카오페이 Cloud Function) ★ |
| 9 | C8 (결제 UI + 이력) |
| 10 | C9 (대리결제) ★ 법무 |
| 11 | C10 (AI triage) ★ |
| 12 | C11 (알림톡 + fallback) ★ 심사 대기 |
| 13 | C12 (주차 어댑터 + 입원/검진 실내용) |
| 14 | 통합 QA + 버그 수정 |
| 15-16 | 배포 + PR |

---

## 11. v2 차분 체크리스트

- [ ] F6 처방전 **MVP 축소** — 약국 QR·즐겨찾기 Drop
- [ ] **F19 AI triage 신규 추가** — v1에 없음
- [ ] 주차 할인은 **어댑터만** — 파일럿별 실 구현 Drop
- [ ] Live Activity = TIG 수준 기대치 (Rich Push 대체)
- [ ] 대리결제 MOAT 영업 메시지 반영
- [ ] 입원·검진 실내용은 P3 기본 셋만 (복잡 기능은 P4·P5)

---

## 12. 참조

- `GUIDE_v2/plusultra_v2.md` §"Phase 3"
- `GUIDE_v2/PlusUltra#3.md` (v1 상세 + v2 덮어쓰기 블록)
- `mediway/docs/PLAN_P1.md`, `PLAN_P2.md`
- P1 PR #1, P2 PR #2

---

_작성일: 2026-04-23_
