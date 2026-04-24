# MediWay · Plus Ultra 계획 (Multi-Tenant SaaS 전환)

> 단일 데모 병원 → **여러 병원과 계약하는 화이트라벨 SaaS**로 전환하고, 단순 길찾기에서 **병원별 맞춤 대시보드**로 확장하기 위한 Phase별 상세 구현 계획.

## 0. 전체 비전

### 목표
1. **계약 병원 다수를 하나의 플랫폼으로 운영** — 공통 코어 + 병원별 브랜딩/설정
2. **환자에게는 "내 병원 앱"** — 로그인 후 소속 병원의 대시보드로 자연 진입
3. **의료진에게는 업무용 콘솔** — 소속 병원 범위 내에서 세션·계획 관리
4. **플랫폼 관리자(MediWay 운영사)** — 병원 온보딩·계약·감사

### 핵심 원칙
- **Single codebase, per-tenant config** — 병원별 fork 금지
- **데이터 격리는 보안 규칙으로 강제** — `hospitalId` 기반 RTDB 규칙
- **점진적 출시** — P1 완료 시점에도 단일 병원 모드가 깨지지 않아야 함
- **접근성 우선** — 고령 사용자가 앱의 절반 이상 차지한다는 가정으로 설계
- **시장 앱 단점 학습** — 세브란스·서울아산 "잦은 오류", MyChart "복잡성", 똑닥 "실시간 대기" 차별점 흡수

### 범위
5개 Phase × 총 ~10-14주 (1인 풀타임 기준, 병렬화 시 축소)

---

## Phase 1 — Multi-Tenant 기반 (1~2주)

**목적**: 단일 데모 병원 하드코딩을 제거하고, 복수 병원을 수용할 수 있는 스키마·라우팅·인증 기반 마련.

### 1.1 데이터 모델 (RTDB)

```
/hospitals/{hospitalId}
  profile:
    name:           string                # "MediWay 데모 병원"
    slug:           string                # "demo" (URL용)
    logoUrl:        string
    themeColor:     string                # "#004e9f"
    contractStatus: "active" | "pilot" | "paused"
    features:       {                     # per-hospital feature flags
      appointments: true,
      inpatient:    false,
      checkup:      true,
      payment:      false
    }
    createdAt: number
  floor-plans/{level}   # P1에서는 기존 정적 데이터 마이그레이션만
  pois/                 # 동일
  staff-codes/
  departments/          # {id, name, location, floorLevel}
  announcements/        # 공지

/users/{uid}
  primaryHospitalId: string
  hospitalIds:       [h1, h2]
  role:              "patient" | "staff" | "admin" | "platformAdmin"
  hospitalRoles:     { h1: "patient", h2: "patient" }
  # 기존 필드 유지: email, displayName, status, ...

/visit_plans/{uid}      # 기존 유지, hospitalId 필드 추가
/sessions/{sid}         # hospitalId 필드 추가
/audit_logs/{hospitalId}/{id}   # 병원별 분리
```

### 1.2 인증 / 권한 (Firebase Auth Custom Claims)

- 로그인 시 Cloud Function이 `onCreate` 또는 `onRoleChange` trigger로 custom claim 세팅:
  ```json
  { "role": "patient", "hospitalId": "smch", "hospitalIds": ["smch", "asan"] }
  ```
- RTDB 규칙에서 `auth.token.hospitalId === $hospitalId` 또는 `auth.token.role in ["platformAdmin"]` 로 격리

### 1.3 가입·로그인 플로우

1. **환자 가입 (신규)**: 이메일/OAuth 로그인 → 이름·전화번호 → **병원 선택 화면** → 완료
2. **환자 가입 (사전 초대)**: 의료진이 `invitation` 발급 시 `hospitalId` 지정 → 토큰 수락 시 자동 매핑
3. **의료진**: 기존 `staff-codes` 플로우 유지. 코드에 hospitalId 있으므로 자동 매핑
4. **기존 환자**: 마이그레이션 스크립트로 `primaryHospitalId: "demo"` 채움

### 1.4 병원 선택 UI

