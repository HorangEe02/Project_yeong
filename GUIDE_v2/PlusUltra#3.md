# PlusUltra #3 — 고수요 편의 기능 상세 구현 가이드

> **Phase 3 기능 설명서 + 구현 가이드라인**
> 범위: 실시간 대기 순번 · 처방전 전송 · 결제/대리결제 · 카카오 알림톡+FCM · 주차 할인 자동화
> 예상 기간: 3~4주 (1인 풀타임, UIUX·심사 대응 포함 ≈ 18~20일)
> 선행 요건: **Phase 1·2 완료** — multi-tenant 기반, 대시보드 셸, 외래 예약이 정상 작동해야 함

---

## 목차

- [起 — 왜 지금 "편의 기능"인가](#起--왜-지금-편의-기능인가)
- [承 — 설계 원칙과 기술 선택](#承--설계-원칙과-기술-선택)
- [轉 — 세부 구현 설계](#轉--세부-구현-설계)
  - [1. 실시간 대기 순번 (F1)](#1-실시간-대기-순번-f1)
  - [2. 처방전 + 약국 전송 (F6)](#2-처방전--약국-전송-f6)
  - [3. 결제 / 대리결제 (F8, F9)](#3-결제--대리결제-f8-f9)
  - [4. 알림톡 / Push (F5)](#4-알림톡--push-f5)
  - [5. 주차 할인 자동화 (F8)](#5-주차-할인-자동화-f8)
  - [6. 입원 · 건강검진 탭 실내용](#6-입원--건강검진-탭-실내용)
  - [7. 데이터 스키마 확장](#7-데이터-스키마-확장)
  - [8. 보안 규칙 확장](#8-보안-규칙-확장)
  - [9. 규제·법률 대응](#9-규제법률-대응)
- [結 — 완료 기준·검증 전략·Next](#結--완료-기준검증-전략next)
- [UIUX 가이드라인](#uiux-가이드라인)
- [부록](#부록)

---

## 📌 v2 업데이트 (2026-04-22)

> **이 파일은 PlusUltra v1 상세 가이드입니다.** v2 기준 문서 `GUIDE_v2/plusultra_v2.md` §Phase 3이 최종 실행 기준이며, 충돌 시 **v2가 우선**합니다.

### Phase 3 v2 조정사항

| # | 조정 | v1 대비 | 영향 섹션 |
|---|---|---|---|
| 1 | 🔻 **F6 처방전 MVP 축소** | v1은 약국 QR 발급 + 약국 선택 UI + 즐겨찾기 약국까지 | §2. 처방전 + 약국 전송 — **PDF 업로드 · 환자 다운로드 · 공유 링크 생성**만 유지. 약국 앱 직접 전송·즐겨찾기 약국은 2026 전자처방전 표준 확정 후 재도입 |
| 2 | 🆕 **F19 AI 증상 triage 신규 추가** (v1에 없음) | — | **신규 §3.6** 개념: 환자 홈 입력 → OpenAI/Anthropic/Gemini API → 진료과 추천. 자세한 사양은 `plusultra_v2.md` §3.6 및 §부록 C 참조 |
| 3 | 🔻 **주차 할인 파일럿별 feature flag** | v1은 공통 어댑터 인터페이스 정의 + 1곳 구현 | §5. 주차 할인 — 인터페이스 정의는 유지, **실제 구현은 파일럿 계약 후**. 도심 중소병원(주차장 없음)은 완전 OFF |
| 4 | 🔸 **Live Activity 기대치 TIG 수준으로 하향** | v1은 "차별점" 표현 | 똑닥이 2023부터 보편화, 동등 수준 = **본전**. 영업 셀링 포인트에서 제외 |
| 5 | 🔥 **대리결제 (F9) MOAT로 강조** | v1은 일반 기능 | §3. 결제 — 대리결제를 영업 Top 3 중 하나로 포지셔닝 (가족 대리 MOAT와 연결) |

### 신규 §3.6 — AI 증상 triage (F19) 핵심

- **입력**: 증상 자유 텍스트 (최대 500자)
- **처리**: LLM API 호출 → 병원 `/hospitals/{id}/triage-map` 진료과 매핑
- **출력**: 상위 3개 진료과 + 근거 문장 + **"진단 아님" 고지 필수**
- **저장**: 증상 텍스트 **서버 저장 금지** (API 후 파기)
- **비용**: GPT-4o-mini 기준 월 10k 호출 ~$20
- **리스크 완화**: audit log · 속도 제한 · 사용 동의 필수

상세는 `plusultra_v2.md` §3.6 및 §부록 C.F19 참조.

### 적용 원칙

- 실시간 대기 · 결제 · 알림톡 · 어댑터 패턴 · HMAC 검증 · 멱등성 키: **v1 원안 준수**
- F6 처방전 스코프 · F19 AI triage 신규 · 주차 flag · Live Activity 기대치: **v2 기준**
- 의심 시 `GUIDE_v2/plusultra_v2.md` §"Phase 3" 확인

---

## 起 — 왜 지금 "편의 기능"인가

### Phase 2의 한계
P2 종료 시점 MediWay는 **"탭 기반 병원 대시보드 + 예약 + 길찾기"**다. 사용 가능하지만 **차별화 부족**. 국내 앱 경쟁 구도:

| 경쟁 포인트 | 현재(MediWay P2) | 경쟁 수준 |
|---|---|---|
| 실시간 대기 순번 | ❌ | 똑닥 **Live Activity** 압도적 |
| 결제 | ❌ | 삼성서울병원 강점 |
| 알림톡 | ❌ | 국내 의료앱 표준 |
| 주차 할인 | ❌ | 삼성서울병원 자동화 |
| 처방전 약국 전송 | ❌ | 똑닥 핵심 기능 |
| 길찾기 + 세션 | ✅ (차별화) | 경쟁사 대부분 단순 위치 표시 |

Phase 3는 경쟁 평균을 따라잡고 **핵심 차별점(QR 세션 + 길찾기)에 편의 기능을 결합**하는 단계다.

### 비즈니스 타당성
- 시장 조사(`plusultra.md`): 디지털 wayfinding + 편의 기능 통합 ROI **396%** / 회수기간 3개월
- 파일럿 병원 영업에서 **"실시간 대기 + 결제 + 알림톡"은 사실상 필수**. 이들 없이는 계약 불가
- 이미 E2E 테스트·RTDB 규칙·화이트라벨 기반이 있어 **한 번 만들면 모든 병원에 재활용** 가능

### Phase 3의 4대 가치
1. **차별화 완성** — QR 세션 × 실시간 대기의 시너지 (의료진이 호출 → 환자 순번 + 길안내 동시 활성)
2. **영업력** — 파일럿 병원 계약 성사 가능성 대폭 상승
3. **수익화 기반** — 결제 거래 수수료 또는 건당 fee
4. **규제·심사 역량 내재화** — 카카오 알림톡 · PG 심사 과정을 정비하여 다음 병원 확장 시 반복 비용 제거

---

## 承 — 설계 원칙과 기술 선택

### 원칙 8계명
1. **서비스별 어댑터 인터페이스** — PG·알림톡·주차는 병원마다 다른 벤더. 추상 인터페이스 + 구현체 교체 가능
2. **결제는 서버 권위, 클라이언트 UI** — 금액·승인은 반드시 서버 검증. 클라이언트가 `amount`를 보내도 **무시**
3. **멱등성 키** — 결제/알림 트리거에 `idempotencyKey` 필수. 재시도 중복 방지
4. **실패 투명성** — 알림톡·FCM 실패 시 사용자에게 fallback (SMS·이메일) 또는 알림 미전송 상태 표시
5. **규제 최소 수집** — 결제 카드정보는 PG가 저장, MediWay는 거래 ID·상태만 보관 (PCI DSS 회피)
6. **사용자 동의 기록** — 알림 수신·결제 정보 이용 동의는 타임스탬프·버전과 함께 보관
7. **실시간 대기는 낙관적 UI** — 의료진 호출 후 환자 화면은 최악 500ms 안에 반영. RTDB `onValue`로 실현
8. **탭과 결합** — 실시간 대기는 홈 위젯 + 안내 탭에 자동 동기화

### 기술 스택 선택 근거

| 영역 | 선택 | 대안 | 이유 |
|---|---|---|---|
| 실시간 대기 | RTDB `onValue` + FCM | Firestore 실시간, 웹 Push 전용 | RTDB가 이미 주력, 초저지연 |
| iOS Live Activity | 초기엔 **FCM + Rich Push**, 추후 native app wrapper(Capacitor)로 ActivityKit | 웹 only | 순수 웹은 Live Activity 불가. P3는 웹 Rich Push + Safari Web Push로 대응, ActivityKit은 선택적 |
| 결제 PG | **카카오페이**(1차) → 토스·네이버(확장) | 자체 PG, Bootpay 등 aggregator | 국내 MAU 최대, 승인 프로세스 안정, Subscription/비대면 결제 풍부 |
| 알림톡 | **카카오 비즈메시지 API(톡비즈)** | Aligo·Lunasoft 등 재판매 | 공식 API가 가장 안정. 장기적 비용도 낮음 |
| 푸시 | **FCM**(Web+Android+iOS) | OneSignal | Firebase 스택 내부. 비용 무료 |
| 주차 | **Adapter 패턴** (병원별 구현 플러그인) | 단일 API | 국내 주차 시스템 파편화 극심 |
| 결제 백엔드 | Firebase Functions v2 + Axios | 별도 Express | 기존 스택 유지 |
| Webhook 검증 | HMAC SHA-256 + nonce | IP 화이트리스트만 | 가장 안전 |
| 데이터 암호화 | Firebase Firestore/RTDB 전송 TLS + 민감 필드 AES-256-GCM (Cloud KMS) | 로컬 키 | 규제 대응. 민감 정보 최소화 |

### 필요 선행 지식

| 분야 | 깊이 | 핵심 |
|---|---|---|
| Phase 1·2 산출물 | 완전 이해 | HospitalContext · features flag · OutpatientTab |
| Firebase Cloud Functions v2 + Secret Manager | 실무 | PG·카카오 API 키 안전 보관 |
| Web Push Protocol + Service Worker | 실무 | 이미 `firebase-messaging-sw.js` 존재 |
| 카카오페이 온라인 결제 API | 실무 | Ready → Approve → Webhook |
| 카카오 비즈메시지(알림톡) API + 템플릿 심사 | 실무 | 템플릿 사전 심사 7~14일 소요 |
| HMAC·암호화 기초 | 실무 | Webhook 검증 |
| 개인정보보호법(PIPA), 전자금융거래법, 의료법 광고 규제 | 기본 | 결제·알림·의료광고 주의 |

### 위험 조기 식별

| 위험 | 영향 | 완화 |
|---|---|---|
| 카카오페이 심사 거절/지연 | 출시 연기 | **P3 초반**에 서류 준비 시작. 테스트 결제 샌드박스 먼저 연동 |
| 알림톡 템플릿 반려 | 알림 채널 손실 | FCM·SMS fallback 3중 구조. 템플릿 5종 병행 제출 |
| 결제 취소·환불 로직 누락 | 컴플레인 폭발 | 취소 API 우선 구현 + PG 웹훅 처리 |
| 결제 금액 조작 시도 | 금전 손실 | 모든 금액은 **서버 재조회**, 클라가 보내는 값 무시 |
| Live Activity 미지원 | 기대치 불일치 | P3는 Rich Push까지. Live Activity는 Capacitor 래퍼 후속 작업 |
| 주차 어댑터 복잡도 | 파일럿별 n배 | 1차 파일럿 1개 병원 API만 구현, 나머지는 manual flow |
| Webhook 서명 우회 | 가짜 결제 성공 | 항상 HMAC 검증 + nonce 재사용 차단 |

---

## 轉 — 세부 구현 설계

### 1. 실시간 대기 순번 (F1)

#### 1.1 데이터 모델

```
/wait_queue/{hospitalId}/{departmentId}/{date}/
  cursor: 43                              # 현재 호출 중인 번호
  entries/
    {entryId}:
      uid: "..."                          # 환자 UID
      appointmentId: "..."                # 연계 예약 (있으면)
      number: 45                          # 순번
      status: "waiting" | "called" | "in_consult" | "done" | "no_show"
      calledAt?: number
      joinedAt: number
      ahead: 2                            # 내 앞 대기 수 (server-maintained)
```

- `ahead`는 서버 계산값. `cursor`와 `number` 차이로 유도도 가능하지만 **비정규화**로 클라이언트 연산 간소화
- `cursor` 이동 시 Cloud Function이 관련 entries 일괄 업데이트 (batched transaction)

#### 1.2 의료진 호출 흐름

1. Staff 콘솔에서 "다음 환자 호출" 버튼
2. `onCallNextPatient(hospitalId, departmentId)` Callable Function
3. 서버 transaction:
   - 가장 작은 `waiting` entry 찾기
   - `status → called`, `calledAt = now`
   - `cursor = 그 entry의 number`
   - 나머지 `waiting` entries의 `ahead` 재계산
4. 환자 앱(RTDB onValue)이 자기 entry 상태 변화 감지 → 홈 위젯·Push 알림

#### 1.3 환자측 UI

- 홈 `WaitQueueWidget`: "내 앞 3명 · 예상 10분" → 호출되면 gradient 배경 + "지금 내 차례입니다" + "진료실 안내" CTA
- 안내 탭(기존 GuideTab): 호출 시점에 자동으로 진료실 경로 로드. 세션 `status === called` 감지 훅

#### 1.4 Push 트리거

- `status === called`가 되면 Functions에서 FCM `sendToDevice(userTokens, ...)` 
- 알림 내용: "곧 진료입니다! 3번 진료실로 이동해 주세요" + deep link `mediway://guide/ward-3`
- iOS Safari Web Push: APNs VAPID 설정 필요

#### 1.5 "호출 예상 시간" 계산

- 의료진 평균 진료 시간 `avgConsultMs` 병원별 DB 저장
- `expectedWaitMs = ahead * avgConsultMs`
- 30분 단위로 값 업데이트 (스케줄 Function)

### 2. 처방전 + 약국 전송 (F6)

#### 2.1 처방전 데이터 소스
- **A. Staff 수동 업로드 (P3 MVP)**: 진료 완료 시 PDF 업로드 → `/hospitals/{id}/prescriptions/{uid}/{rxId}`
- **B. EMR 연동 (P5)**: EMR이 자동 push — 병원별 파트너십

P3 범위는 **A만**. B는 Phase 5.

#### 2.2 약국 전송 메커니즘

두 가지 경로 병행:

**경로 1: QR 코드**
- 환자가 약국에서 MediWay QR 제시 → 약국 스캐너가 서버에 조회 → 처방전 PDF 또는 구조화 JSON 반환
- QR 만료 10분, 일회용

**경로 2: 약국 코드 입력**
- 환자 앱에서 약국 검색 → 선택 → 서버가 해당 약국에 업로드 알림 (email + API)

#### 2.3 데이터 모델

```
/hospitals/{id}/prescriptions/{uid}/{rxId}
  issuedAt: number
  doctorId: string
  status: "issued" | "sent_to_pharmacy" | "dispensed" | "cancelled"
  pdfUrl: string              # Firebase Storage 암호화
  items: [
    { drugCode, drugName, dosage, duration, instructions }
  ]
  sentTo?: { pharmacyId, sentAt }
  qrToken?: string            # 일회용 토큰
```

#### 2.4 약국 디렉토리
- `/pharmacies/{pharmacyId}` — 전국 공용 디렉토리
  - 심평원 공개 API로 초기 시드
  - 팩스·이메일 연락처 보유
- 초기 약국 등록은 수동·OCR, P4에서 B2B 약국 파트너 진입 유도

### 3. 결제 / 대리결제 (F8, F9)

#### 3.1 결제 대상
- 진료비
- 검사비
- 약제비 (처방전 기반)
- 주차 할증 (P3.5 주차 섹션 연계)

#### 3.2 아키텍처

```
[환자 앱] ─(결제 요청)─> [Cloud Function: readyPayment]
                                │
                                ▼
                        카카오페이 Ready API
                                │
                                ▼
                        [환자 앱] kakao redirect/WebView
                                │
                                ▼
                  승인 페이지에서 사용자 확인
                                │
                                ▼
                        카카오페이 Approve API ────> [Cloud Function: approvePayment]
                                │
                                ▼
                        [DB: /payments/{id}] 상태 업데이트
                                │
                                ▼
                        [카카오페이 Webhook] ─검증─> [Function: onPaymentWebhook]
                                                        │
                                                        ▼
                                                [FCM 알림 · 영수증 생성]
```

#### 3.3 결제 레코드

```
/payments/{paymentId}
  hospitalId
  uid              # 결제자(환자 또는 대리인)
  payerRole: "self" | "proxy"
  beneficiaryUid   # 진료 당사자
  amount
  currency: "KRW"
  status: "pending" | "approved" | "failed" | "cancelled" | "refunded"
  pgProvider: "kakaopay"
  pgTxId
  idempotencyKey
  items: [ {type, refId, title, amount} ]
  createdAt
  approvedAt
  receiptUrl
```

#### 3.4 대리결제 (Proxy Payment) 흐름

1. 환자가 "대리 결제 요청" 버튼
2. 서버: 결제 레코드 생성 (`status: pending`, `payerRole: proxy`)
3. 보호자에게 **카카오 알림톡**으로 결제 링크 전송
4. 보호자가 링크 탭 → MediWay 로그인(간편) → 결제 페이지 → 카카오페이 결제
5. 승인 후 환자·보호자 모두에게 알림

링크 보안:
- 링크 토큰은 JWT 서명, 10분 만료, 일회용
- 보호자가 MediWay 계정 없으면 간편 가입 또는 게스트 결제

#### 3.5 서버 금액 결정 규칙 (중요)

**절대로 클라이언트가 보낸 `amount`를 신뢰하지 않는다.**

```ts
// functions/src/payment/readyPayment.ts
export const readyPayment = onCall({...}, async (req) => {
  const { hospitalId, itemType, itemId } = req.data;  // amount 없음
  const amount = await computeServerAmount(hospitalId, itemType, itemId, uid);
  // 카카오페이 Ready 호출 with amount
});
```

- 이유: 클라 조작 시 환자가 100원에 결제하고 100만원 진료비를 해결하는 시나리오 차단

#### 3.6 환불

- 전액 환불: 카카오페이 Cancel API
- 부분 환불: Cancel with partial amount
- 관리자 UI로 트리거, 서버측 권한 검증(`staff` 또는 `admin`)

### 4. 알림톡 / Push (F5)

#### 4.1 알림 채널 우선순위

```
1순위: 카카오 알림톡 (수신자 카카오 계정 연결 시)
2순위: FCM Push (앱 설치 + 권한 허용)
3순위: SMS (비상시, 비용 지불)
4순위: 이메일 (최후 fallback)
```

Functions 내부에 `NotificationDispatcher`가 우선순위대로 시도, 실패 시 다음 채널로 승계.

#### 4.2 알림 시나리오 (P3)

| 시나리오 | 채널 | 템플릿 예시 |
|---|---|---|
| 예약 확인 | 알림톡 | "{name}님, {date}({dayOfWeek}) {time} {doctorName} 선생님 진료가 예약되었습니다." |
| 예약 당일 리마인더 (1h 전) | 알림톡 + FCM | "{name}님, 1시간 뒤 진료가 예정되어 있습니다. 미리 도착해 주세요." |
| 순번 호출 (당장) | FCM + 알림톡 | "지금 {department} 진료실로 이동해 주세요." |
| 순번 5분 전 | FCM | "내 앞 1명, 5분 내 호출 예정" |
| 결제 완료 | 알림톡 | 영수증 링크 |
| 대리결제 요청 | 알림톡 | "{name}님이 결제를 요청했습니다. [결제하기]" |
| 처방 약국 전송 완료 | 알림톡 | "처방전이 {pharmacy}로 전송되었습니다." |

#### 4.3 카카오 알림톡 템플릿 준수

- 템플릿은 **사전 심사 필수** (카카오 비즈메시지 관리자)
- 변수는 `#{name}` 형태, 30자 내외 제한적
- 광고성 문구 금지 — "신상품", "할인" 등
- 템플릿 코드를 DB에 매핑해 Functions에서 치환
- **심사 기간 7~14일** 여유 두고 P3 초반에 착수

#### 4.4 사용자 동의 및 수신 설정

- 회원 가입 시 알림 동의 체크박스 (필수/선택 구분, 필수는 예약 관련)
- 더보기 탭 → 알림 설정: 시나리오별 on/off
- 철회 시 타임스탬프 기록 (PIPA 대응)

### 5. 주차 할인 자동화 (F8)

#### 5.1 어댑터 패턴

```ts
// src/services/parking/types.ts
export interface ParkingAdapter {
  registerVehicle(hospitalId: string, uid: string, plate: string): Promise<void>;
  applyDiscount(hospitalId: string, uid: string, appointmentId: string): Promise<{ discount: number }>;
  getParkingInfo?(plate: string): Promise<ParkingSession | null>;
}

// src/services/parking/adapters/mock.ts
export const mockAdapter: ParkingAdapter = { ... };

// src/services/parking/adapters/hospitalA.ts
export const hospitalAAdapter: ParkingAdapter = { ... };
```

- 병원별 구현체는 Cloud Functions에서 로드. `hospitals/{id}/profile.parking.adapter` 필드로 선택 (`mock` / `hospitalA` / `none`)

#### 5.2 환자 UX
- 더보기 → 주차 등록 → 차량번호 입력 (OCR 선택)
- 진료 완료 시 자동으로 adapter.applyDiscount 호출
- 결과 카드: "오늘 진료 방문으로 주차 할인 3시간 적용됨"

#### 5.3 파일럿 파트너 선정
- 1차 파일럿 병원의 주차 시스템 벤더와 API 계약
- 미연동 병원은 "주차 정산 안내"만 보여주는 `none` 어댑터

### 6. 입원 · 건강검진 탭 실내용

#### 6.1 입원 탭 (P2 skeleton 채움)
- 담당 의료진 카드, 입원실 정보
- 면회 예약 (시간 슬롯, 방문객 인원 제한)
- 식단 안내 (오늘/내일, 알레르기 제외 옵션)
- 퇴원 수속 체크리스트 + 서류 다운로드

#### 6.2 건강검진 탭
- 검진 예약/변경 (외래 예약 wizard 재활용, 부서만 "검진센터")
- **검진 전 온라인 문진** (P5 부분 미리)
- 검진 결과 이력 (PDF 업로드 방식; P5 EMR 연동까지 수동)

### 7. 데이터 스키마 확장

```
/wait_queue/{hospitalId}/{departmentId}/{date}/
/hospitals/{id}/prescriptions/{uid}/{rxId}/
/pharmacies/{pharmacyId}/
/payments/{paymentId}/
/notifications/queue/{id}/                 # 발송 예약
/notifications/history/{uid}/{id}/         # 수신 이력
/hospitals/{id}/visits/{uid}/{visitId}/parking/
/hospitals/{id}/profile/parking/           # adapter 설정
/users/{uid}/notificationPrefs/            # 수신 동의
/users/{uid}/vehicles/                     # 차량 번호
/users/{uid}/family/                       # 가족 대리인 (P4 병행)
```

### 8. 보안 규칙 확장

핵심:
- `/payments/{id}` — 본인(payer) or 수혜자(beneficiary) 또는 hospital admin/staff 읽기
- `/wait_queue/...` — 본인 entry 읽기, staff/admin 쓰기
- `/pharmacies` — 공개 읽기, platform admin 쓰기
- `/notifications/history/{uid}` — 본인만 읽기

민감 필드는 **`.validate`로 구조 강제** (금액은 서버만 쓰기, 환자는 상태 못 바꿈)

### 9. 규제·법률 대응

#### 9.1 전자금융거래법
- 결제 대행은 **PG 사업자가 부담** (카카오페이). MediWay는 **결제 대행 가맹점**으로 계약
- 사업자 등록 + 전자금융업 신고 등 **자체 결제 서비스 제공자로 등록은 필요 없음**
- 카카오페이 제휴 계약 시 영업·세무 정보 제출

#### 9.2 PIPA (개인정보보호법)
- 결제 정보, 차량 번호, 연락처, 알림 수신 등 **처리 방침 문서화** 필수
- 수집 시 **선택/필수 구분** 동의
- 민감 정보(진단명, 처방) 접근 로그 감사

#### 9.3 의료법
- 의료 광고 규제: 알림톡 템플릿이 "할인 이벤트" "최저가" 등 사용 불가
- 비대면 진료는 재진·만성질환 대상만 (굿닥처럼) — P3에서는 결제에 한정

#### 9.4 개인정보 제3자 제공 동의
- 알림톡 발송 위탁·PG 위탁·주차 시스템 위탁 각각 동의 문구 작성
- 동의 기록: 사용자별·시점별 보관

---

## 結 — 완료 기준·검증 전략·Next

### 완료 기준 (세부화)

#### 기능
- [ ] 의료진이 "다음 환자 호출" → 환자 홈 위젯 1초 이내 "지금 차례" 변경
- [ ] 호출 시점에 Push/알림톡 수신 (최소 1채널)
- [ ] 호출 시점에 안내 탭의 경로가 해당 진료실로 자동 업데이트
- [ ] 진료 완료 후 처방전 업로드 → 환자 앱에서 확인 가능
- [ ] 약국 QR 생성 가능, 10분 만료
- [ ] 카카오페이 샌드박스에서 결제 성공 + 웹훅 수신 + `/payments` status `approved`
- [ ] 대리결제: 보호자에게 알림톡 전송 + 링크 접근 가능
- [ ] 환불 시 상태 `refunded`로 전이, 금액 복원
- [ ] 알림 설정에서 채널별 on/off 동작
- [ ] 주차 차량 번호 등록 가능 (mock adapter)

#### 보안·규제
- [ ] 결제 요청에 클라 `amount` 무시, 서버 재계산
- [ ] Webhook HMAC 검증 실패 시 거부
- [ ] 민감 필드 (PDF URL, 카드 일부) 암호화 저장
- [ ] 수집·이용·제3자 제공 동의 UI 존재 + 로그 저장
- [ ] 의료 광고 문구 심사 가이드 준수 (템플릿 5종 승인)

#### 성능
- [ ] 실시간 대기 업데이트 지연 < 1s (목표 <500ms)
- [ ] 결제 Ready → Approve 평균 3s 이내
- [ ] 알림톡 발송 → 수신 평균 5s 이내

#### 품질
- [ ] tsc/eslint 통과
- [ ] 결제 E2E (sandbox) 자동 테스트
- [ ] 보안 규칙 E2E 추가 (payments, wait_queue)

### 검증 전략

1. **자동**
   - Functions unit test: readyPayment·approvePayment·웹훅 서명 검증
   - E2E Playwright: 환자 예약 → 호출 → 알림 → 결제 → 완료 전 흐름
   - `public/e2e-payment.html` sandbox 결제 스모크 테스트
2. **수동**
   - 파일럿 병원 직원 5명이 실제 흐름 체험
   - 알림 채널 3종 fallback 동작 (카카오 계정 미연결 → FCM → SMS)
3. **규제 준비**
   - 개인정보 처리방침·이용약관 문서 검토
   - PG 심사 서류 제출

### 롤백 계획
- 기능별 feature flag: `VITE_P3_WAIT_QUEUE`, `VITE_P3_PAYMENT`, `VITE_P3_ALIMTALK`, `VITE_P3_PARKING`
- 장애 시 flag off → 홈 위젯·탭 숨김. 기존 P2 기능은 영향 없음
- 결제 장애 긴급: 서버 `GLOBAL_PAYMENT_DISABLED` 플래그로 Ready API 차단

### Next (Phase 4 진입 조건)
1. 완료 기준 100% 통과
2. 파일럿 병원 1곳에서 실제 결제 1주 무사고 운영
3. P4 시작 시 `PlusUltra#4.md`로 이어받아 **고령자·접근성·OAuth·가족 대리**

---

## UIUX 가이드라인

본 절은 `uiux/` 폴더를 Phase 3 신규 화면에 녹일 때의 가이드. P1/P2의 원칙을 전제하고 P3 특유의 요소만 다룬다.

### U1. 참조 자산 매핑 (P3 대상)

| 경로 | 대응 P3 화면 |
|---|---|
| `mobile_uiux/mediway_user_main/` | 홈 탭 — WaitQueueWidget, ProxyPaymentCTA 삽입 |
| `web_page_uiux/mediway_user_main/` | 홈 탭 (웹) — ProxyPayment col-span-2 CTA 실제 활성화 |
| `mobile_uiux/mediway_qr/` | 약국 QR 전송 화면 참조 (QR UI 패턴) |
| `mobile_uiux/mediway_staff_*/` · `web_page_uiux/mediway_staff_v2_*/` | Staff 콘솔 — "다음 환자 호출" 버튼, 환자 세션 관리 |
| `uiux/*/mediway_clinical/DESIGN.md` | 알림 배너, 결제 CTA, 긴급 상태 시각화에 `error-container` · Glassmorphism 재사용 |

### U2. 모바일 vs 웹 — P3 기능별 레이아웃

#### U2.1 WaitQueueWidget (대기 순번)

**공통 상태 3가지**
- **Idle** ("대기 중 아님"): 숨김
- **Waiting** (대기 중): 잔잔한 카드. 순번 · 내 앞 · 예상 시간
- **Called** (호출됨): 강조 카드. 그라디언트 + 펄스 애니메이션 + CTA

##### 모바일

```
Waiting:
┌────────────────────────────────────┐
│ 🏥 내과 대기                       │
│                                    │
│  #45                               │  text-5xl font-bold
│  내 앞 3명 · 약 10분               │
│                                    │
│  [진료실 보기 →]                    │
└────────────────────────────────────┘

Called (진료 호출됨):
┌────────────────────────────────────┐
│ 🔔 지금 내 차례입니다!             │  gradient + white text
│                                    │
│  3번 진료실                        │
│  2층 · 서쪽 복도                   │
│                                    │
│  [바로 안내받기 ⚡]                 │  큰 CTA, gradient
└────────────────────────────────────┘
```

- Waiting: `surface-container-lowest` 배경, `shadow-[0_4px_24px_rgba(0,78,159,0.04)]`
- Called: `bg-gradient-to-br from-primary to-primary-container text-on-primary`, 펄스 애니메이션 (5s), 배경에 subtle ping ring
- CTA "바로 안내받기" 탭 → 안내 탭으로 전환 + `mode=guide&sessionId=...` 자동

##### 웹

- 홈 탭의 좌측 컬럼(col-span-7) 내 TodayScheduleWidget 위로 승격
- 카드 크기 더 큼, `text-7xl` 순번, 오른쪽에 "안내 시작" 큰 CTA
- Called 상태에서는 **전체 화면 모달 glassmorphism** 옵션 (`mediway_clinical/DESIGN.md`의 "Vitality Glass Modal")

#### U2.2 Payment UI (결제 / 대리결제)

##### 결제 버튼 / Sheet

**모바일**
- 진료 완료 후 홈 또는 외래 탭에서 "진료비 결제" 배너
- 탭 시 **Bottom Sheet** (drawer) 펼침: 금액·항목 요약 → 카카오페이 결제 버튼
- 결제 진행 중: 로딩 상태 (`loading spinner` + "결제 처리 중…")
- 완료: 체크 애니메이션 + 영수증 공유 옵션

**웹**
- 모달 다이얼로그 (glassmorphism `backdrop-blur-xl`)
- 좌측 결제 요약, 우측 결제 버튼
- 결제 완료 시 영수증 PDF 바로 다운로드 가능

##### ProxyPayment CTA (홈 탭)

- P2에서 placeholder였던 것을 **실제 활성화**
- 모바일: Schedule 위 큰 gradient 배너, 탭 시 결제 요청 모달
- 웹: Quick Actions 하단 col-span-2 gradient CTA

##### 대리결제 링크 수신 화면 (보호자용)

- `/pay/:token` 전용 페이지
- 헤더 없음 (결제 집중형)
- 요약 카드 (누가·얼마·항목) + "결제하기" gradient 버튼
- 본인이 이미 MediWay 사용자면 자동 로그인, 아니면 간편 가입 안내
- 만료 임박 카운트다운 (`10:00 → 09:59 ...`)

#### U2.3 처방전·약국 전송 화면

##### 처방전 상세 (모바일/웹 공통 구조)

```
┌─────────────────────────────────────┐
│ ← 처방전                            │
│                                     │
│  {병원명} · {날짜}                    │
│  처방 의료진: {doctor}                │
│                                     │
│  처방 약품                           │
│  ┌─────────────────────────────────┐│
│  │ 타이레놀 500mg · 1일 3회 · 3일 ││
│  │ 위장약 · 1일 1회 · 3일         ││
│  └─────────────────────────────────┘│
│                                     │
│  [💊 약국으로 전송]                  │  gradient CTA
│  [📥 PDF 다운로드]                    │
└─────────────────────────────────────┘
```

##### 약국 선택

- 검색 + 즐겨찾기 별도 섹션
- 카드 형태 (약국명 · 주소 · 영업 중/종료 상태)
- 선택 후 **확인 모달**: "전송하시겠어요?" + 약국명 · 전송 방식(QR / 서버)

##### QR 코드 화면

- 전체 화면 카드, 중앙에 QR (Storage URL 또는 클라이언트 생성)
- QR 아래 **"10:00 남음"** 카운트다운
- 만료 시 "QR이 만료됐어요. 다시 생성할까요?" fallback

#### U2.4 의료진 콘솔 "다음 환자 호출" 버튼

- Staff 대시보드 상단에 큰 primary 버튼
- 클릭 시 확인 없이 즉시 호출 (빠른 동선)
- 호출 후 해당 환자 카드가 상단 강조 (hovering + timer)
- 웹은 키보드 단축키 `Space` 또는 `N` — 의료진 업무 효율

#### U2.5 알림 설정 (더보기 탭)

- 토글 리스트 (iOS 설정 앱 스타일)
- 섹션: 예약 · 진료 · 결제 · 처방 · 마케팅(기본 off)
- 각 토글 옆 "카카오 연결" 상태 뱃지 (연결됨/미연결 시 "연결하기" 유도)

### U3. 애니메이션·피드백

| 상황 | 패턴 |
|---|---|
| 순번 호출 | 펄스 ring (`@keyframes pulse-ring`), 5초 반복 |
| 결제 성공 | 체크 아이콘 스케일 인 (0.5s spring) |
| 결제 실패 | 좌우 shake (0.3s) + error 텍스트 |
| 알림 수신 | Toast 슬라이드 인 (하단/우측), 3s 자동 닫힘 |
| 대기 시간 갱신 | 숫자 카운트 애니메이션 (`framer-motion`의 `animate`) |
| prefers-reduced-motion | 모든 motion 해제, fade만 |

### U4. 상태 시각 코드

| 상태 | 색상 | 용도 |
|---|---|---|
| 대기 중 | `primary-container` (옅은) | 잔잔 |
| 호출됨 | gradient primary→primary-container | 강조 |
| 결제 진행 | `tertiary` (옅은 청록) | 중립 진행 |
| 결제 완료 | `secondary-container` | 긍정 완료 |
| 결제 실패 | `error-container` | 주의 |
| 무효/만료 | `surface-container-high` + `opacity-60` | 비활성 |

### U5. 접근성 (P3 특화)

- 순번 호출 알림: **시각 + 청각(선택) + 진동(모바일)** 3중
- 금액 정보는 `aria-label`에 "사만오천원" 한글 표기
- 결제 버튼 disabled 상태 명확 (회색 + `aria-disabled="true"`)
- Bottom Sheet는 `role="dialog"` + `aria-modal="true"` + Escape 닫기
- QR 화면은 `aria-label="약국 QR 코드"` + 아래 숫자 코드 텍스트 병기

### U6. 피해야 할 함정

1. **결제 금액을 클라 UI 기반으로 결정** — 치명. 서버 재계산 원칙
2. **알림톡만 믿기** — 카카오 서버 장애·심사 반려 시 대체 채널 필수
3. **Push 권한 요청을 로그인 직후** — 거절률 높음. 사용자가 첫 알림 트리거 가까운 시점(첫 예약 완료 후)에 요청
4. **호출 알림 과도** — 순번 변경마다 Push 보내면 지치게 함. 호출·5분 전·당장 3회로 제한
5. **주차 어댑터 공통화 과욕** — 초기엔 파일럿 1개만. 추상화는 2~3번째부터
6. **영수증·PDF 업로드 후 보관기간 명시 안 함** — 규제 위반. 5년(전자금융거래법)
7. **에러 toast로만 처리** — 결제 실패는 구체적 원인(카드 한도·네트워크 등) 안내 필요
8. **Live Activity 기대 설정** — 순수 웹은 불가. P3는 Rich Push로 대체, 문서에 명확히

### U7. 구현 체크리스트 — UIUX

- [ ] WaitQueueWidget 3상태 (idle/waiting/called) 구현 + 모바일·웹 크기 차
- [ ] 호출 상태 펄스 애니메이션 + `reduced-motion` 폴백
- [ ] 결제 Bottom Sheet (모바일) · Glassmorphism 모달 (웹)
- [ ] ProxyPayment CTA 활성화, P2 placeholder 교체
- [ ] 대리결제 링크 화면 독립 레이아웃 (`/pay/:token`)
- [ ] 처방전 상세 + 약국 선택 + QR 화면 3단계 UX
- [ ] Staff "다음 환자 호출" 버튼 + 단축키 (웹)
- [ ] 알림 설정 토글 리스트 + 카카오 연결 상태 뱃지
- [ ] Lighthouse Accessibility 95+ 유지
- [ ] 모든 새 알림/결제 에러는 구체적 한국어 안내

### U8. 작업 견적 (UIUX 포함)

| 작업 | 소요 |
|---|---|
| 실시간 대기 RTDB·Function·호출 Webhook | 2.0일 |
| WaitQueueWidget UI (모바일/웹·3상태) | 1.5일 |
| 결제 Functions (Ready·Approve·환불·Webhook) | 2.5일 |
| 결제 UI (Bottom Sheet + Modal + ProxyLink) | 2.0일 |
| 카카오 알림톡 연동 + NotificationDispatcher | 2.0일 |
| 알림 설정 UI + 사용자 동의 모달 | 1.0일 |
| 처방전 업로드·약국 전송·QR 생성 | 1.5일 |
| 약국 디렉토리 seed + 검색 UI | 1.0일 |
| 주차 어댑터 인터페이스 + mock + 1개 실구현 | 1.5일 |
| 입원·검진 탭 실내용 채움 | 1.5일 |
| 보안 규칙 확장 + E2E 테스트 | 1.0일 |
| 규제 문서 (처리방침·이용약관) 초안 | 1.0일 |
| 회귀 테스트·UIUX QA | 1.0일 |
| **합계** | **19.5일 (≈ 4주)** |

---

## 부록

### 부록 A. 의사결정 레지스터 (P3)

| ID | 결정 | 대안 | 근거 |
|---|---|---|---|
| D1 | 카카오페이 1차 | 토스·네이버 | MAU·안정성 우위 |
| D2 | 알림 우선순위 알림톡→FCM→SMS→이메일 | FCM만 | 국내 수용도 |
| D3 | 주차 어댑터 패턴 | 단일 API 강요 | 국내 시스템 파편화 |
| D4 | 처방전 P3는 Staff 수동 업로드 | 자동 EMR 연동 | EMR 연동은 파트너십 필요(P5) |
| D5 | Live Activity는 향후 | P3 포함 | 웹 단독 불가, Capacitor 래퍼 시점 |
| D6 | 결제 금액 서버 권위 | 클라 전달 | 보안 필수 |
| D7 | 대리결제 토큰 10분 JWT | 영구 토큰 | 유출 피해 최소화 |
| D8 | 결제 레코드 5년 보관 | 무기한/1년 | 전자금융거래법 |

### 부록 B. 파일 생성·수정 체크리스트

**신규**
- `src/services/waitQueue.ts`, `src/services/prescription.ts`, `src/services/payment.ts`, `src/services/notifications.ts`, `src/services/pharmacies.ts`, `src/services/parking/` (여러 어댑터)
- `src/components/hospital/home/WaitQueueWidget.tsx`
- `src/components/hospital/payment/PaymentSheet.tsx`, `PaymentModal.tsx`, `ProxyPayModal.tsx`
- `src/pages/ProxyPayPage.tsx` (`/pay/:token`)
- `src/components/hospital/prescription/PrescriptionDetail.tsx`, `PharmacyPicker.tsx`, `PharmacyQr.tsx`
- `src/components/hospital/more/NotificationSettingsPage.tsx`
- `src/components/staff/CallNextPatientButton.tsx`
- `functions/src/waitQueue/callNext.ts`, `updateAhead.ts`
- `functions/src/payment/readyPayment.ts`, `approvePayment.ts`, `onWebhook.ts`, `refund.ts`
- `functions/src/notifications/dispatcher.ts`, `kakaoAlimtalk.ts`, `fcm.ts`, `sms.ts`
- `functions/src/prescription/issue.ts`, `qrToken.ts`
- `functions/src/parking/*` (어댑터별)
- `public/e2e-payment.html`, `public/e2e-wait-queue.html`

**수정**
- `src/pages/hospital/HospitalShell.tsx` — WaitQueueWidget 추가
- `src/components/hospital/InpatientTab.tsx`, `CheckupTab.tsx` — 실내용 채움
- `database.rules.json` — payments·wait_queue·prescriptions·notifications·pharmacies 추가
- `src/types/*` — 관련 타입
- 개인정보 처리방침·이용약관 (신규 md)

### 부록 C. Phase 관계 다이어그램

```
 Phase 2 (완료)              Phase 3 (본 문서)                 Phase 4
 ───────────                  ───────────────                  ────────
 HospitalShell + 6 tabs       + WaitQueueWidget (홈)          고령자 모드
 OutpatientTab MVP            + 호출 이벤트 → 안내 탭 자동    OAuth(카카오)
 AnnouncementBanner           + ProxyPayment 활성             TTS 음성안내
 (Proxy CTA placeholder)      + Kakao 알림톡 + FCM            가족 대리권한
 GuideTab                     + 처방전/약국 전송
                              + 주차 어댑터
                              + InpatientTab/CheckupTab 채움
```

### 부록 D. 카카오페이 통합 체크리스트

- [ ] 카카오 개발자 계정 + 앱 등록
- [ ] 카카오페이 사업자 가입 + 심사
- [ ] 샌드박스 계정 발급 (개발 중)
- [ ] Secret Manager에 CID·Admin Key 저장
- [ ] Ready → Approve → Cancel 3개 Function 구현
- [ ] Webhook URL 등록, HMAC 검증 로직
- [ ] 영수증 발급·환불 흐름 테스트
- [ ] 프로덕션 심사 통과 후 키 교체

### 부록 E. 알림톡 템플릿 샘플 (5종 제출용)

| 코드 | 시나리오 | 본문 |
|---|---|---|
| `MW_APPT_CONFIRM` | 예약 확인 | `[MediWay]\n#{name}님, #{date} #{time} #{doctor} 선생님 진료가 예약되었습니다.\n문의: #{phone}` |
| `MW_APPT_REMIND` | 예약 리마인더 | `[MediWay]\n#{name}님, 1시간 뒤 진료가 예정입니다. 도착 후 #{place}에서 접수해 주세요.` |
| `MW_TURN_CALL` | 순번 호출 | `[MediWay]\n지금 #{department}로 이동해 주세요. #{roomName}에서 진료가 시작됩니다.` |
| `MW_PROXY_PAY` | 대리결제 요청 | `[MediWay]\n#{name}님이 진료비 결제를 요청했습니다.\n결제: #{link}\n(10분 내 만료)` |
| `MW_RX_SENT` | 처방 약국 전송 | `[MediWay]\n처방전이 #{pharmacy}에 전송되었습니다. 영업시간을 확인해 방문하세요.` |

### 부록 F. 학습 리소스

- Kakao Pay 온라인 결제 API: https://developers.kakaopay.com/docs/payment/online
- Kakao 비즈메시지(알림톡): https://business.kakao.com/info/bizmessage/
- Firebase Functions v2 Secret Manager: https://firebase.google.com/docs/functions/config-env#params
- Web Push Protocol (VAPID): https://web.dev/notifications/
- FCM for Web: https://firebase.google.com/docs/cloud-messaging/js/client
- 전자금융거래법 가이드: 금융위원회 법령정보
- 개인정보보호법 처리방침 가이드: https://www.privacy.go.kr
- Capacitor Live Activities(참고): https://capacitorjs.com/docs/

---

_작성일: 2026-04-22_
_대상 Phase: #3 — 고수요 편의 기능_
_선행: `PlusUltra#1.md`, `PlusUltra#2.md`_
_이어지는 문서: `PlusUltra#4.md` (고령자·접근성·OAuth·가족 대리)_
_UIUX 참조: `uiux/mobile_uiux/mediway_user_main/`, `mediway_qr/`, `mediway_staff_*/`, `uiux/*/mediway_clinical/DESIGN.md`_
