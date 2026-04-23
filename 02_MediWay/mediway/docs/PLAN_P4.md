# Phase 4 구현 계획 — 접근성·가족 대리(MOAT)·OAuth

> **상태**: 계획 (2026-04-23)
> **브랜치**: `mediway/plusultra/p4` (착수 시 `mediway/develop`에서 분기)
> **타깃 병합지**: `mediway/develop`
> **기반**: P1 + P2 + P3 Track 1 완료 (`develop @ 4e9ac21`)
> **예상 기간**: 2~3주 (1인 풀타임, Track A 기준)
> **참조**: `GUIDE_v2/plusultra_v2.md §Phase 4` + `GUIDE_v2/PlusUltra#4.md` (v1 + v2 덮어쓰기 블록)

---

## 0. 목표

P3 Track 1에서 "파일럿 병원 계약 가능" 수준의 공통 편의 기능을 완료했다. P4는 여기에 **MediWay 유일의 MOAT(가족 대리)** 와 **한국 고령 인구용 접근성**을 얹어, **"MyChart·똑닥·세브란스·아산이 따라올 수 없는 영업 포인트"** 를 확립한다.

### 성공의 정의 — 비즈니스 관점

1. **자녀가 부모 앱을 대리 관리** 할 수 있다 (재방문률·충성도 기대)
2. **60대+ 환자가 보호자 도움 없이** 예약·대기 확인이 가능하다
3. **Apple 계정 사용자가 1탭으로 로그인**
4. 길찾기가 시각적 어려움 있는 사용자에게도 **음성으로** 안내된다
5. 모든 가족 대리 접근은 **audit** 에 남아 PIPA·개인정보처리 근거 확보

---

## 1. 스코프

### Track 분리 (v2 §4·§부록 C.F20 및 사용자 맞춤 재평가)

**Track A — 웹만으로 완결 가능한 11 커밋 (이번 PR)**
P4 메인 스코프. PWA·웹 범위에서 전부 끝낼 수 있다.

**Track B — 네이티브 빌드 필수 (별도 PR, P4B)**
Apple Watch / Samsung Health 연동. Capacitor 래퍼 구축이 선행되므로 독립 프로젝트로 분리.

**Track C — 기존 유지/연기**
네이버 OAuth는 이미 P1에 구현되어 있다 (카카오/네이버 양쪽 지원). v2 "연기" 권고는 **신규 마케팅 축소** 의미이지 기존 코드 제거가 아니다. feature flag로 UI 노출만 제어.

### IN (Track A)