- 드롭다운: 로고(아이콘 48×48) + 병원명 + 거리(선택). 검색창 + "최근 방문" 섹션
- 위치 기반 추천: `navigator.geolocation` 승인 시 가까운 순 정렬
- URL 파라미터 `?hospital={slug}` → 드롭다운 자동 선택 (로비 QR 부트스트랩)
- 빈 상태: "가입 가능한 병원이 없습니다. 코드를 입력하거나 병원에 문의해 주세요"

### 1.5 라우팅

- 신규 구조: `/h/:slug/patient/home`, `/h/:slug/staff/dashboard`, `/h/:slug/admin` (병원 관리자)
- Platform admin: `/admin` (변경 없음)
- `HospitalProvider` React Context — slug → hospital profile 조회 → 테마·로고 주입

### 1.6 화이트라벨 브랜딩

- CSS custom property 동적 주입:
  ```css
  :root {
    --color-primary: var(--hospital-primary, #004e9f);
  }
  ```
- Tailwind 토큰을 `var(--color-primary)` 기반으로 리팩터
- 로고는 Firebase Storage 경로. 런타임 fetch + fallback

### 1.7 변경 파일 (개략)

| 경로 | 변경 |
|---|---|
| `src/types/hospital.ts` | `Hospital` 인터페이스 확장 (profile, features) |
| `src/services/hospitals.ts` | **신규** — CRUD, subscribe |
| `src/contexts/HospitalContext.tsx` | **신규** |
| `src/pages/SelectHospitalPage.tsx` | **신규** — 가입 후 병원 선택 |
| `src/App.tsx` | 라우팅 재구성 (`/h/:slug/*` 추가) |
| `src/config/firebase.ts` | 변경 없음 |
| `database.rules.json` | hospitalId 기반 규칙 재작성 |
| `functions/src/setClaims.ts` | **신규** — 역할/병원 custom claim |
| `data/migrate-demo-hospital.mjs` | **1회성** 마이그레이션 스크립트 |

### 1.8 완료 기준

- [ ] 데모 병원이 `/hospitals/demo`에 정상 저장, 기존 환자 페이지가 깨지지 않음
- [ ] 신규 환자가 회원가입 → 병원 선택 → 해당 병원 홈으로 이동
- [ ] 의료진 코드로 가입 시 hospitalId 자동 설정
- [ ] RTDB 보안 규칙 E2E 테스트 통과 (P1 범위)
- [ ] 다른 병원 데이터 교차 접근 시 401
- [ ] 플랫폼 관리자는 전체 병원 목록 관리 가능

---

## Phase 2 — 대시보드 셸 + 상단 탭 (2~3주)

**목적**: 환자 페이지를 단순 QR/지도에서 **병원별 맞춤 대시보드**로 확장. 탭 구조·홈·외래·안내의 최소 기능 셋.

### 2.1 탭 구조

| 탭 | 노출 조건 | 핵심 위젯 |
|---|---|---|
| 🏠 홈 | 항상 | 오늘 일정, 대기 순번, 빠른 CTA, 공지 |
| 🏥 외래 | `features.appointments` | 예약·접수·대기·처방 |
| 🛏 입원 | `features.inpatient` + 현재 입원 중 | 담당 의료진, 면회 예약, 퇴원 수속 |
| 💊 건강검진 | `features.checkup` | 검진 예약, 결과 이력 |
| 🗺 안내 | 항상 | 기존 지도 + QR 흡수 |
| ⋯ 더보기 | 항상 | 결제·서류·가족·설정 |

### 2.2 탭 네비게이션 UI

- 모바일: 상단 가로 스크롤 탭 + 현재 탭 강조. **6개 초과 시 "더보기" 드롭다운** (admin 네비 패턴 재활용)
- 데스크탑: 동일 상단 탭 (사이드바 없음)
- 탭 상태: URL 쿼리 `?tab=home` 영속화 (새로고침 대응)
- 하위 탭(예: 안내 = 지도/QR)은 기존 `useSearchParams` 패턴 활용

### 2.3 홈 탭 위젯 (P2 범위)

1. **오늘 일정** — 예약된 진료/검사 카드. 없으면 "오늘 일정이 없습니다" 빈 상태
2. **빠른 CTA 4개** — 진료 예약·길찾기·대기 확인·응급실 (응급실은 홈 고정 제안)
3. **공지 배너** — `hospitals/{id}/announcements` 최신 1건
4. **대기 순번 플레이스홀더** — P3에서 실시간 채움

