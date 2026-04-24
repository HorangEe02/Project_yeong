# PlusUltra #5 — 고급 확장 (검사결과·메시지·문진·PHR·다국어) 상세 구현 가이드

> **Phase 5 기능 설명서 + 구현 가이드라인**
> 범위: 검사결과 무기한 보관 · 진료 전 디지털 문진 · 의료진 메시지 · 나의건강기록(PHR) 연동 · 보험 청구 지원 · 다국어 i18n
> 예상 기간: **3~6개월 이상** (1인 풀타임 + 파트너십 외부 의존). 내부 구현만 놓고 보면 5~6주
> 선행 요건: **Phase 1~4 완료** — multi-tenant · 대시보드 · 알림 · 결제 · 접근성이 모두 안정화되어 있어야 함

---

## 목차

- [起 — 왜 지금 "고급"인가](#起--왜-지금-고급인가)
- [承 — 설계 원칙과 기술 선택](#承--설계-원칙과-기술-선택)
- [轉 — 세부 구현 설계](#轉--세부-구현-설계)
  - [1. 검사 결과 무기한 보관 (F3)](#1-검사-결과-무기한-보관-f3)
  - [2. 진료 전 디지털 문진 (F4)](#2-진료-전-디지털-문진-f4)
  - [3. 의료진 메시지 (F11)](#3-의료진-메시지-f11)
  - [4. PHR 연동 — 나의건강기록 (F14)](#4-phr-연동--나의건강기록-f14)
  - [5. 보험 청구 지원](#5-보험-청구-지원)
  - [6. 다국어 i18n (F18)](#6-다국어-i18n-f18)
  - [7. 데이터 스키마 확장](#7-데이터-스키마-확장)
  - [8. 보안 규칙 확장](#8-보안-규칙-확장)
  - [9. 규제·법률 대응](#9-규제법률-대응)
- [結 — 완료 기준·검증 전략·이후](#結--완료-기준검증-전략이후)
- [UIUX 가이드라인](#uiux-가이드라인)
- [부록](#부록)

---

## 📌 v2 업데이트 (2026-04-22)

> **이 파일은 PlusUltra v1 상세 가이드입니다.** v2 기준 문서 `GUIDE_v2/plusultra_v2.md` §Phase 5가 최종 실행 기준이며, 충돌 시 **v2가 우선**합니다.

### Phase 5 v2 조정사항 — 대규모 재우선순위화

#### 🔥 실행 순서 재정의

v1은 섹션 순서(§1 검사결과 → §2 문진 → §3 메시지 → §4 PHR → §5 보험 → §6 다국어)로 암묵적 우선순위 부여. **v2는 MOAT 기반으로 전면 재배열**:

| v2 순서 | 기능 | 변경 사유 |
|---|---|---|
| 🥇 1 | **검사결과 무기한 보관 (F3)** | 세브란스 1년 제한 정면 차별화 — MOAT #3 |
| 🥈 2 | **실손 청구 자동화** | 한국 유저 고통 1위 — 킬러 기능 승격 (v1 한 줄 언급 → v2 독립) |
| 🥉 3 | **PHR 연동 (F14)** | 나의건강기록 2025 FHIR R4 안정화, 파트너십 타이밍 적기 |
| 4 | 디지털 문진 (F4) | EMR 벤더 확보 후에만 착수 — **후순위** |
| 5 | **의료진 메시지 (F11) — 법무 조건부** | ⚠️ 2024 법개정 후에도 "원격진료" 경계 모호. **Drop 가능 설계** |
| 6 | 다국어 (F18) — **Tier 2 연기** | 중소병원 파일럿 ROI 낮음. 외국인 환자 다수 Tier 1 병원 요청 시에만 |

#### 주요 조정

| # | 조정 | v1 대비 | 영향 섹션 |
|---|---|---|---|
| 1 | 🥇 **§1 검사결과 무기한 P5 1순위 착수** | v1은 §1이지만 우선순위 명시 안 함 | §1. 검사결과 — 가장 먼저 구현. "세브란스 1년 제한 극복"을 핵심 영업 메시지로 |
| 2 | 🔥 **실손 청구 자동화 킬러 기능 승격** | v1 §5는 한 줄 수준 | §5. 보험 청구 — **독립 기능으로 본격 확장**. 1단계: 진단서·영수증·세부내역서 자동 묶음 PDF 다운로드. 2단계: 보험사 API 직접 제출 (삼성화재·KB·현대해상·메리츠). MOAT #2 |
| 3 | ⚠️ **의료진 메시지 (F11) 법무 게이트** | v1은 정식 포함 | §3. 의료진 메시지 — **법무 검토 Go/No-Go 게이트 추가**. 통과 조건: ① 병원 법무팀 확인서 ② 처방·진단 키워드 자동 차단 ③ 응답 SLA 명시 ④ PHI 최소 수집. 실패 시 **Drop 또는 단순 FAQ 게시판**으로 축소 |
| 4 | ⏸ **다국어 (F18) Tier 2 연기** | v1은 P5 포함 | §6. 다국어 — **P5 기본 스코프에서 제외**. Tier 1 대형 병원(외국인 환자 다수) 파일럿 요청 시 별도 sprint |
| 5 | 🆕 **F20 Apple Watch 실시간 · 의료진 공유 (P4 확장)** | v1에 없음 | **신규 섹션**: P4에서 읽기만 했던 바이탈을 실시간 구독 + 의료진 메시지로 확장. 심박 이상 → 앱 알림 → 의료진 메시지 or 응급 버튼 트리거 |

### MOAT 강조 (검사결과 무기한 + 실손 청구)

| MOAT | Phase | 영업 메시지 |
|---|---|---|
| 검사결과 무기한 (F3) | P5 1순위 | "세브란스는 1년, MediWay는 **무기한**" |
| 실손 청구 자동화 | P5 2순위 | "진단서·영수증 자동 묶음 → 원터치 제출" |

가족 대리(P4) + 이 두 MOAT가 **MediWay 3대 차별화 축**. 영업 자료에서 이 순서로 노출.

### 의료진 메시지 법무 체크리스트

게이트 통과 시에만 Go:

- [ ] 병원별 법무팀 서면 확인 (의료법 "원격진료" 해석 분리)
- [ ] 처방·진단 관련 키워드 자동 감지·차단 (LLM moderation 또는 룰 기반)
- [ ] "응답 SLA 24시간" 같은 약속은 병원별 설정, UI에 명시
- [ ] PHI 최소 수집 (질문 본문에 개인정보 최소화 안내)
- [ ] "진료 대체 아님" 고지 UI 상시 노출
- [ ] 수퍼바이저(의료진 관리자) 모든 스레드 audit 가능

게이트 실패 시: **기능 자체를 Drop**하거나 **단순 FAQ 게시판**(의료진 답변 O, 양방향 X)으로 축소.

### 적용 원칙

- FHIR R4 · OAuth2 PKCE · Cloud KMS · i18next 기술 · 동적 JSON Schema 문진: **v1 원안 준수**
- 실행 순서 · 의료진 메시지 법무 게이트 · 실손 청구 격상 · 다국어 연기 · Apple Watch 확장: **v2 기준**
- 의심 시 `GUIDE_v2/plusultra_v2.md` §"Phase 5" 및 §"부록 A. MOAT 랭킹" 확인

---

## 起 — 왜 지금 "고급"인가

### P4 종료 시점의 위치

Phase 4 완료 시 MediWay는 **"내 병원 앱"**으로 기능적 완성도가 높은 상태다:
- 여러 병원 지원 · 대시보드 · 외래/입원/검진 · 길찾기 · 결제 · 대기 · 알림 · 고령자 · 가족 대리

그러나 **"의료 정보 허브"**로서는 아직 빈약하다. 환자 입장에서:
- 검사결과를 앱으로 볼 수 없음 (진료내역 기록 부재)
- 진료 때마다 종이 문진 반복
- 의료진과 비동기 소통 불가 → 전화로만 문의
- 다른 병원 이력은 단절
- 보험 청구는 여전히 종이·팩스

MyChart가 지배적인 이유는 **"모든 의료 정보가 한 앱에 있다"**는 점이다. P5는 MediWay를 **의료 정보 플랫폼**으로 끌어올리는 단계다.

### 시장 벤치마크 회상
- 세브란스: 검사결과 강점, but **1년 제한** ← **MediWay 무기한으로 정면 차별화**
- MyChart: 의료진 메시지·크로스 조직 이력 = 가장 "끈끈한" feature
- 나의건강기록: 복지부 공식 PHR, 표준 FHIR
- 다국어: 외국인 환자(연 100만+)·의료관광 수요

### 파트너십 의존성

Phase 5는 Phase 1~4와 다르게 **"내부 개발만으로 완결 불가"**:
- EMR 연동은 병원별 벤더 계약 필요 (굿닥·메디블록·이지케어텍 등)
- 나의건강기록 API는 보건복지부·한국보건의료정보원과 협약
- 실손 청구 자동화는 손해보험사 API (삼성화재·KB·현대해상) 각각 협약
- 템플릿 심사·법무 검토 등 외부 일정 다수

**P5는 단일 스프린트가 아니라 "6개월 로드맵"이다.** 이 문서는 내부 구현·설계를 완성하여 파트너십 속도에 맞게 출시할 수 있도록 **사전 준비**하는 것이 목표.

### Phase 5의 4대 가치

1. **의료 정보 허브화** — 단순 안내를 넘어 "내 건강의 중심"이 됨
2. **끈끈한 사용자 lock-in** — 검사결과·메시지는 5년+ 축적
3. **MyChart 수준의 국내 대안** — 국내 중소 병원 SaaS로 포지셔닝
4. **글로벌 확장 기반** — 다국어로 외국인 환자·의료관광 시장 진입

---

## 承 — 설계 원칙과 기술 선택

### 원칙 10계명

1. **의료 데이터는 최소 수집, 최대 보호** — 필요한 것만, 암호화 저장
2. **무기한 보관은 사용자 선택** — 자동 삭제 옵션 병행
3. **FHIR 표준 선호** — 이후 PHR 연동·의료기관 간 상호운용
4. **문진·메시지는 비공식 소통 경계** — "진단·처방 대체 아님" 명시
5. **EMR 어댑터 패턴** — 주차와 동일. 병원별 구현체 교체
6. **다국어는 별도 데이터·콘텐츠** — UI 문자열뿐 아니라 POI·부서명·공지도 번역 가능
7. **모든 PHI 접근은 audit log** — HIPAA 수준 지향
8. **외부 연동 실패 투명화** — "현재 EMR 연동이 불안정합니다" 상태 배지
9. **문진 답변은 서버 검증** — 허위 입력 방지
10. **메시지 SLA 존중** — "24시간 내 답변" 같은 약속은 병원별 설정

### 기술 스택 선택 근거

| 영역 | 선택 | 대안 | 이유 |
|---|---|---|---|
| 검사결과 저장 | **Firebase Storage (AES-256) + 메타 Firestore/RTDB** | Object storage in-house | 규제 대응 + 기존 스택 |
| EMR 연동 | **어댑터 패턴 + FHIR R4 (있으면)** | 병원별 프로토콜 고정 | 확장성 |
| 문진 | **동적 스키마 (JSON Schema) + 조건부 분기** | 하드코딩 | 병원별 차이·다국어 |
| 메시지 | **RTDB 실시간 + SLA 타이머 Scheduler** | Firestore | 기존 스택, RTDB 저지연 |
| PHR | **나의건강기록 FHIR API + OAuth2** | 직접 스크레이핑 | 공식 API만 지원 |
| 보험 청구 | **PDF 생성 + 보험사 API** | 수동 접수 | 자동화 가치 |
| 다국어 | **`react-i18next` + ICU MessageFormat** | 자체 구현 | 커뮤니티·도구 |
| 콘텐츠 번역 | **Hospital별 `translations/{locale}` 서브트리** | 별도 CMS | 단순, 병원 관리자 편집 |
| 자동 번역 (보조) | **Google Cloud Translate API + 사람 검수** | 자동만 | 의료 정확도 |
| 문서 생성 | **`pdf-lib` or Puppeteer headless** | 서버 PDF SaaS | 제어·비용 |
| Encryption at rest | **Cloud KMS + envelope encryption** | 자체 키 관리 | 감사·회전 |

### 필요 선행 지식

| 분야 | 깊이 | 핵심 |
|---|---|---|
| Phase 1-4 산출물 | 완전 이해 | 인프라·알림·결제·가족 |
| FHIR R4 기본 | **실무 수준 권장** | Patient·Observation·DocumentReference·Condition resource |
| OAuth2 Authorization Code + PKCE | 실무 | 나의건강기록 연동 시 표준 |
| Firebase Storage + Custom Metadata | 실무 | 암호화, access token |
| Cloud KMS + Envelope Encryption | 기본 | 열쇠 회전, 감사 |
| `react-i18next` + ICU 플랜 | 실무 | 복수·성별·날짜 포맷 |
| 의료법 광고·비대면 진료 규정 | 기본 | 메시지가 "진료 행위" 경계에 닿지 않도록 |
| 전자문서법 (공인전자서명) | 참고 | 보험 청구 진단서 서명 |

### 위험 조기 식별

| 위험 | 영향 | 완화 |
|---|---|---|
| EMR 벤더 API 제공 거부 | 병원별 기능 파편 | Staff 수동 업로드 UI를 항상 지원하는 fallback |
| 나의건강기록 협약 지연 (월 단위) | PHR 기능 출시 연기 | P5 초반부에 착수. 협약 전 로컬 타임라인 기능만 먼저 |
| 메시지가 "진료 행위"로 해석 | 의료법 위반 | 문구·스코프 명확화, 면책 고지, 처방·진단 불허 |
| 무기한 보관 = 규제 위반 가능성 | 사용자 데이터 보존 의무/권리 충돌 | 개인정보 보존·파기 기준 명시 (PIPA 시행령), "사용자 요청 시 삭제" 우선권 |
| 다국어 번역 오류 → 환자 오해 | 안전 이슈 | 의학 용어는 원어 + 쉬운 번역 병기, 최종은 의료 번역가 검수 |
| 보험사 API 각자 다름 | 통합 복잡 | 1개 보험사 우선 (삼성화재·KB 중) 파일럿 |
| FHIR 구현 오류 | PHR 거절 | 공식 FHIR validator 통과 기준화 |

---

## 轉 — 세부 구현 설계

### 1. 검사 결과 무기한 보관 (F3)

#### 1.1 데이터 소스

| 소스 | P5 범위 | 설명 |
|---|---|---|
| **A. Staff 수동 업로드** | ✅ MVP | Staff가 진료 시 PDF 업로드 |
| **B. EMR 연동 (push)** | 일부 (파일럿 1개) | EMR이 자동 push (FHIR or 벤더 API) |
| **C. EMR 연동 (pull)** | 설계만 | MediWay가 주기적 pull |
| **D. 환자 자기 업로드** | ✅ 옵션 | 타 병원 결과 보관용 |

#### 1.2 데이터 모델

```
/hospitals/{id}/test_results/{uid}/{resultId}
  kind: "lab" | "imaging" | "pathology" | "report" | "other"
  issuedAt: number
  hospitalName: string
  department: string
  doctorName: string
  title: string                    # "일반혈액검사"
  summary?: string                 # 짧은 요약
  fhir?: { ... }                   # FHIR Observation / DocumentReference (선택)
  attachments: [ { pdfUrl, mimeType, size } ]
  tags: ["정기", "외래"]
  uploadedBy: "staff" | "emr" | "self"
  encryptedMeta: string            # 민감 메타는 AES-256
  createdAt
```

- 복수 첨부 가능 (혈액검사 리포트 + 영상 이미지)
- `encryptedMeta`는 Cloud KMS로 감싼 envelope encryption
- 타 병원 결과는 `/users/{uid}/external_test_results/` 경로에 별도 저장

#### 1.3 저장·암호화

- PDF는 **Firebase Storage `hospitals/{id}/test_results/{uid}/{resultId}/*.pdf`**
- Storage 규칙: 본인·대리 권한자·병원 staff만 read
- URL은 **signed URL** + 10분 만료
- 파일명에 `uid` 노출 금지 (UUID 사용)

#### 1.4 타임라인 UI 위치

- **더보기 → 건강 이력 → 검사 결과** 섹션
- **건강검진 탭** 내부에 병원별 이력
- 필터: 기간·종류·병원·의료진
- 카드 클릭 → 상세 뷰 (PDF 인라인 or 다운로드)

#### 1.5 다운로드·공유

- PDF 다운로드 (signed URL)
- 공유: 카카오톡으로 특정 수신자에게 전송 (링크는 10분 만료 일회용)
- 가족 대리(delegate) 권한자도 열람 가능 (P4 연계)

#### 1.6 검색

- 제목·요약·태그 기반 클라이언트 검색 (MVP)
- 대용량은 Typesense/Algolia (향후)

### 2. 진료 전 디지털 문진 (F4)

#### 2.1 템플릿 스키마 (JSON Schema 유사)

```ts
interface Questionnaire {
  id: string;
  hospitalId: string;
  name: string;
  version: number;
  locale: Record<'ko' | 'en' | 'zh' | 'ja', QuestionnaireContent>;
  questions: Question[];
  createdAt: number;
  validUntil?: number;
}

interface Question {
  id: string;
  type: 'text' | 'number' | 'choice' | 'multiple' | 'scale' | 'date' | 'file';
  required: boolean;
  conditional?: { dependsOn: string; when: unknown };
  meta?: Record<string, unknown>;
}
```

- 변경 시 **version 증가 + 이전 답변은 immutable**
- `conditional`: 특정 답변 선택 시에만 표시

#### 2.2 예시 (고혈압 재진 문진 일부)

```jsonc
{
  "questions": [
    { "id": "bp_systolic", "type": "number", "required": true,
      "meta": { "min": 60, "max": 240, "unit": "mmHg",
                "label": { "ko": "최근 1주 평균 수축기 혈압" }}},
    { "id": "bp_medications_taken", "type": "choice", "required": true,
      "meta": { "options": ["매일", "가끔", "안 먹음"] }},
    { "id": "side_effects", "type": "multiple",
      "conditional": { "dependsOn": "bp_medications_taken", "when": "가끔" },
      "meta": { "options": ["어지럼", "기침", "두통", "없음"] }}
  ]
}
```

#### 2.3 트리거·제출

- 예약 24시간 전 푸시 알림 + 알림톡 (P3 알림 인프라 재활용)
- 제출 시 서버 측 validation (범위·필수) + 타임스탬프
- Staff 콘솔에 환자 답변 **구조화 뷰** 노출
- 제출 없이 내원 → Staff가 현장 체크 모드로 진입

#### 2.4 답변 저장

```
/hospitals/{id}/questionnaire_responses/{uid}/{respId}
  questionnaireId
  version
  appointmentId?
  submittedAt
  answers: { [qid]: value }
  locale: "ko"
```

#### 2.5 관리자 편집 UI

- Hospital admin 콘솔에 "문진 템플릿" 페이지
- 시각적 빌더(드래그·드롭) 지양, **JSON 편집 + 실시간 미리보기** MVP
- 주요 템플릿은 플랫폼이 제공(고혈압·당뇨·감기 등), 병원이 fork하여 편집

### 3. 의료진 메시지 (F11)

#### 3.1 범위와 경계

- **허용**: 증상 문의, 복약 확인, 검사 결과 해석 질문, 재예약 문의
- **금지**: 원격 진단, 처방 요청 (의료법·비대면진료 규정)
- 대화 상단 **면책 고지** 상시 노출: "이 메시지는 진료·처방 대체가 아닙니다."

#### 3.2 SLA·영업시간

- 병원별 설정: 답변 SLA (24h·48h·7d), 영업시간
- 응답 기대치 안내: "평일 24시간 이내" 등
- Staff 불가 시 전환: "급하신 경우 대표 전화로 문의하세요"

#### 3.3 데이터 모델

```
/hospitals/{id}/threads/{threadId}
  patientUid
  participantStaffUids: [uid]
  topic: string
  status: "open" | "waiting_staff" | "waiting_patient" | "closed"
  lastMessageAt
  slaDeadline?                # lastPatientMessage + SLA

/hospitals/{id}/threads/{threadId}/messages/{msgId}
  senderUid
  senderRole: "patient" | "staff"
  body: string
  attachments?: [ fileRef ]
  createdAt
  readAt?
```

#### 3.4 실시간 + Push

- RTDB `onValue`로 스레드·메시지 구독
- 새 메시지 도착 시 Push + 알림톡 (병원 설정)
- Staff 대시보드에 "답변 대기 중 스레드" 리스트 + SLA 임박 경고

#### 3.5 첨부

- 사진·PDF 첨부 가능 (검사결과 공유에 유용)
- Storage 업로드, signed URL 저장

#### 3.6 스레드 종료

- Staff가 "종료" → `status: closed`. 환자가 새 질문 시 새 스레드
- 자동 종료: 마지막 메시지로부터 7일 무응답 (병원 설정)

### 4. PHR 연동 — 나의건강기록 (F14)

#### 4.1 나의건강기록이란
- 보건복지부 + 한국보건의료정보원이 운영하는 공식 개인 건강 이력 서비스
- FHIR R4 표준 기반
- 사용자가 동의하면 앱은 타 병원 이력을 읽을 수 있음

#### 4.2 연동 플로우

1. 사용자가 MediWay에서 "나의건강기록 연동" 선택
2. OAuth2 Authorization Code + PKCE로 나의건강기록 로그인
3. 사용자가 MediWay에 접근 권한 승인 (범위 선택: 진료기록·검사결과·처방 등)
4. MediWay가 access_token·refresh_token 수령
5. `/users/{uid}/phr/external/*`에 import

#### 4.3 import 범위

- 의료기관 방문 내역
- 처방약
- 검사 결과 요약
- 예방접종 기록

원본 FHIR 데이터는 `fhir_raw`에 보관, MediWay 내부 모델로 매핑된 사본은 `normalized`에.

#### 4.4 통합 타임라인

- "내 건강 이력" 페이지 (더보기 탭 내부)
- 시계열 정렬: MediWay 병원 이력 + PHR import 데이터
- 아이콘으로 출처 구분 (MediWay 병원 vs PHR)

#### 4.5 주기적 갱신

- 30일마다 refresh_token으로 재조회
- 사용자에게 "새 이력 3건" 알림

#### 4.6 연동 해제

- 사용자 요청 시 token revoke + import 데이터 삭제

### 5. 보험 청구 지원

#### 5.1 범위

- **실손보험 청구**: 진단서 + 진료비 영수증 + 진료세부내역서 + 처방전을 자동으로 묶어 보험사에 제출
- **건강보험 자격 조회**: 건보공단 API 연동

#### 5.2 흐름

1. 결제 완료 후 "실손 청구" CTA
2. 청구 서류 자동 수집 (Storage에서 PDF 조합)
3. 보험사 선택 (사용자 즐겨찾기 or 검색)
4. 보험사 API로 전자 제출
5. 심사 상태 tracking

#### 5.3 전자서명

- 진단서 전자서명 필요 시 staff 공인전자서명
- 환자 동의 서명은 캔버스 드로잉

#### 5.4 보험사 어댑터

- 주차·EMR과 동일 패턴
- 1차 파일럿 보험사 1개

### 6. 다국어 i18n (F18)

#### 6.1 지원 언어

- 한국어 (기본)
- 영어
- 중국어 (간체)
- 일본어

#### 6.2 UI 텍스트

- `react-i18next`, `ICU MessageFormat`
- `src/locales/{ko,en,zh,ja}/common.json`
- 네임스페이스: `common`, `home`, `outpatient`, `guide`, `payment` 등
- 번역 누락 시 fallback = ko

#### 6.3 콘텐츠 번역

- Hospital 별 POI·부서·공지 등도 번역 필요
- `/hospitals/{id}/i18n/{locale}/...` 서브트리
- 병원 관리자 UI에서 편집
- 자동 번역 보조: Google Cloud Translate API → 사람 검수 단계 필수

#### 6.4 언어 감지·선택

1. 사용자 설정 (더보기 → 언어)
2. URL 파라미터 `?lang=en`
3. `navigator.language`
4. 기본 한국어

#### 6.5 화면 요소 영향

- 날짜 포맷 (`Intl.DateTimeFormat(locale)`)
- 숫자·통화 (`Intl.NumberFormat`)
- 전화번호: 국제 포맷 옵션
- RTL 고려 없음 (지원 언어 모두 LTR)

#### 6.6 테스트 전략

- Pseudo-localization (`[TestTest-테스트]`) 로 긴 문자열 깨짐 감지
- 번역 커버리지 100% 체크 스크립트

### 7. 데이터 스키마 확장

```
/hospitals/{id}/test_results/{uid}/{resultId}
/hospitals/{id}/questionnaires/{qId}
/hospitals/{id}/questionnaire_responses/{uid}/{respId}
/hospitals/{id}/threads/{threadId}
/hospitals/{id}/threads/{threadId}/messages/{msgId}
/hospitals/{id}/i18n/{locale}/...

/users/{uid}/phr/external/...
/users/{uid}/insuranceClaims/{claimId}
/users/{uid}/language                            # 선호 언어
/users/{uid}/externalTestResults/...

/audit_logs/{hospitalId}/phi_access/{id}         # 검사결과·메시지 접근 로그
```

### 8. 보안 규칙 확장

핵심:
- `test_results/{uid}`: 본인 + hospital staff/admin + family delegate 권한
- `questionnaire_responses/{uid}`: 본인 + staff
- `threads/{threadId}`: 환자 본인 + 참여 staff
- 첨부 Storage: signed URL + 10분
- audit log 쓰기는 Cloud Function만 (클라이언트 쓰기 불가)

### 9. 규제·법률 대응

#### 9.1 개인건강정보 보호
- PIPA "민감정보" 해당 — 별도 동의 필수
- 암호화 저장·전송, 접근 로그 감사

#### 9.2 의료법
- 메시지·문진이 **진단·처방 대체가 아님** 명시
- 비대면 진료는 재진·만성질환 한정 (현행 시행 규칙)
- 광고성 콘텐츠 금지

#### 9.3 전자의무기록(EMR) 관련
- EMR에서 pull·push하는 경우 병원과 데이터 처리 계약 필요
- EMR 데이터는 **병원 소유** — MediWay는 위탁 처리자
- 파기 요청 시 즉시 이행

#### 9.4 보험업법
- 실손 청구 대행은 전자문서 제출 가능 (보험업법·의료법 정리 완료된 기업체 기준)
- 필요 시 보험 청구 대행 허가·계약

#### 9.5 다국어 규제
- 의료 광고 규정은 언어별 동일 적용
- 중문·일문 번역 시 현지 의료 표현 주의

---

## 結 — 완료 기준·검증 전략·이후

### 완료 기준 (세부화)

#### 기능 (내부 범위)
- [ ] Staff 수동 업로드로 검사결과 PDF 업로드 → 환자 앱에서 조회/다운로드
- [ ] 검사결과 타임라인이 무기한 노출 (삭제 옵션도 제공)
- [ ] 고혈압 문진 템플릿 작성 → 환자에게 배포 → 답변 수집 → Staff 콘솔 노출
- [ ] 환자-의료진 메시지 스레드 생성 → 양방향 대화 → SLA 체크 → 종료
- [ ] 다국어 토글: 한국어 ↔ 영어 ↔ 중국어 ↔ 일본어 즉시 전환, 핵심 페이지 번역 100%
- [ ] 보험 청구 폼 생성 및 PDF 패키지 다운로드 (보험사 API 없이도 MVP)

#### 파트너십 의존 (시간 걸림)
- [ ] EMR 벤더 1곳과 데이터 파이프라인 연동 (1차 파일럿)
- [ ] 나의건강기록 OAuth 승인 + FHIR import 성공
- [ ] 보험사 1곳 API 연동

#### 보안·규제
- [ ] 모든 PHI 접근에 audit log 기록
- [ ] Cloud KMS 기반 envelope encryption 동작
- [ ] 삭제 요청 시 Storage·DB 동시 정리
- [ ] PIPA 민감정보 동의 UI 및 로그

#### 품질
- [ ] tsc/eslint/build 통과
- [ ] 다국어 번역 커버리지 100% (공통 UI)
- [ ] Lighthouse Accessibility 95+
- [ ] FHIR validator 통과 (import 데이터 테스트셋)

### 검증 전략

1. **자동**
   - 문진 스키마 validator 단위 테스트
   - i18n 커버리지 CI 스크립트 (누락 키 감지)
   - 메시지 RTDB 규칙 E2E (`public/e2e-messages.html`)
   - 검사결과 Storage 규칙 E2E
2. **수동**
   - 의료진 3명에게 메시지 UI 사용성 테스트
   - 외국인 모니터 영/중/일 번역 리뷰
   - 문진 템플릿 편집 UX 리뷰
3. **규제**
   - 법무 검토: 메시지 경계·면책 고지
   - PIPA 민감정보 동의 문구
   - 보험 청구 대행 자문

### 롤백·feature flag

- `VITE_P5_TEST_RESULTS`, `VITE_P5_QUESTIONNAIRE`, `VITE_P5_MESSAGES`, `VITE_P5_PHR`, `VITE_P5_INSURANCE`, `VITE_P5_I18N`
- 파트너십 대기 중인 기능은 off → placeholder UI

### 이후 (Phase 5 이후)

P5 완료 시 MediWay 로드맵은 **"의료 정보 허브"**로 완결. 이후 가능한 확장:
- **AI 건강 코칭** (만성질환 관리, 약 복용 최적화)
- **웨어러블 연동** (Apple Health, Samsung Health)
- **원격 진료 본격화** (법 개정 대응)
- **해외 진출** (일본 의료 tourism 특화 버전)
- **B2B 데이터 플랫폼** (익명화된 건강 데이터를 연구 기관에 제공)

---

## UIUX 가이드라인

### U1. 참조 자산 매핑 (P5 대상)

| 경로 | 대응 P5 화면 |
|---|---|
| `mobile_uiux/mediway_admin/` · `web_page_uiux/mediway_admin/` | Hospital admin의 문진 템플릿 편집 |
| `mobile_uiux/mediway_user_main/` | "건강 이력" 신규 탭 노출 (더보기 내부) |
| `mobile_uiux/mediway_staff_*/`, `web_page_uiux/mediway_staff_v2_*/` | Staff 콘솔에 메시지·문진 섹션 추가 |
| `uiux/*/mediway_clinical/DESIGN.md` | "No-Line Rule", Glassmorphism, 타이포 (다국어 적용 시 세심히 따라야 함) |

목업에 메시지·검사결과 화면은 없다. **Staff 콘솔 확장과 환자 "더보기 → 건강 이력"을 새로 디자인하여 uiux 폴더에 추가** 권장.

### U2. 검사결과 타임라인 UI

#### 모바일

```
┌────────────────────────────────────┐
│ ← 건강 이력                        │
│ ─────────────────────────────────  │
│ 🔍 [검색 · 필터]                    │
│                                    │
│ 2026-04-22                         │
│  ┌──────────────────────────────┐ │
│  │ 🔬 일반혈액검사               │ │
│  │ 내과 · Dr. Sarah             │ │
│  │ [PDF 보기] [공유]             │ │
│  └──────────────────────────────┘ │
│                                    │
│ 2026-03-10                         │
│  ┌──────────────────────────────┐ │
│  │ 📷 흉부 X-ray                 │ │
│  │ 영상의학과 · Dr. Lee          │ │
│  └──────────────────────────────┘ │
└────────────────────────────────────┘
```

- 시간 역순 스택, 날짜 그룹핑
- 종류 아이콘 컬러 다양화 (lab: primary, imaging: tertiary, pathology: secondary)
- 카드 hover/tap 시 상세 sheet

#### 웹

- 2컬럼: 좌측 타임라인, 우측 상세 뷰어
- PDF 인라인 뷰 (`iframe` 또는 `react-pdf`)

### U3. 문진 UI

#### 문진 플로우 (모바일)

- 단계별 질문 한 화면에 하나 (카드 형태, fullscreen)
- 상단 진행도 (bar + "3/10 질문")
- "이전 / 다음" 하단 CTA
- 완료 시 요약 화면 → 제출

#### 웹
- 좌측 진행도 사이드, 우측 질문
- 또는 롱 스크롤 폼 (병원 선택)

#### 관리자 편집

- JSON 좌측 · 미리보기 우측
- 향후 드래그·드롭 빌더 (후속 작업)

### U4. 메시지 UI

#### 환자 측 (모바일)

```
┌────────────────────────────────────┐
│ ← 김선생님에게 문의                 │
│ 내과 · 평일 24시간 이내 답변        │
│ ─────────────────────────────────  │
│ ⚠️ 진료·처방 대체가 아닙니다.      │  면책 배너
│                                    │
│  [환자] 혈압약 복용 후 어지러워요  │
│  10:34                            │
│                                    │
│              [의료진] 어지러움 지속│
│              되면 진료 예약을 권합│
│              니다. 12:10          │
│                                    │
│  [텍스트 입력..................]  │
│  📎 첨부  ✉ 전송                    │
└────────────────────────────────────┘
```

#### Staff 측 (웹)

- 스레드 리스트 (SLA 임박 상단)
- 대화창 · 환자 정보 사이드 패널 (진료 이력·알레르기)

### U5. PHR / 건강 이력 통합 뷰

- 더보기 → 건강 이력
- 탭: 검사결과 / 처방 / 방문 이력 / 예방접종
- 출처 뱃지: `MediWay` / `나의건강기록` 아이콘 구분
- 상세 모달에 원본 FHIR 링크 (고급 사용자)

### U6. 다국어 UI

#### 언어 스위처
- 더보기 → 언어
- 4개 언어 리스트, 선택 시 즉시 새로고침 없이 반영
- **국기 아이콘 + 원어 표기** ("한국어 🇰🇷", "English 🇺🇸", "中文 🇨🇳", "日本語 🇯🇵")

#### 번역 품질 표시
- 의료 용어는 **원어 병기**: "혈압(Blood Pressure)"
- 병원별 번역이 없으면 fallback 언어(한국어) 표시 + "번역 미지원" 작은 뱃지

### U7. 다국어 레이아웃 주의사항

- 긴 문자열: 독일어·일본어가 한국어 대비 1.3~1.8배 길어짐. 버튼은 **min-width만**, max-width 회피
- 영문 대문자 축약 금지 (`OK` → 각 언어 긴 번역)
- 월/요일 포맷은 `Intl.DateTimeFormat` 사용
- 숫자 천단위 구분자: 한국·영어 `,`, 일본·중국 동일, 유럽은 `.`

### U8. 규제성 UI (민감정보 동의)

- 검사결과 무기한 보관 시작 전 동의 모달: 대형·명확 설명
- "동의하지 않으면 검사결과 자동 삭제 (30일 후)" 대안 명시
- 접근 권한·제3자 제공 분리 동의

### U9. 접근성 · 신뢰감

- 메시지·검사결과 섹션은 고대비, 큰 글자 기본
- PHI 화면은 스크린 capture 경고 배너 (선택)
- 민감 데이터 감사 로그 사용자 본인도 열람 가능 ("내 정보에 누가 접근했는지 보기")

### U10. 피해야 할 함정

1. **문진을 모든 사용자에게 필수** — 고령자 부담. 선택으로 제공
2. **메시지에 의료진 실명 공개** — 개인정보 이슈. 닉네임·직책만
3. **다국어 번역을 자동 번역만** — 의료 오역 위험. 검수 필수
4. **PHR 연동 동의 UI를 간소화** — PIPA 위반. 범위별 세분 체크
5. **검사결과 PDF URL을 사전 공개** — 절대 금지. 항상 signed URL
6. **보험 청구 자동화 문구가 상담 수준 조언** — 의료법·보험업법 경계
7. **Staff 메시지 응답을 앱 강제** — 의료진 워크로드. 지연 투명화
8. **다국어 폰트 부족** — CJK 4종 로드하면 용량 폭발. `font-display: swap` + 서브셋
9. **FHIR 필드를 UI에 그대로 노출** — "observation.valueQuantity.unit" 등 기술 용어는 사용자 친화 번역 필수

### U11. 구현 체크리스트 — UIUX

- [ ] 검사결과 타임라인 날짜 그룹핑·종류 아이콘 분리
- [ ] PDF 인라인 뷰어 (웹) / 외부 뷰어 (모바일)
- [ ] 문진 fullscreen 단계 흐름 + 진행도
- [ ] 관리자 문진 편집기 JSON ↔ 미리보기
- [ ] 메시지 면책 고지 상단 고정
- [ ] 메시지 SLA 임박 시 Staff 강조 표시
- [ ] 4개 언어 스위처 + 즉시 반영
- [ ] 의료 용어 원어 병기
- [ ] PHR 통합 타임라인 출처 뱃지
- [ ] 민감정보 동의 모달 범위별 체크박스
- [ ] Lighthouse Accessibility 95+ (다국어 포함)

### U12. 작업 견적 (UIUX 포함)

| 작업 | 소요 |
|---|---|
| 검사결과 저장 스키마·Storage 규칙·업로드 Function | 2.5일 |
| 검사결과 UI (타임라인·상세·PDF 뷰어) | 2.0일 |
| 문진 스키마·관리자 편집 UI·환자 풀로우 | 3.0일 |
| 메시지 RTDB·SLA 스케줄러·Staff 콘솔 | 3.0일 |
| PHR FHIR 파서·import·정규화 | 3.0일 |
| PHR 통합 타임라인 UI | 1.5일 |
| 보험 청구 패키지 PDF 생성 | 1.5일 |
| 보험사 1곳 API 어댑터 (파일럿) | 2.0일 |
| i18n 프레임워크 구축 · 4언어 리소스 작성(공통) | 3.0일 |
| 병원별 콘텐츠 번역 관리 UI | 1.5일 |
| 규제 문서·민감정보 동의 UI | 1.5일 |
| 규칙·E2E·FHIR validator 통과 | 1.5일 |
| 사용자 연구·번역 검수 | 2.0일 |
| 회귀·UIUX QA | 1.0일 |
| **합계 (내부 개발분)** | **28.0일 (≈ 6주)** |
| 파트너십 의존 (EMR·PHR·보험사) | **+월 단위** |

---

## 부록

### 부록 A. 의사결정 레지스터 (P5)

| ID | 결정 | 대안 | 근거 |
|---|---|---|---|
| D1 | 검사결과 무기한 + 사용자 삭제 옵션 | 자동 파기 | "세브란스 1년 제한" 차별화 |
| D2 | EMR 연동은 어댑터 패턴 | 단일 API | 벤더 파편화 |
| D3 | 메시지는 비진료 행위 한정 | 원격진료 허용 | 의료법 리스크 |
| D4 | PHR는 OAuth2 PKCE | 다른 인증 | 공식 표준 |
| D5 | 다국어 4개 우선 | 더 많은 언어 | 외국인 환자 수 비례 |
| D6 | 자동 번역 + 사람 검수 | 자동만 | 의료 정확도 |
| D7 | 문진 템플릿 JSON Schema | UI 빌더 | MVP 단순 |
| D8 | Cloud KMS envelope encryption | AWS KMS | Firebase 생태계 |
| D9 | 보험 청구 1개사 파일럿 | 전부 | 검증 먼저 |

### 부록 B. 파일 생성·수정 체크리스트

**신규**
- `src/services/testResults.ts`, `questionnaires.ts`, `messages.ts`, `phr.ts`, `insurance.ts`, `i18n.ts`
- `src/components/health/TestResultsTimeline.tsx`, `TestResultDetail.tsx`, `UploadDialog.tsx`
- `src/components/questionnaire/QuestionnaireRunner.tsx`, `QuestionnaireBuilder.tsx`
- `src/components/messages/ThreadList.tsx`, `MessageView.tsx`, `ComposeBar.tsx`, `DisclaimerBanner.tsx`
- `src/components/phr/HealthTimeline.tsx`, `SourceBadge.tsx`
- `src/components/insurance/ClaimForm.tsx`
- `src/components/i18n/LanguageSwitcher.tsx`
- `src/locales/{ko,en,zh,ja}/*.json`
- `functions/src/testResults/upload.ts`, `signUrl.ts`
- `functions/src/questionnaires/validate.ts`
- `functions/src/messages/slaTimer.ts`, `autoClose.ts`
- `functions/src/phr/oauth.ts`, `importFhir.ts`, `refresh.ts`
- `functions/src/insurance/buildPackage.ts`, `submitToInsurer.ts`
- `functions/src/i18n/translateContent.ts` (GC Translate)
- `public/e2e-messages.html`, `e2e-test-results.html`, `e2e-phr.html`

**수정**
- `src/components/hospital/MoreTab.tsx` — 건강 이력·언어 설정 항목
- `src/components/hospital/InpatientTab.tsx`, `CheckupTab.tsx` — 검사결과 섹션 연결
- `src/components/staff/*` — 메시지 인박스·문진 뷰어
- `database.rules.json` — 전면 확장 (test_results·questionnaires·messages·phr)
- `storage.rules` — 첨부·검사결과 파일 규칙
- 개인정보 처리방침·이용약관 전면 개정

### 부록 C. Phase 관계 다이어그램

```
 Phase 4 (완료)                Phase 5 (본 문서)
 ───────────                   ───────────────
 SeniorMode · TTS · OAuth       + 검사결과 무기한
 Emergency · Family              + 문진 템플릿
 Audit logs                      + 의료진 메시지 (SLA)
                                 + PHR(FHIR) 연동
                                 + 보험 청구 자동화
                                 + 다국어 (ko/en/zh/ja)
                                 + Staff 콘솔 확장

 P5 완료 → MediWay = "의료 정보 허브"
```

### 부록 D. EMR 연동 패턴 요약

| 패턴 | 설명 | 예시 |
|---|---|---|
| Push | EMR이 MediWay Webhook에 POST | 검사결과 생성 시 |
| Pull | MediWay가 주기적으로 EMR API 호출 | 매시간 신규 결과 조회 |
| Batch | 야간 배치 파일 전송 | SFTP CSV/HL7 |
| Manual | Staff가 PDF 업로드 | fallback / 파일럿 초기 |

### 부록 E. FHIR 매핑 예시

| FHIR Resource | MediWay 모델 |
|---|---|
| `Patient` | `User` |
| `Appointment` | `Appointment` |
| `Observation` | `TestResult.fhir.observation` |
| `DocumentReference` | `TestResult.attachments` + `fhir` |
| `MedicationStatement` | `Prescription` |
| `Immunization` | `HealthTimelineItem` |

### 부록 F. 학습 리소스

- FHIR R4 Specification: https://hl7.org/fhir/R4/
- 나의건강기록 OpenAPI: https://www.k-his.or.kr/devGuide
- `react-i18next`: https://react.i18next.com
- ICU MessageFormat: https://unicode-org.github.io/icu/userguide/format_parse/messages/
- Firebase Cloud KMS (envelope encryption): https://cloud.google.com/kms/docs/envelope-encryption
- Google Cloud Translation API: https://cloud.google.com/translate
- `pdf-lib`: https://pdf-lib.js.org
- 의료법·의료광고 심의 기준: 보건복지부 자료
- 전자문서·전자서명법 요약: 행정안전부 전자정부 포털

---

_작성일: 2026-04-22_
_대상 Phase: #5 — 고급 확장 (의료 정보 허브)_
_선행: `PlusUltra#1.md`~`PlusUltra#4.md`_
_이어지는 단계: 본 Phase 이후 AI 건강 코칭 · 웨어러블 · 원격진료 · 해외 확장 검토_
_UIUX 참조: `uiux/mobile_uiux/mediway_admin/`, `uiux/web_page_uiux/mediway_admin/`, `mediway_staff_v2_*/`, `uiux/*/mediway_clinical/DESIGN.md`_
