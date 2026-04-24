# Secrets Setup — MediWay

> **작성일**: 2026-04-24 (Commit 7.5)
> **범위**: Firebase Secret Manager 이관 + 프론트 env 분리 + Kakao/Naver 콘솔 등록 체크리스트

## 0. 원칙

| 카테고리 | 보관 위치 | 예시 |
|---|---|---|
| **Public (클라이언트 번들 포함 OK)** | `.env.local` → Vite `VITE_*` | Firebase apiKey, Kakao JavaScript 키, Naver client_id |
| **Private (서버만)** | Firebase Secret Manager | Kakao REST API 키·Client Secret, Naver Client Secret, Kakao Admin 키 |
| **로컬 개발 Private** | `mediway/functions/.secret.local` | 위 Private 키들의 로컬 값 (`.gitignore` 적용됨) |

🔥 **Git에 절대 들어가면 안 되는 것**: `.env.local`, `functions/.secret.local`, 그리고 `../data/kakao_api/*` (현재 평문 키가 들어있음).

---

## 1. 현재 MediWay에서 쓰는 Secret 키 매트릭스

| Secret 이름 | 타입 | 어디서 받나 | 어디서 쓰나 |
|---|---|---|---|
| `KAKAO_CLIENT_ID` | REST API 키 | Kakao Developers > 앱 설정 > 앱 키 > REST API 키 | `functions/src/index.ts :: kakaoAuth` |
| `KAKAO_CLIENT_SECRET` | 보안 코드 | Kakao Developers > 제품 설정 > 카카오 로그인 > 보안 > Client Secret | `kakaoAuth` (추가 보안) |
| `NAVER_CLIENT_ID` | REST | Naver Developers > 앱 > Client ID | `naverAuth` |
| `NAVER_CLIENT_SECRET` | 보안 | Naver Developers > 앱 > Client Secret | `naverAuth` |
| `KAKAO_ADMIN_KEY` | 관리자 | Kakao Developers > 앱 설정 > 앱 키 > Admin 키 | (P3 알림톡에서 사용 예정, 미배포) |

프론트엔드용 (클라이언트 번들):
| Env 이름 | 타입 | 메모 |
|---|---|---|
| `VITE_KAKAO_CLIENT_ID` | JavaScript 키 | OAuth authorize URL의 `client_id` — **REST 키가 아닌 JS 키** |
| `VITE_KAKAO_MAP_KEY` | JavaScript 키 | Kakao Maps SDK 동일 키 |
| `VITE_NAVER_CLIENT_ID` | Client ID | OAuth authorize URL의 `client_id` |

---

## 2. 로컬 개발 셋업 (최초 1회)

### 2.1 프론트 env

```bash
cd mediway
cp .env.local.example .env.local
# .env.local을 편집해 실제 값으로 교체
```

### 2.2 Functions Secret (로컬 emulator)

`mediway/functions/.secret.local` 파일을 **새로 생성** (placeholder를 실제 값으로 치환):

```
KAKAO_CLIENT_ID=<kakao-rest-api-key>
KAKAO_CLIENT_SECRET=<kakao-login-client-secret>
KAKAO_ADMIN_KEY=<kakao-admin-key>
NAVER_CLIENT_ID=<naver-client-id>
NAVER_CLIENT_SECRET=<naver-client-secret>
```

> 🔥 **실제 키는 이 문서에 작성하지 않는다.** 다음 출처에서 개별 수동 복사:
> - Kakao 키 3종: Kakao Developers 콘솔 (`developers.kakao.com` > 내 애플리케이션 > 앱 설정 · 제품 설정 · 앱 키 · 어드민 키)
> - Naver 키 2종: Naver Developers 콘솔 (`developers.naver.com/apps`)
> - 로컬 보조 참조: `../data/kakao_api/`, `../data/Naver_api/` (이 디렉터리는 outer `.gitignore` 적용되어 push 금지 상태)
>
> 과거 이 문서 또는 `KAKAO_INTEGRATION.md`에 실제 키가 평문으로 포함된 이력이 있다면 **즉시 Kakao/Naver 콘솔에서 재발급** 후 재등록.

이 파일은 `.gitignore`에 포함되어 있어 실수로도 push되지 않음.

### 2.3 Firebase Emulators 실행

```bash
cd mediway/functions
npm run serve   # = build + firebase emulators:start --only functions
```

`defineSecret(...)`.value()는 emulator에서도 `.secret.local`의 값을 읽는다.

---

## 3. 프로덕션 배포 전 (최초 1회)

### 3.1 Firebase Secret 등록