### 2.4 외래 탭 (P2 최소 셋)

- 진료 시간표 조회 (부서별 의료진 근무표)
- 예약 생성 (날짜 + 부서 + 의료진 선택)
- 내 예약 목록
- 예약 취소
- **실시간 대기·접수·결제는 P3로**

### 2.5 안내 탭 (이관)

- 현재 `PatientPage.tsx` + `PatientMapBrowseView.tsx` + `PatientDashboard.tsx`를 **안내 탭 내부로** 이동
- 기능은 100% 보존, 위치만 변경

### 2.6 "더보기" 탭 (스켈레톤)

- 내 정보, 병원 스위처, 알림 설정, 고령자 모드 토글(P4), 로그아웃
- 결제·서류·가족은 P3·P5에서 채움

### 2.7 변경 파일

| 경로 | 변경 |
|---|---|
| `src/pages/HospitalHomePage.tsx` | **신규** — 탭 셸 |
| `src/components/hospital/HomeTab.tsx` | **신규** |
| `src/components/hospital/AppointmentsTab.tsx` | **신규** |
| `src/components/hospital/GuideTab.tsx` | **기존 PatientPage 내용 흡수** |
| `src/components/hospital/MoreTab.tsx` | **신규** |
| `src/components/hospital/HospitalTabs.tsx` | **신규** — 네비 + 드롭다운 |
| `src/services/appointments.ts` | **신규** |

### 2.8 완료 기준

- [ ] 로그인 후 `/h/{slug}/patient/home`으로 진입
- [ ] 6개 탭 전환 + URL 영속화
- [ ] 홈 탭에서 오늘 일정 위젯, 공지 표시
- [ ] 외래 탭에서 예약 생성·취소 가능 (MVP 수준)
- [ ] 안내 탭이 기존 지도/QR 기능 전부 포함
- [ ] 탭 전환 시 기존 QR 세션·길찾기 상태 보존 (visibility 토글)

---

## Phase 3 — 고수요 편의 기능 (3~4주)

**목적**: 시장 앱들의 핵심 경쟁력(실시간 대기·처방·결제·알림)을 흡수해 "차별화된 환자 경험" 완성.

### 3.1 실시간 대기 순번 (F1)

- 스키마: `/wait_queue/{hospitalId}/{department}/{date}/{queueNumber}`
- 환자 접수 시 queueNumber 부여 → RTDB onValue 구독으로 실시간 반영
- 홈 위젯: "내 앞 3명 · 예상 대기 ~12분"
- **iOS Live Activity**: Expo Live Activity 또는 native bridge 고려. 웹에서는 Push Notification으로 대체
- 의료진 콘솔: 다음 환자 호출 버튼 → 상태 전이

### 3.2 처방전 + 약국 전송 (F6)

- 진료 완료 시 staff가 처방전 업로드 (PDF 또는 구조화 JSON)
- 환자: "약국 선택" → QR 발급 또는 약국 코드로 전송
- 즐겨찾기 약국 저장

### 3.3 결제 / 대리결제 (F8, F9)

- **카카오페이·토스·네이버페이** 중 1개 선택 (국내 시장 점유율 기준 카카오페이 우선 권장)
- Firebase Functions에서 PG 토큰 발급 + Webhook 처리
- 대리결제: 결제 링크 생성 → 보호자에게 카카오톡 알림톡 → 웹 뷰에서 결제
- 결제 이력 조회

### 3.4 알림톡 / Push (F5)

- **카카오 알림톡** (비즈톡) — 내 차례 5분 전, 예약 확인, 결제 영수증
- Firebase Cloud Messaging 병행 (앱 내 Push)
- 사용자 설정: 채널별 on/off

### 3.5 주차 할인 자동화 (F8)

- 차량 번호 등록 UI (기본 1대, 최대 3대)
- 진료 완료 시 자동 매칭 → 주차 시스템과 연동 (병원 API 개별)
- Phase 3에서는 **병원별 어댑터 인터페이스**만 정의, 실제 연동은 파일럿 병원별 추가

### 3.6 변경 파일

