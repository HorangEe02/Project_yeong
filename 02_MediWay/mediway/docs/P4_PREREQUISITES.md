# P4 선결 항목 체크리스트

> **상태**: 사용자 결정·계정·키·법무 대기 (2026-04-23)
> **목적**: P4 착수(브랜치 `mediway/plusultra/p4` 분기) 전에 확보해야 할 외부 계정·암호화 키·법무 검토를 한 곳에 정리.
> **다음 세션에서**: 이 문서 체크박스 전부 완료되면 `PLAN_P4.md §3` 순서대로 C1부터 순차 구현.
> **참조**: `docs/PLAN_P4.md`, `GUIDE_v2/PlusUltra#4.md`, `GUIDE_v2/plusultra_v2.md §Phase 4`

---

## 1. 🍎 Apple Sign-In 웹 활성화 (C11 · F15)

### 왜 필요한가

- **P4 C11**에서 Firebase Auth `OAuthProvider('apple.com')`로 Apple 로그인을 활성화한다.
- Apple 정책상 다른 3rd-party OAuth(카카오 등)를 제공하는 앱은 **Apple Sign-In도 필수 제공**. 현재 MediWay는 카카오/네이버 로그인이 있으므로 **향후 App Store 심사 시 Apple Sign-In 없으면 반려**.
- 웹만으로도 Capacitor 없이 구현 가능 (native 래퍼 불필요).

### 사전 결정

- [ ] **Apple Developer Program 가입 여부**
  - 개인 또는 조직 명의 ($99/년, 일 단위 갱신 불가)
  - 조직 명의일 경우 DUNS 번호 필요 (사업자 등록증 기반 발급, 무료)
  - 결제 카드 · 한국 세금계산서 대응 여부 확인

### 단계

#### 1-1. Apple Developer 계정 준비
- [ ] [developer.apple.com/programs](https://developer.apple.com/programs/) 접속 → Enroll
- [ ] 결제 완료 후 최대 48시간 승인 대기
- [ ] Team ID 확인 (`https://developer.apple.com/account` 우측 상단)

#### 1-2. App ID 생성 (없으면)
- [ ] Certificates, Identifiers & Profiles → Identifiers → **+** → App IDs
- [ ] Description: `MediWay`, Bundle ID: 예) `com.mediway.app`
- [ ] Capabilities에서 **Sign in with Apple** 체크 → 저장

#### 1-3. Services ID 생성 (웹 로그인용 핵심)
- [ ] Identifiers → **+** → **Services IDs**
- [ ] Description: `MediWay Web Sign-In`, Identifier: `com.mediway.app.signin-web`
- [ ] Sign in with Apple 활성화 → **Configure**
- [ ] **Return URLs**:
  ```
  https://mediway-demo.firebaseapp.com/__/auth/handler
  ```
  (Firebase Auth handler 경로 — Firebase Console에서 정확한 URL 복사)
- [ ] **Domains**:
  ```
  mediway-demo.firebaseapp.com
  ```

#### 1-4. Private Key (.p8) 다운로드
- [ ] Keys → **+** → Key Name: `MediWay Sign in with Apple`
- [ ] Sign in with Apple 체크 → Configure → 위 App ID 연결
- [ ] Register → **`.p8` 파일 1회 다운로드 (재다운로드 불가 — 안전 보관)**
- [ ] Key ID 기록 (10자리)