```bash
# 저장소 루트
cd mediway
firebase functions:secrets:set KAKAO_CLIENT_ID
# (입력창이 열림 — 값 붙여넣고 Enter)
firebase functions:secrets:set KAKAO_CLIENT_SECRET
firebase functions:secrets:set NAVER_CLIENT_ID
firebase functions:secrets:set NAVER_CLIENT_SECRET
firebase functions:secrets:set KAKAO_ADMIN_KEY
```

Secret은 Google Cloud Secret Manager에 저장되며, Function 배포 시 런타임에 환경변수로 주입.

### 3.2 배포

```bash
firebase deploy --only functions
```

최초 배포 시 IAM 권한 요청 팝업이 나올 수 있음 — Functions Service Account에 Secret Accessor 역할 부여.

### 3.3 Secret 회전 (키 유출 의심 시)

1. Kakao/Naver 콘솔에서 새 키 발급
2. `firebase functions:secrets:set KAKAO_CLIENT_SECRET` 재실행 → 새 버전 생성
3. `firebase deploy --only functions` → 새 버전 바인딩
4. 구 버전 폐기: `firebase functions:secrets:destroy KAKAO_CLIENT_SECRET@1`

---

## 4. Kakao 개발자 콘솔 설정 체크리스트

### 4.1 앱 설정 > 앱 키
- JavaScript 키, REST API 키, Native 앱 키, Admin 키 확인 (이미 보유)

### 4.2 앱 설정 > 플랫폼 > Web
- 사이트 도메인 추가:
  - `http://localhost:5173`
  - `https://mediway-demo.web.app`
  - (배포 도메인 추가 시마다 갱신)

### 4.3 제품 설정 > 카카오 로그인
- 활성화 ON
- **OAuth Redirect URI** 등록:
  - `http://localhost:5173/auth/callback/kakao`
  - `https://mediway-demo.web.app/auth/callback/kakao`
- **보안 > Client Secret** 활성화 — 값은 Firebase Secret `KAKAO_CLIENT_SECRET`과 동일해야 함

### 4.4 제품 설정 > 카카오 로그인 > 동의 항목
- `profile_nickname` — 필수 동의
- `profile_image` — 선택 동의
- `account_email` — 필수 동의 (이메일로 유저 병합 가능하려면)
- (P4에서 `phone_number`, `birthday` 추가 예정 — Kakao Sync 비즈니스 인증 필요)

---

## 5. Naver 개발자 콘솔 설정 체크리스트

### 5.1 Application 등록
- 사용 API: 네이버 로그인
- 서비스 환경: 웹 애플리케이션
- 서비스 URL: `https://mediway-demo.web.app`
- 네아로 Callback URL:
  - `http://localhost:5173/auth/callback/naver`
  - `https://mediway-demo.web.app/auth/callback/naver`

### 5.2 서비스 제공 정보
- 이메일 주소 — 필수
- 이름 — 필수
- (프로필 사진·전화번호는 옵션)

---

## 6. 보안 이슈 감사 프로토콜

만약 키가 유출되었거나 의심될 때:

1. **즉시 회전** — Kakao/Naver 콘솔에서 해당 키 재발급
2. **Firebase Secret 업데이트** — `firebase functions:secrets:set <NAME>`
3. **재배포** — `firebase deploy --only functions`
4. **git 이력 검사** — 과거에 평문 키가 커밋된 적 있는지 `git log -p -- data/kakao_api/` 등으로 확인
5. **발견 시**: `git filter-repo --path data/kakao_api/ --invert-paths` 로 과거 이력에서 제거 + 모든 clone·fork에 재클론 공지
6. **Audit log 확인** — Kakao Developers 콘솔의 "API 호출 이력"에서 비정상 호출 여부 점검

---

## 7. Commit 7.5 완료 판정 체크

- [x] `.gitignore` (outer + mediway) 에 Secret 파일 경로 포함
- [x] `functions/src/secrets.ts` 에 `defineSecret` 참조 정의
- [x] `kakaoAuth`·`naverAuth` onCall이 `secrets: [...]` 옵션 포함
- [x] `.value()` 기반 참조로 `process.env` 제거
- [x] `.env.local.example` Kakao/Naver 섹션 추가
- [ ] 실제 Secret 등록 (`firebase functions:secrets:set ...`) — **배포 담당자 수동 작업**
- [ ] Kakao/Naver 콘솔 Redirect URI 등록 — **배포 담당자 수동 작업**
- [ ] (옵션) 과거 키 재발급 — `data/kakao_api/` 이력 유출 여부 확인 후 결정

### 다음 단계
- Commit 8 (RTDB Security Rules) — Custom Claims 기반 격리 규칙
- Commit 9 (마이그레이션) — 기존 유저 claim 일괄 주입
- 배포 시 Commit 7 → 7.5 → 8 → 9 순서로 일괄 deploy