| 영역 | v2 기준 내용 |
|---|---|
| F16 고령자 모드 완성 | root `font-size` 16→22px, `.ui-senior` CSS 확장, SeniorHome (위젯 2~3개), 언어 단순화 사전 (`i18n.senior.json`) |
| F17 TTS 음성 길안내 | `useTextToSpeech` 훅 + GuideTab 길찾기에만 통합. 전역 TTS Drop |
| F15 Apple Sign-In | Firebase Auth `OAuthProvider('apple.com')` + `signInWithPopup` — 웹 범위 |
| F7 가족 대리 (MOAT #1) | JWT 초대 링크 · reader/delegate 2단계 권한 · audit log · 더보기 탭 가족 섹션 |
| 응급 버튼 마무리 | P2 EmergencyCtaWidget 접근성 감사 + 고령자 모드 폰트 스케일 적용 |
| 네이버 OAuth 숨김 flag | `VITE_ENABLE_NAVER_LOGIN=false` 기본값, 로그인 페이지 조건 렌더 |

### OUT (Track B / Track C)

- Apple Watch / HealthKit 바이탈 연동 (Capacitor 래퍼 필요) → **P4B**
- Samsung Health SDK → **P4B**
- 가족 대리 + **실결제** 연동 (대리 결제) → **Track 2 C9와 합쳐 P3 Track 2 스코프**
- 전역 TTS / Cloud TTS 서버 백업 → **P5 이후**
- 미성년자·피후견인 대리 (법정대리인 확인 절차) → **P5 이후 법무 후**

### v2 특이사항 (PlusUltra#4.md 상단 블록 반영)

| 항목 | v2 결정 | Track A 구현 |
|---|---|---|
| F7 MOAT 격상 | MOAT #1 | 영업 메시지 · 코드 comment에 "**MOAT 씨앗**" 태그 |
| F17 TTS 축소 | 길찾기만 | GuideTab만 integration, 홈 위젯 TTS 제외 |
| 네이버 OAuth 연기 | 신규 마케팅 중단 | 기존 코드 유지, 로그인 페이지 노출만 flag |
| F20 Apple Watch 신규 | v2 신규 | **Track B로 분리** — 본 PR 범위 밖 |
| 고령자 모드 | P2 위에 완성 | P2 `useSeniorMode` · `senior.css` 재활용 |
| 응급 버튼 | P2에서 배치 완료 | 접근성 감사 + 고령자 모드 폰트 스케일 적용만 |

---

## 2. 선행 조건

- [x] P3 Track 1 merge to develop (`4e9ac21`)
- [x] `features.aiTriage=true` for demo (프로덕션 설정 완료)
- [x] RTDB rules: wait_queue / wait_queue_by_patient / user_fcm_tokens 배포됨
- [ ] Apple Developer 계정 + Apple App Store Connect (Apple Sign-In Web 활성화를 위해 Services ID 필요)
- [ ] Firebase Auth Console에서 **Apple 공급자 활성화** (Services ID · Private Key 업로드)
- [ ] 법무 검토: **가족 대리 범위** (읽기/대리 권한 선택지, 미성년자 배제 문구)
- [ ] 법무 검토: **PIPA 처리방침 업데이트** (가족 대리 수탁, audit 저장 기간)
- [ ] JWT 서명키 — Cloud Functions 환경변수 (`FAMILY_INVITE_JWT_SECRET`) Secret Manager 등록

**법무 게이트 선결 완료 전에는 C6~C9(가족 대리) 배포 금지**. 구현은 하되 feature flag로 off.

---

## 3. 작업 순서 — 11 커밋 (Track A)

리스크 체크포인트: **C7 (JWT 초대·만료·일회용)**, **C8 (권한 규칙 확장)**, **C10 (Apple Sign-In 웹 OAuth 흐름)**.

### Commit 1 — 고령자 모드 스케일 확장 (F16)

- `src/styles/senior.css` 확장 — root `font-size` 16→22px, 터치 타겟 56px+, 고대비 variables
- `@media (prefers-reduced-motion)` 대응
- Lighthouse Accessibility 90+ 유지 검증
- 테스트: `useSeniorMode` 토글 시 root class 주입·제거 회귀

### Commit 2 — SeniorHome 레이아웃 (F16)

- `src/components/hospital/tabs/SeniorHome.tsx` 신규
- 위젯 **2~3개**로 단순화: 오늘 일정 · 대기 순번 · 응급 CTA (이 순서, AI triage 제외)
- HomeTab 분기: `largeUi ? <SeniorHome /> : <StandardHome />`
- 언어 단순화: 카드 캡션 "집에서 진료", "돈 내기" 등 `i18n.senior.json` 참조

### Commit 3 — 언어 단순화 사전 (F16)

- `src/i18n/senior.json` — 한자어·외래어 치환 사전
- `src/hooks/useSeniorCopy.ts` — `useSeniorMode` 결과에 따라 자동 치환
- 적용 범위: 탭 라벨·CTA 버튼·빈 상태 메시지 (전부 아님, 과잉 적용 주의)
- 테스트: 토글 ON시 "진료 예약" → "병원 예약" 전환

### Commit 4 — TTS 길안내 훅 (F17 축소)

- `src/hooks/useTextToSpeech.ts` — Web Speech API 래퍼
  - 한국어 voice 우선 선택 (iOS Yuna, Android ko-KR)
  - 미지원 브라우저 graceful degradation (시각 알림 fallback)
  - rate / pitch 사용자 preference 반영 (`/users/{uid}/preferences/tts`)
- 안내 탭(GuideTab) 길찾기 중 "다음: 엘리베이터에서 좌회전" 수준 발화
- 사용자 허락 토글 UI (더보기 탭 → "음성 길안내")
- **전역 TTS·홈 위젯 읽기 미포함** (v2 축소)

### Commit 5 — 응급 버튼 polish (F10)

- P2 `EmergencyCtaWidget`의 고령자 모드 폰트·터치 타겟 검증
- `prefers-reduced-motion` 대응
- 119 확인 모달 접근성(aria-modal·focus trap) 감사
- 실질적 구현 없음 — 주로 QA + 마이너 수정

### Commit 6 — 가족 데이터 모델 + 타입 (F7)

- `src/types/family.ts` — `FamilyRole = 'reader' | 'delegate'`, `FamilyGrant`, `FamilyInvite`
- `src/services/family.ts` 초기 — `listGrantees`, `listGranters`, `revokeGrant`
- 스키마 설계 (§4.1 참조)
- 단위 테스트 8+ 케이스

### Commit 7 — 가족 초대 JWT Cloud Function (F7)

**리스크 ★★★** — 토큰 유출 시 무단 접근, 10분 만료·일회용 엄수

- `functions/src/familyInvite.ts`
  - `createFamilyInvite(inviterUid, role, inviteeContact): { token, expiresAt }`
  - `acceptFamilyInvite(token, accepterUid): void` — 서명·만료·사용 여부 검증
  - `revokeFamilyInvite(inviterUid, token)`
- Secret: `FAMILY_INVITE_JWT_SECRET`
- 단위 테스트: 만료·일회용·서명 위조·self-accept 차단 5+ 케이스

### Commit 8 — 가족 권한 RTDB 규칙 확장 (F7)

**리스크 ★★★** — 타 사용자 데이터 접근 허용. 규칙 오류 시 전사 data leak.

- `visit_plans/{uid}`: granters에 auth.uid 존재 시 read 가능
- `hospitals/{hid}/appointments_by_patient/{uid}`: granters에 auth.uid + role='delegate' 시 read
- `hospitals/{hid}/prescriptions/{uid}`: role='delegate'만 read
- `/family_invites/{token}`: Cloud Function SDK만 read/write (client 차단)
- `/audit_logs/{hospitalId}/family_access/{id}`: admin + 본인 read
- `scripts/test-rules.mjs` +10~12 시나리오 (31 → 41+)

### Commit 9 — 가족 UI (F7)

- `src/pages/account/FamilyPage.tsx` — 더보기 탭 → "가족" 섹션
- 2개 리스트: "내가 권한 준 사람" (grantees) / "내게 권한 준 사람" (granters)
- 초대 보내기 Dialog (역할 선택 + 카카오톡 공유 링크)
- 권한 변경·해제 Dialog
- 감사 로그 뷰 (누가·언제·어떤 자원)

### Commit 10 — 가족 접근 audit 훅 (F7)

- `src/services/familyAudit.ts` — grantee가 민감 정보(진단·처방) 접근 시 자동 로그
- `useFamilyAccessLog` 훅 — WaitQueueWidget·AppointmentsTab 등에서 granter 모드 진입 시 push
- 서버 훅 대안: Cloud Function이 RTDB read 감시 (간단 client 쓰기로 우선, 신뢰 경계는 서버 버전 P5)

### Commit 11 — Apple Sign-In 웹 통합 (F15)

- `src/services/appleAuth.ts` — Firebase Auth `OAuthProvider('apple.com')` + `signInWithPopup`
- `src/pages/auth/LoginPage.tsx` — Apple 버튼 추가 (카카오 옆)
- 신규 사용자 플로우: Apple 이메일 relay 처리, `ensureUserProfile`
- `VITE_ENABLE_NAVER_LOGIN=false` 기본값 — 네이버 버튼 조건 렌더 (Track C)
- **Apple Developer Services ID 세팅**은 사용자 측 사전 작업

---

## 4. 데이터 모델

### 4.1 `/users/{uid}/family/grantees/{granteeUid}` + `/granters/{granterUid}`

```typescript
interface FamilyGrant {
  role: 'reader' | 'delegate';
  grantedAt: number;
  acceptedAt?: number;    // null이면 pending
  displayName?: string;   // 상대방 표시명 (캐시)
}
```

### 4.2 `/family_invites/{token}` (Cloud Function SDK only)

```typescript
interface FamilyInvite {
  token: string;           // JWT
  inviterUid: string;
  role: 'reader' | 'delegate';
  createdAt: number;
  expiresAt: number;       // createdAt + 10분
  status: 'pending' | 'accepted' | 'expired' | 'revoked';
  inviteeContact?: string; // email or phone (선택)
  acceptedBy?: string;     // accepterUid
}
```

### 4.3 `/users/{uid}/preferences` (P2 확장)

```typescript
interface UserPreferences {
  largeUi?: boolean;
  tts?: { enabled: boolean; rate?: number };     // P4 NEW
  emergencyNumber?: string;                      // P4 NEW, default "119"
  notificationChannels?: ('push' | 'sms' | 'email' | 'alimtalk')[];
  language?: 'ko' | 'en' | 'zh' | 'ja';
}
```

### 4.4 `/audit_logs/{hospitalId}/family_access/{id}`

```typescript
interface FamilyAccessLog {
  id: string;
  actorUid: string;       // grantee
  targetUid: string;      // granter (data owner)
  resource: 'appointments' | 'prescriptions' | 'wait_queue' | 'visit_plans';
  refId?: string;
  timestamp: number;
}
```

### 4.5 `/users/{uid}/linkedProviders`

```typescript
interface LinkedProviders {
  email?: boolean;
  google?: boolean;
  kakao?: boolean;
  naver?: boolean;
  apple?: boolean;        // P4 NEW
}
```

---

## 5. 보안 규칙 확장

핵심 패턴:
- **granter 데이터 접근은 granters 역인덱스 기반** (client에서 `/users/{uid}/family/granters/{auth.uid}` 존재 확인)
- **reader는 일정·대기 순번만**, **delegate는 처방까지**
- **`/family_invites/{token}`은 Cloud Function SDK로만** 접근 (client read/write 전부 차단)
- 시나리오 10~12개 추가 목표 — `scripts/test-rules.mjs` 31 → **41+**

```jsonc
{
  "users": {
    "$uid": {
      "family": {
        "grantees": {
          "$granteeUid": {
            ".read":  "auth.uid === $uid || auth.uid === $granteeUid || auth.token.role === 'platformAdmin'",
            ".write": "auth.uid === $uid || auth.token.role === 'platformAdmin'"
          }
        },
        "granters": {
          "$granterUid": {
            ".read":  "auth.uid === $uid || auth.uid === $granterUid || auth.token.role === 'platformAdmin'",
            ".write": "auth.uid === $uid || auth.token.role === 'platformAdmin'"
          }
        }
      }
    }
  },
  "family_invites": {
    ".read":  false,
    ".write": false
  },
  "audit_logs": {
    "$hospitalId": {
      "family_access": {
        ".read": "auth.token.role === 'admin' || auth.token.role === 'platformAdmin'",
        "$id": {
          ".write": "auth != null && !data.exists() && newData.child('actorUid').val() === auth.uid"
        }
      }
    }
  }
}
```

기존 `visit_plans`·`appointments_by_patient`·`prescriptions` 규칙에 **granters 체크를 OR 추가**:

```jsonc
".read": "... || root.child('users').child($uid).child('family/granters').child(auth.uid).exists()"
```

---

## 6. 테스트 전략

### 단위 테스트 (vitest)
- `useSeniorMode` / `useSeniorCopy` 토글·persist
- `useTextToSpeech` — voice pick, 미지원 브라우저 fallback
- `family` service — grant/revoke/audit
- `appleAuth` service — popup success/cancel/error
- `useFamilyAccessLog` 훅

### Cloud Function 테스트 (functions/vitest)
- `createFamilyInvite` — JWT payload, expiresAt, 서명
- `acceptFamilyInvite` — 만료 토큰·일회용·self-accept 차단·서명 위조
- audit log push 호출 확인

### Emulator 규칙 테스트
- `scripts/test-rules.mjs` +10~12 시나리오
  - granter 데이터 grantee 읽기 허용
  - reader의 prescription read 차단 ★
  - delegate의 prescription read 허용
  - family_invites client read/write 전부 차단 ★
  - 해제 즉시 access 차단 ★
  - audit_logs admin 외 read 차단 ★

### E2E 페이지
- `public/e2e-family-access.html` — reader/delegate 권한 시나리오 수동 체크리스트
- `public/e2e-senior-mode.html` — 고령자 모드 + TTS + Apple 로그인 통합

### 수동 QA
- 60대+ 사용자 3명 1회 세션 관찰 (예약 완주)
- Apple 로그인 Safari/Chrome 양쪽 성공
- 가족 초대 → 카톡 공유 → 수락 → 상호 연결 실기기

---

## 7. 리스크 레지스터

| 리스크 | 확률 | 영향 | 완화 |
|---|---|---|---|
| Apple Developer Services ID 세팅 지연 | 중 | 높 | C11 직전에 사용자 측 사전 작업 확인. 최악 시 C11만 다음 PR |
| 가족 대리 법무 검토 반려 | 중 | 크리티컬 | 구현은 완료하되 feature flag off 배포, 법무 통과 후 활성화 |
| JWT secret 유출 | 낮 | 크리티컬 | Secret Manager, 로테이션 90일, 만료 10분 엄수 |
| granters 규칙 오배포로 data leak | 낮 | 크리티컬 | Emulator 테스트 필수 통과 게이트 → dry run → deploy |
| 고령자 모드 스케일이 레이아웃 깨뜨림 | 중 | 중 | C1 후 스크린샷 리뷰, Tailwind `rem` 기반이라 범위 제한적 |
| TTS 한국어 voice 미지원 브라우저 | 중 | 저 | 시각 알림 fallback, `navigator.vibrate` 보조 |
| 언어 단순화 사전 오탈자·오치환 | 중 | 중 | 치환은 whitelist 방식 (키 목록 한정) |
| Apple 이메일 relay → 사용자 프로필 매칭 실패 | 중 | 중 | `ensureUserProfile`에서 email fallback 로직, uid 우선 |

---

## 8. 배포 전략

1. **Commit 1-3** (고령자 모드): hosting만 배포
2. **Commit 4-5** (TTS + 응급 polish): hosting만
3. **Commit 6-7** (가족 데이터 + Cloud Function): Secret Manager 세팅 → functions 배포
4. **Commit 8** (규칙 확장): Emulator 41+ 시나리오 통과 필수 게이트 → rules 배포 → hosting 배포
5. **Commit 9-10** (가족 UI + audit): hosting만. feature flag `aiFamilyDelegation=false` 기본값
6. **Commit 11** (Apple Sign-In): Apple Services ID 등록 확인 → hosting 배포

**법무 검토 통과 후** 병원별 `features.familyDelegation=true` 활성화로 점진 롤아웃.

---

## 9. 완료 기준

### 기능
- [ ] 더보기 → 고령자 모드 토글 → 폰트·버튼·간격 전부 확대
- [ ] 고령자 모드에서 홈 탭이 SeniorHome (위젯 2~3개)
- [ ] 안내 탭 길찾기 시 TTS 한국어 발화
- [ ] Apple Sign-In 성공 (Safari·Chrome 양쪽)
- [ ] 카카오 로그인 유지, 네이버는 flag OFF 기본
- [ ] 가족 초대 링크 발송 → 수락자 로그인 → 상호 연결
- [ ] reader는 진료 일정 조회 가능, 처방 상세 접근 시 401
- [ ] delegate는 처방 접근 가능 + audit log 기록
- [ ] 가족 연결 해제 즉시 access 차단
- [ ] 응급 버튼 고령자 모드에서도 접근성 통과

### 접근성
- [ ] Lighthouse Accessibility **95+** (고령자 모드 AAA 목표)
- [ ] 키보드 단독 네비로 주요 플로우 완주
- [ ] `prefers-reduced-motion` 존중
- [ ] aria-modal·focus trap 응급 버튼 다이얼로그

### 품질
- [ ] `npx tsc --noEmit` + `npm run build` + `npx vitest run` 통과
- [ ] Emulator rules **41+** 시나리오 통과
- [ ] Functions vitest 통과 (+JWT 시나리오)
- [ ] PR 생성 → develop 병합

---

## 10. 일정 (Day-level)

| Day | 작업 | 체크포인트 |
|---|---|---|
| 1 | C1 (senior.css 스케일) |  |
| 2 | C2 (SeniorHome) | 스크린샷 리뷰 |
| 3 | C3 (언어 단순화) |  |
| 4 | C4 (TTS 훅 + GuideTab 통합) |  |
| 5 | C5 (응급 버튼 polish) |  |
| 6-7 | C6 (가족 데이터 모델) + C7 (JWT Function) ★ | Secret Manager 세팅 |
| 8 | C8 (규칙 확장) ★ | Emulator 41+ 통과 필수 |
| 9-10 | C9 (가족 UI) |  |
| 11 | C10 (audit 훅) |  |
| 12 | C11 (Apple Sign-In) | Apple Services ID 확인 |
| 13 | 통합 QA + 사용자 연구 (60대+ 3명) |  |
| 14 | 배포 + PR |  |

---

## 11. v2 차분 체크리스트 (구현 전 재확인)

- [ ] F7 **MOAT #1**로 영업 메시지·코드 주석 반영
- [ ] F17 TTS **길찾기만** — 전역 TTS Drop
- [ ] 네이버 OAuth **UI flag 숨김** — 기존 코드 유지
- [ ] F20 Apple Watch/HealthKit **Track B 분리** (P4B 별도 PR)
- [ ] 응급 버튼 F10 P2 위치 유지 (신규 배치 아님)
- [ ] 가족 대리 **reader / delegate 2단계만** — 세밀 RBAC 금지
- [ ] 모든 가족 접근은 **audit** 필수
- [ ] 미성년자·피후견인 대리 **제외** (P5 법무 후)

---

## 12. 참조

- `GUIDE_v2/plusultra_v2.md` §"Phase 4"
- `GUIDE_v2/PlusUltra#4.md` (v1 상세 + v2 덮어쓰기 블록)
- `mediway/docs/PLAN_P1.md`, `PLAN_P2.md`, `PLAN_P3.md`
- PR #1 (P1), #2 (P2), #3 (P3 Track 1)
- `P3_PREREQUISITES.md` — Track 2 선결 항목 (P4와 병행 가능)

---

## 13. 사용자 맞춤 필요성 재평가 (구현 전 자기검토)

각 기능은 **비판적 자기 검토** 를 거친 결과로 선정되었다.

| 기능 | 실사용자 ROI | 구현 부담 | 경쟁 대비 차별성 | 결론 |
|---|---|---|---|---|
| F16 고령자 모드 완성 | 🟢 매우 높음 (60대+ 비중 高) | 중 | MyChart 반면교사 극복 | ✅ Track A |
| F17 TTS (길찾기 한정) | 🟡 중간 (접근성 체크박스) | 소 | 차별화 포인트는 아니나 필수 | ✅ Track A |
| F7 가족 대리 | 🟢 **극도로 높음** | 대 | 🔥 **경쟁사 전멸 — 유일 MOAT** | ✅ Track A (핵심) |
| F15 Apple Sign-In | 🟢 높음 (iOS 사용자) | 중 | 경쟁 비등 | ✅ Track A |
| F10 응급 버튼 | 이미 완료 | 0 | 공통 기본 | ⚠️ polish만 |
| 네이버 OAuth | 기존 유지 | 0 | 공통 기본 | 🟡 flag 숨김 |
| F20 Apple Watch/HealthKit | 🟡 중~낮음 (보유율 제한) | **극대** (네이티브 빌드) | 차별화 가능하나 ROI 불확실 | ❌ **Track B 분리** |

### 이 범위가 "사용자 맞춤" 인 이유

1. **한국 대형병원 60대+ 내원객 50%+** — 고령자 모드는 옵션이 아닌 필수
2. **부모 의료 관리를 자녀가 맡는 가족 문화** — 가족 대리 없으면 MediWay는 20~40대만의 앱으로 축소
3. **경쟁사가 전부 미지원** (MyChart·똑닥·세브란스·아산) — 지금이 선점 타이밍
4. **Apple Watch는 ROI 불명** — 보유율·실사용률 불확실 + Capacitor 래퍼 부담. 웹 범위 완료 후 재평가

---

_작성일: 2026-04-23_