| 경로 | 변경 |
|---|---|
| `src/services/waitQueue.ts` | **신규** |
| `src/services/prescription.ts` | **신규** |
| `src/services/payment.ts` | **신규** |
| `src/services/notifications.ts` | **신규** (Push 등록 등) |
| `functions/src/payment/kakaoPay.ts` | **신규** |
| `functions/src/notifications/alimtalk.ts` | **신규** |
| `functions/src/waitQueue/onCall.ts` | **신규** — 다음 환자 호출 webhook |

### 3.7 완료 기준

- [ ] 환자가 접수 후 홈에서 실시간 대기 순번 확인
- [ ] 의료진이 "다음 환자 호출" → 환자 Push 알림 수신
- [ ] 진료 완료 후 처방전을 약국으로 QR 전송
- [ ] 카카오페이로 진료비 결제 성공
- [ ] 보호자 대리결제 링크 생성 → 결제 완료
- [ ] 알림톡 수신 확인 (실발송은 PG 계약 후 파일럿)

---

## Phase 4 — 고령자·접근성 (지속, P2~P3 병행 가능)

**목적**: 고령자 UI 연구 결과(디자인/콘텐츠/프로세스/시스템 4영역)를 반영하여 모든 연령대가 불편 없이 사용하도록.

### 4.1 고령자 모드 (F16)

- "더보기 → 고령자 모드" 토글 → `user.preferences.largeUi = true`
- CSS class `.ui-senior`가 root에 적용 → 전체 폰트·버튼 크기 ↑
- 홈 위젯 단순화: **4개 기능만** (예약·안내·대기·전화)
- 단어 축약: "비대면 진료" → "집에서 진료"

### 4.2 음성 길안내 / TTS (F17)

- 지도 경로 안내 시 Web Speech API `SpeechSynthesisUtterance`로 한국어 TTS
- "다음: 엘리베이터에서 좌회전 · 15미터"
- 저시력·운전 중 사용 고려

### 4.3 OAuth 로그인 확장 (F15)

- **카카오 로그인** (국내 OTP 대체 최적) → Firebase Custom Token
- **Apple Sign-In** (iOS 심사 요건)
- 네이버 로그인 (선택)
- 기존 이메일/비밀번호는 유지 (백업)

### 4.4 응급 버튼 (F10)

- 홈 화면 고정 red CTA: "응급실 바로 가기" → 한 탭으로 응급실 내비 시작 + 119 단축 전화 (옵션)

### 4.5 가족 계정 연동 (F7)

- "가족 추가" → 초대 링크 (카카오톡 공유) → 수락 시 상호 연결
- 권한 레벨:
  - **읽기** — 일정·대기 순번 조회
  - **대리** — 예약·결제까지 가능
- 개인정보 민감 항목(진료 상세)은 본인만

### 4.6 변경 파일 (주요)

| 경로 | 변경 |
|---|---|
| `src/styles/senior.css` | **신규** |
| `src/hooks/useTextToSpeech.ts` | **신규** |
| `src/services/auth/kakao.ts` | **신규** |
| `src/services/family.ts` | **신규** |
| `functions/src/auth/kakaoToken.ts` | **신규** |

### 4.7 완료 기준

- [ ] 고령자 모드 토글 시 전체 UI 스케일 확대
- [ ] 길찾기 도중 TTS 음성 안내 작동
- [ ] 카카오 로그인 성공 + Firebase 세션 획득
- [ ] 가족 읽기/대리 권한 분리 동작
- [ ] 응급 버튼 한 탭으로 응급실 길찾기

---

## Phase 5 — 고급 (지속, 파트너십 필요)

**목적**: MyChart 수준의 "개인 건강 허브"로 확장. 파트너·규제 이슈로 시간 필요.

### 5.1 검사 결과 조회 (F3) — **무기한 보관**

- EMR API 연동 (병원별) 또는 staff 수동 업로드
- PDF·영상 저장 Firebase Storage (암호화)
- 타임라인·검색 필터
- **세브란스 단점(1년 제한)을 "영구 보관"으로 차별화**

### 5.2 진료 전 디지털 문진 (F4)

- 병원별 문진 템플릿 (관리자 편집)
- 방문 1일 전 알림 → 제출 → 진료 중 의료진 화면에 노출

### 5.3 의료진 메시지 (F11)

- 비동기 Q&A 스레드
- 의료진은 스태프 대시보드에서 확인·답변 (SLA 설정)
- 의료법 광고/처방 관련 규제 검토