#### 1-5. Firebase Auth Apple 공급자 활성화
- [ ] [Firebase Console](https://console.firebase.google.com/project/mediway-demo/authentication/providers) → Authentication → Sign-in method
- [ ] Apple 공급자 → 사용 설정
- [ ] 입력 항목:
  - Services ID: `com.mediway.app.signin-web`
  - Apple Team ID: (1-1에서 확인한 10자리)
  - Key ID: (1-4에서 생성한 10자리)
  - Private Key: `.p8` 파일 내용 전체 붙여넣기 (`-----BEGIN PRIVATE KEY-----` 포함)
- [ ] 저장 → 상단 배너에 "사용 설정됨" 확인

#### 1-6. 클라이언트 리다이렉트 URI 허용 목록
- [ ] Firebase Auth → 승인된 도메인에 다음 추가 (이미 있으면 skip):
  - `mediway-demo.web.app`
  - `mediway-demo.firebaseapp.com`
  - 로컬 개발: `localhost`

### 완료 체크
- [ ] Apple Developer Program 가입 (Team ID 확보)
- [ ] Services ID + Private Key (.p8) 확보
- [ ] Firebase Auth에 Apple 공급자 등록 완료
- [ ] 승인된 도메인 설정 확인

### 대안 (Apple 가입 지연 시)
- P4 C1~C10 먼저 완료, **C11 Apple Sign-In만 별도 PR**로 후행.
- 가입 대기 기간(최대 일주일)에 법무·JWT secret 등 다른 선결 병행 가능.

---

## 2. 🔑 `FAMILY_INVITE_JWT_SECRET` 생성 + Secret Manager 등록 (C7 · F7)

### 왜 필요한가

- 가족 초대 JWT 토큰 서명·검증에 사용.
- 유출 시 **무단 가족 권한 탈취** 가능 → 크리티컬 시크릿.
- Cloud Function `createFamilyInvite` / `acceptFamilyInvite`가 이 키로 서명·검증.
- LLM_API_KEY와 동일하게 `defineSecret()` 방식.

### 단계

#### 2-1. 강력한 random 키 생성 (로컬)
- [ ] 터미널에서:
  ```bash
  openssl rand -base64 48
  ```
  → 약 64자 base64 문자열. 복사해서 **안전 저장** (1Password, KeePass 등).

#### 2-2. Secret Manager에 등록
- [ ] LLM_API_KEY 때와 동일한 방법:
  ```bash
  cd ~/Project_yeong/02_MediWay/mediway
  firebase functions:secrets:set FAMILY_INVITE_JWT_SECRET --project mediway-demo
  ```
- [ ] 프롬프트에 위 key 붙여넣기 → Enter
- [ ] "Created a new secret version" 확인

#### 2-3. 로테이션 정책
- [ ] 90일마다 key 재생성 권장 (2-1, 2-2 반복)
- [ ] 기존 토큰은 10분 만료라 key 교체 즉시 무효화되어도 UX 영향 미미
- [ ] Calendar 알림 등록 권장: "2026-07-22 JWT secret 로테이션"

### 완료 체크
- [ ] `openssl`로 random secret 생성 완료
- [ ] Secret Manager에 `FAMILY_INVITE_JWT_SECRET/versions/1` 등록 확인
- [ ] 키 값은 안전한 저장소(패스워드 매니저)에 백업

---

## 3. ⚖️ 법무 검토 — 가족 대리 범위 + PIPA 처리방침

### 3-1. 가족 대리 범위 자문

**질의 주제:**
- **대리 권한의 법적 근거**
  - 민법상 임의대리 (§114~)
  - 의료법상 진료 정보 공유 규정
- **권한 2단계 설계 적정성** — reader vs delegate
- **허용 범위**:
  - reader: 일정 · 대기 순번만
  - delegate: 예약 · 결제 · 처방 · 진단 상세

**결정 필요:**
- [ ] **대리인 자격**: 직계 가족만 (부모·자녀·배우자)? 또는 친인척 포함?
- [ ] **미성년자 피대리인 처리**: P4에서는 성인(만 19세+)끼리만 → P5에서 법정대리인 확인 추가
- [ ] **피후견인**: 민법상 성년후견 등기사항증명서 필요 여부
- [ ] **결제 대리의 상한**: 무제한? 일일·월간 한도?
- [ ] **응급 시 예외 조항**: 본인 동의 불가능한 응급상황에서 가족 대리 범위

**질의 템플릿 (법무팀·외부 변호사 제출용):**

> 병원 모바일앱 MediWay의 "가족 대리" 기능 법적 검토 요청
>
> 1. 본인이 JWT 서명 초대 링크를 가족에게 전송·수락받은 뒤, 가족이 앱을 통해 본인의 진료 예약·결제·처방 조회를 대리 수행하는 구조의 법적 적정성 (민법상 임의대리 vs 의료법상 정보 공유)
> 2. reader(일정·대기순번) / delegate(전체) 2단계 권한 구조의 유효성
> 3. 모든 접근을 audit_logs/family_access/*에 기록·본인에게 요약 알림 발송하는 방식이 개인정보 동의 원칙을 충족하는지
> 4. 미성년자·피후견인을 대리 대상에서 배제하고 성인 간 대리만 지원하는 정책의 법적 리스크
> 5. 권한 해제 즉시 access 차단 + audit 보존 기간 권장치 (제안: 3년)
>
> 참고 자료: 본 문서 + `mediway/docs/PLAN_P4.md` §4~§7

### 3-2. PIPA 처리방침 업데이트

**업데이트 항목:**
- [ ] **수탁 현황**: 가족 대리인이 peer로서 본인 정보에 접근한다는 점 (3자 제공이 아닌 동의 기반 공유)
- [ ] **보유 기간**:
  - audit_logs: **3년** (일반 권고)
  - 해제된 가족 grant: 30일 후 soft-delete
- [ ] **민감정보 동의**: 진단명·처방 내용이 가족에게 노출 가능함을 사용자가 사전 동의
- [ ] **해제 권리**: 언제든 대리인 연결 해제 가능 + audit 확인 가능 명시
- [ ] **문의 창구**: 개인정보 보호 책임자 연락처

**완료 체크:**
- [ ] 법무팀·외부 자문 서면 의견 수령
- [ ] PIPA 처리방침 개정 초안 작성
- [ ] 개정 처리방침 앱 내 노출 UI 확정 (로그인 시 동의 재취득)
- [ ] 변경 사항 공지 이력 보관

### 3-3. 대안 (법무 지연 시)

법무 결론까지 2~4주 걸릴 수 있다. 그사이 구현은 진행하되:

- Feature flag `features.familyDelegation=false` 기본값으로 배포
- demo 병원만 true로 설정해 내부 QA
- 법무 통과 후 병원별 flag on — **점진 롤아웃**

---

## 4. 🧒 미성년자·피후견인 대리 제외 처리 (P4 정책)

### 왜 P4에서는 성인만

- 미성년자 대리: 친권자 확인 + 가족관계증명서 필요 → UI 복잡도 폭발
- 피후견인 대리: 성년후견 등기사항증명서 필요 → 전자문서 파싱 필요
- 법적 리스크 < 구현 복잡도 → **P5에서 별도 phase**

### P4 구현 시 적용

- [ ] 가족 초대 생성 UI에 고지문:
  > "본 기능은 만 19세 이상 성인 간 대리에만 이용 가능합니다. 미성년자·피후견인 대리는 추후 별도 제공됩니다."
- [ ] 사용자 profile에 `birthdate` 있으면 만 19세 미만 차단
- [ ] birthdate 없으면 체크박스 "만 19세 이상입니다" 필수 (간편 확인)

### P5+ 계획 (이 파일 범위 밖)
- 법정대리인 서류 업로드 (가족관계증명서 PDF)
- staff/admin 수동 승인 플로우
- 성년후견 등기사항증명서 API (법원 전자제공)

---

## 5. 🚀 최종 체크리스트 (다음 세션 진입 조건)

체크박스 전부 완료 시 `mediway/plusultra/p4` 분기 + C1 착수 가능.

### 🚨 필수 (P4 C6-C9 가족 대리 착수 전)
- [ ] `FAMILY_INVITE_JWT_SECRET` Secret Manager 등록
- [ ] 법무 검토 의뢰 발송 (§3-1 질의 템플릿)
- [ ] 미성년자 제외 정책 확정 (§4)

### 🔔 중요 (P4 C11 Apple Sign-In 착수 전)
- [ ] Apple Developer Program 가입 + Team ID 확보
- [ ] Services ID + Private Key(.p8) 생성
- [ ] Firebase Auth Apple 공급자 활성화
- [ ] 승인된 도메인 확인

### ⚖️ 중요 (배포 전)
- [ ] 법무 검토 서면 의견 수령
- [ ] PIPA 처리방침 업데이트 초안
- [ ] 사용자 고지 UI 문구 확정 (§3-2, §4)

### 📋 권장 (병행 가능)
- [ ] P3_PREREQUISITES.md의 Track 2 선결과 병행 진행 (카카오 심사·알림톡)
- [ ] 60대+ 사용자 연구 대상자 3명 섭외 (P4 통합 QA용)

---

## 6. 🚪 다음 세션에서 할 일 (예상)

위 체크박스 기준 완료도에 따라:

### Case A: 전부 완료
→ `mediway/plusultra/p4` 브랜치 생성 + C1(고령자 모드 스케일) 즉시 착수

### Case B: 법무 대기, 나머지 완료
→ C1-C5 (고령자 모드·TTS·응급 polish) + C11 (Apple Sign-In) 먼저
→ C6-C10 (가족 대리)는 법무 통과 후 feature flag 유지로 선반영

### Case C: Apple 가입 지연
→ C1-C10 먼저 완료 → Apple Sign-In만 **P4.1 별도 PR**로 분리

### Case D: 전부 대기
→ P3 Track 2 (카카오페이·알림톡 심사 후)를 먼저 재개 — 선결 조건이 병행되므로 시간 손실 최소화

---

## 7. 🔗 바로가기 (URL 모음)

### Apple
- Developer Program: https://developer.apple.com/programs/
- Certificates, Identifiers & Profiles: https://developer.apple.com/account/resources/
- Sign in with Apple Docs: https://developer.apple.com/sign-in-with-apple/get-started/

### Firebase
- Console: https://console.firebase.google.com/project/mediway-demo
- Auth 공급자: https://console.firebase.google.com/project/mediway-demo/authentication/providers
- Secret Manager: https://console.cloud.google.com/security/secret-manager?project=mediway-demo

### 법률 참고
- 개인정보 보호법(PIPA) 전문: https://www.law.go.kr/법령/개인정보보호법
- 의료법 전문: https://www.law.go.kr/법령/의료법
- 민법 제114조 (대리 행위의 효력): https://www.law.go.kr/법령조문리스트/민법/제114조

### 현재 코드
- PR #3 (P3 Track 1): https://github.com/HorangEe02/Project_yeong/pull/3
- `mediway/develop @ 8c38c97` — PLAN_P4 커밋 완료
- `docs/PLAN_P4.md` — P4 구현 계획서

---

_작성일: 2026-04-23 · 다음 세션 진입 전 이 체크리스트 완료 후 재개_