### 5.4 PHR 통합 (F14)

- 보건복지부 **나의건강기록** 앱 API 연동
- 타 병원 이력 import → 통합 타임라인
- 파트너십·표준 FHIR 연동 필요

### 5.5 공공 API · 보험

- 실손보험 청구 자동화 (진단서·영수증 자동 묶음)
- 건강보험 자격 조회
- 병원별 계약 필요

### 5.6 다국어 (F18)

- i18n (`react-i18next`) + 영어·중국어·일본어
- Tier 1 대형 병원(외국인 환자 비중 높음) 대상

### 5.7 완료 기준

- [ ] 파일럿 병원 1곳에서 검사결과 PDF 조회 가능
- [ ] 진료 전 문진 제출 → staff 콘솔 노출
- [ ] 의료진 메시지 스레드 정상 수신·응답
- [ ] PHR 연동 파트너십 체결 (이 단계는 비즈 이슈)

---

## 공통 품질 기준 (모든 Phase에 적용)

| 축 | 기준 |
|---|---|
| 타입 체크 | `npx tsc --noEmit` 통과 |
| Lint | `npx eslint` 무경고 (신규·변경 파일) |
| 테스트 | 주요 서비스 단위 테스트 + E2E 핵심 플로우 |
| 보안 규칙 | `public/e2e-visit-plan.html`처럼 **규칙 E2E 테스트 페이지** 각 subtree마다 작성 |
| 접근성 | 주요 액션 `aria-label`·키보드 포커스·색대비 4.5:1 |
| 모니터링 | Sentry 또는 Firebase Crashlytics (서울아산·세브란스 "잦은 오류" 반면교사) |
| 배포 | `firebase deploy --only hosting,database,functions` |

## 경쟁 앱 대비 차별화 체크리스트 (지속 검증)

- [ ] **로그인 오류 드묾** (vs 세브란스) — 토큰 자동 갱신·offline graceful
- [ ] **검사결과 무기한** (vs 세브란스 1년) — Storage 보관
- [ ] **에러 잦지 않음** (vs 서울아산) — 모니터링·E2E
- [ ] **간단한 홈** (vs MyChart 복잡성) — 맞춤 위젯 3-5개
- [ ] **고령자 친화** (vs MyChart 디지털 친숙도 요구) — 고령자 모드
- [ ] **병원별 브랜딩** (vs MyChart 제약) — 화이트라벨
- [ ] **실시간 대기 Live Activity** (똑닥 동등) — iOS/웹 동시
- [ ] **비대면 진료 follow-up** (굿닥 대비 의료진 발급 워크플로) — 신뢰성 차별화

## 의사결정 체크포인트

### P1 착수 전
- [ ] Hospital slug 노출 형태: 경로(`/h/smch`) vs 서브도메인
- [ ] Custom claim 전파 타이밍: 로그인 즉시 vs 다음 refresh
- [ ] 기존 데모 병원 데이터 마이그레이션 범위 (hardcoded `src/data/hospital/*` 전부 이관 여부)

### P2 착수 전
- [ ] 탭 네비: 상단 가로 스크롤 vs 드롭다운 (admin 패턴과 일관성 여부)
- [ ] 홈 위젯 기본 구성: 어떤 4-5개를 기본 노출?

### P3 착수 전
- [ ] PG: 카카오페이 / 토스 / 네이버페이 중 1개 확정
- [ ] 알림톡: 카카오 비즈톡 계정 개설 주체 (병원별 vs 플랫폼)

### P4 착수 전
- [ ] Kakao Developers 앱 등록 (플랫폼 OAuth 클라이언트)

### P5 착수 전
- [ ] 나의건강기록 API 파트너십 접촉
- [ ] 파일럿 병원 EMR 벤더 협의

## 리스크 레지스터

| 리스크 | 확률 | 영향 | 완화 |
|---|---|---|---|
| 기존 데모 동작 깨짐 (P1 마이그레이션) | 중 | 높 | feature flag로 구 라우트 병존 |
| 카카오페이 심사 지연 | 중 | 중 | 테스트 결제 환경 우선, 프로덕션은 파일럿 단계 |
| 알림톡 템플릿 심사 | 높 | 중 | 템플릿 병행 제출, 승인까지 FCM 대체 |
| 고령자 UX 실제 테스트 부족 | 중 | 높 | P4 시작 전 실사용자 인터뷰 5명 |
| 파일럿 병원 미확보 | 중 | 크리티컬 | P1·P2 병행해 영업 진행 |
| 의료법/개인정보 위반 | 낮 | 크리티컬 | 법률 검토 계약 (P3 결제·알림톡 전 필수) |

## 권장 실행 순서

1. **P1 즉시 시작** — 후속 모든 작업의 전제
2. **P1 후반부부터 P2 병행** — 탭 셸 스켈레톤 선작업
3. **P2 완료 직후 P4 일부(고령자 모드·Apple Sign-In) 병행** — 모바일 배포 심사 요건
4. **P3 결제 기능은 파일럿 병원 확보 후 착수** — 실거래 전제
5. **P5는 P3 안정화 이후 파트너십 성숙도 맞춰 진행**

---

## 부록 A. 참고 벤치마크 요약

| 앱 | 벤치마크 포인트 | 차용 |
|---|---|---|
| 삼성서울병원 | 길 안내 로봇·일정·대기·위치·결제·서류 | 전반적 기능 set |
| 세브란스 | 검사 결과·식단 정보 | 검사결과 **무기한 보관**으로 차별화 |
| 서울아산 | 예약·결과 | 에러 최소화 반면교사 |
| 똑닥 | **실시간 대기·Live Activity·처방 QR** | 실시간 대기 Live Activity 구현 (F1) |
| 굿닥 | 비대면 진료·전국 검색 | 비대면 follow-up (F2) |
| MyChart | 메시지·결과·크로스 조직·예약 | 메시지·PHR 통합 (F11, F14) |
| 나의건강기록 | 공공 PHR | API 연동 (F14) |

## 부록 B. 스키마 예시 (P1 minimum)

```jsonc
// /hospitals/demo
{
  "profile": {
    "name": "MediWay 데모 병원",
    "slug": "demo",
    "logoUrl": "https://storage.googleapis.com/mediway-demo/hospitals/demo/logo.png",
    "themeColor": "#004e9f",
    "contractStatus": "active",
    "features": {
      "appointments": true,
      "inpatient": false,
      "checkup": true,
      "payment": false
    },
    "createdAt": 1776000000000
  }
}

// /users/S5gU1edQKeQ1w02th37Q8hQYowI2
{
  "primaryHospitalId": "demo",
  "hospitalIds": ["demo"],
  "role": "admin",
  "hospitalRoles": { "demo": "admin" },
  "email": "catlife9029@gmail.com",
  "displayName": "박준영",
  "status": "active",
  "createdAt": 1776760401834
}
```

## 부록 C. 파일 트리 스냅샷 (예상 최종)

```
src/
  contexts/
    HospitalContext.tsx            [P1 신규]
  pages/
    SelectHospitalPage.tsx         [P1]
    HospitalHomePage.tsx           [P2 — 탭 셸]
    admin/ …                        (기존 유지 + hospital scope)
  components/
    hospital/
      HospitalTabs.tsx             [P2]
      HomeTab.tsx                  [P2]
      AppointmentsTab.tsx          [P2]
      InpatientTab.tsx             [P3]
      CheckupTab.tsx               [P3]
      GuideTab.tsx                 [P2 — PatientPage 흡수]
      MoreTab.tsx                  [P2]
      widgets/
        TodaySchedule.tsx          [P2]
        WaitQueueWidget.tsx        [P3]
        AnnouncementBanner.tsx     [P2]
  services/
    hospitals.ts                   [P1]
    appointments.ts                [P2]
    waitQueue.ts                   [P3]
    prescription.ts                [P3]
    payment.ts                     [P3]
    notifications.ts               [P3]
    family.ts                      [P4]
    health-records.ts              [P5]
functions/src/
  setClaims.ts                     [P1]
  payment/kakaoPay.ts              [P3]
  notifications/alimtalk.ts        [P3]
  waitQueue/onCall.ts              [P3]
  auth/kakaoToken.ts               [P4]
```

---

_작성일: 2026-04-22_
_범위: MediWay Plus Ultra 확장안 (multi-tenant SaaS 전환 + 대시보드 + 고급 기능)_
