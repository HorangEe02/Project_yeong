# Firebase Hosting 배포 이력

> **2026-04-26 정책 전환**: B-3.10 (hospital slug routing) + F1 (wait queue UI 통합)
> 완료로 local source 가 prod parity 에 도달 → 전체 `firebase deploy --only hosting`
> 가능. 본 문서는 본 배포(LIVE) 와 surgical patch 배포 모두 기록한다.

---

## 2026-04-26 — Scenario E (AI Triage) 본 배포

- **이전 LIVE 번들**: `index-D_OWDnbO.js` (B-3.10 + F1)
- **신 LIVE 번들**: `index-paEulSKd.js` + `index-CycsFZ0b.css` (CSS 변경 없음)
- **Release time**: 2026-04-26T02:49:19Z (11:49 KST)
- **Functions**: `triageSymptoms(asia-northeast3)` 신규 create — 같은 시점 deploy
- **Channel**: `live` (mediway-demo.web.app)

### 포함 변경 (7 commit, `b2ebbb0` → `8724cbe`)

E Scenario AI Triage 재작성:
- `b2ebbb0` triage types + Zod schema
- `15e1dd4` triageSymptoms cloud function (Gemini + epoch-hour bucket + audit dual-write)
- `d78ffe6` src/services/triage.ts wrapper
- `1773eb8` TriageWidget UI
- `9c4c57a` HomeTab 통합 + features.aiTriage 가드
- `3fc095e` scenario E 통합 smoke (8 케이스)
- `8724cbe` docs(E)

### 배포 검증 (자동)
- HTTP 200 (`https://mediway-demo.web.app/`)
- 신 번들 hash 로컬 dist / LIVE 3자 일치
- LIVE etag `728d2a9e39d698e1...`
- Functions: `Successful create operation` for `triageSymptoms(asia-northeast3)`

### 활성화 조건 (admin 토글 후)
- platformAdmin 가 `/admin/hospitals/{slug}/profile/features/aiTriage` 를 `true` 로 설정
- 환자 홈 (`/h/{slug}/patient/home`) 에서 TriageWidget 노출 — RTDB 토글 즉시 반영
- demo 병원 default `false` 유지 → 토글 전까지는 위젯 숨김 (회귀 없음)

### 후속 시각 검증 체크리스트
1. platformAdmin 로그인 → `/admin/hospitals/demo` → features.aiTriage 체크
2. 환자 (`p0107044@gmail.com`) 로 `/h/demo/patient/home` 진입
3. 홈 탭에 "AI 진료과 추천" 위젯 노출 확인
4. "2일째 기침과 미열이 있어요" 입력 → 5초 이내 Top-3 카드
5. 11번째 호출 시 "약 N분 후 다시 시도" 안내
6. "갑자기 가슴이 너무 아파요" → emergencyNotice + 응급의학과 1순위
7. Firebase Console → Functions → `triageSymptoms` 로그
8. RTDB `/triage_audit/<pushId>` + `/triage_usage/<uid>/<epochHour>` 갱신

### 롤백 절차 (필요 시)
1. Firebase Console → Hosting → 이전 release `index-D_OWDnbO.js` 옆 "Rollback"
2. Functions: `firebase functions:delete triageSymptoms --region asia-northeast3 --force`
3. (선택) features.aiTriage 토글 off 만 해도 위젯 즉시 숨김 — 가장 빠른 임시 비활성화

---

## 2026-04-26 — B-3.10 + F1 결합 본 배포 (prod parity 달성)

- **이전 surgical patch**: `2b52463a288bc8d4`
- **신 LIVE 번들**: `index-D_OWDnbO.js` + `index-CycsFZ0b.css`
- **Release time**: 2026-04-26T02:15:02Z (11:15 KST)
- **Channel**: `live` (mediway-demo.web.app)
- **Preview 사전 검증**: `preview-b310` (mediway-demo--preview-b310-ahxpd47u.web.app, 동일 번들)

### 포함 변경 (13 commit, `4ed4195` → `35b64c8`)

#### B-3.10 Hospital slug nested routing (6 commits)
- `94077e5` hospitalProfile service + HospitalProfile 타입 (12 unit test)
- `d0d145d` HospitalShell + HospitalContext (13 unit test)
- `7a7bb53` nested `/h/:slug/*` + LegacyHospitalRedirect (8 unit test)
- `2eb602d` Header + HospitalHomePage 가 nested 인식
- `5e5f6cc` App-level routing 통합 smoke (10 케이스)
- `33daf30` 추적 갱신

#### F1 Wait queue UI 통합 (7 commits)
- `3174225` `useHospitalFeatures()` + FEATURE_DEFAULTS (13 unit test)
- `fc4650c` HospitalHomePage tab visibility from features (10 unit test)
- `b230db5` WaitQueueWidget hospital-aware + features-gated + empty CTA (15 unit test)
- `bcd9f15` AppointmentsTab → useHospital().slug
- `ad4c5d6` StaffSubNav + Staff/StaffQueue 통합 헤더 (6 unit test)
- `b36936b` 시나리오 A-D 통합 smoke (6 케이스)
- `35b64c8` docs

### 검증 (배포 직후 자동)
- HTTP 200 (`https://mediway-demo.web.app/`)
- `index-D_OWDnbO.js` 가 LIVE / preview / 로컬 dist 일치
- LIVE etag `f57051ab0a1ca219...`

### 후속 (24h 모니터링 후)
1. legacy `/audit_logs/*` + `/visit_plans/*` 트래픽 0 건 확인
2. `scripts/purge-legacy-paths.py --apply --confirm` 실행
3. RTDB rules 의 legacy write 관대처리(`7ec98f8`) 재차 tightening

### 롤백 절차 (필요 시)
1. Firebase Console → Hosting → 이전 release `2b52463a288bc8d4` 옆 "Rollback" 버튼
2. 또는 CLI: `firebase hosting:rollback` (대화형)

---

## 2026-04-24 — Landing "환자" 버튼 V2 라우팅 수정

- **Release**: `1f674c8d5ae50dce`
- **Previous (rollback target)**: `690c50e1e208e60a`
- **Release time**: 2026-04-24T06:20:32Z (15:20 KST)

### 문제
사용자가 `https://mediway-demo.web.app/` 접속 후 "환자" 버튼 클릭 시 V1 `/patient`
페이지로 이동. Prod v2 번들 내부에 `/h/:slug/patient/home` (HospitalHomePage)는
이미 존재하나, LandingPage의 Link가 `to:/patient` (V1) 로 하드코딩돼 있었음.

### 수정
Bundle byte-level surgical patch 1건:
```
to:`/patient`,icon:(0,J.jsx)(Jr,{className:`h-6 w-6 text-primary`}),title:`환자`
→
to:`/hospitals/select`,icon:(0,J.jsx)(Jr,{className:`h-6 w-6 text-primary`}),title:`환자`
```

`/hospitals/select` 선택 이유: prod 번들에 이미 auto-redirect 로직 존재.
- 로그인 환자 → `/h/{hid}/patient/home` 로 redirect
- 익명 → 병원 선택 picker 표시

### 영향
- ✅ V2 flow 복구
- ✅ prod v2 번들의 다른 feature 전부 보존
- ⚠️ Landing → 환자 → V1 QR scan 직접 진입 경로 제거 (V1은 `/patient` URL로 계속
  접근 가능)

### 방법
1. Prod 번들 `/assets/index-BGK9Zs9J.js` 를 local `/tmp/mediway-patch-staging/` 에 복사
2. 유일한 매치 1건 확인 (grep 검증) 후 문자열 치환
3. 새 filename `index-v2fix1.js` 로 저장 (cache busting)
4. `/index.html` 의 `<script src>` 를 새 filename 으로 업데이트
5. Firebase Hosting REST API:
   - `POST /versions` → 새 version 생성
   - `:populateFiles` with 전체 20 path map (17 기존 + 1 교체 + 2 신규)
     - 기존 17개는 CDN 에 이미 있어 upload 불필요
     - 2개만 `uploadRequiredHashes` 로 반환 → gzip + SHA-256 POST
   - `PATCH ...?updateMask=status` body `{status: FINALIZED}`
   - `POST /releases?versionName=...` → publish

### 롤백 절차
```bash
TOKEN=$(gcloud auth print-access-token)
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Goog-User-Project: mediway-demo" \
  "https://firebasehosting.googleapis.com/v1beta1/sites/mediway-demo/releases?versionName=sites/mediway-demo/versions/690c50e1e208e60a"
```

### 이 방식의 전제
Local source가 prod 수준에 도달하지 못한 상황에서 `firebase deploy` 로 전체
번들을 교체하면 퇴행 발생. 따라서 prod 번들에서 필요한 바이트만 치환하고
해시를 새로 계산해 올리는 방식이 안전.

T0-1 Local Sync 완료 후 이 런북은 역할을 마친다.

---

## 2026-04-24 — `1f674c8d5ae50dce` → `e425dbd4ec15af83` config 복구 (긴급)

- **Release**: `e425dbd4ec15af83`
- **Previous**: `1f674c8d5ae50dce` (config 공백으로 SPA rewrite 손실)
- **Release time**: 2026-04-24T07:04:10Z (16:04 KST)

### 문제
사용자가 딥링크 URL (예: `/login`, `/signup`, `/h/demo/patient/home`) 에서 브라우저
새로고침 시 Firebase Hosting 기본 "Page Not Found" 표시.

### 원인
직전 surgical patch 배포 (`1f674c8d5ae50dce`) 에서 Firebase Hosting REST API 로
새 version 을 만들 때 `config` 필드를 비워 버림 (`{}`). 이전 version
`690c50e1e208e60a` 에는 다음이 있었음:
```json
"config": {
  "rewrites": [{"glob": "**", "path": "/index.html"}],
  "headers": [
    {"glob": "/index.html", "headers": {"Cache-Control": "no-cache, no-store, must-revalidate"}},
    {"glob": "/assets/**", "headers": {"Cache-Control": "public, max-age=31536000, immutable"}}
  ]
}
```
패치 배포 시 파일만 populateFiles 로 지정하고 config 는 누락 → SPA rewrite 없음
→ 어떤 client-side route 도 직접 접근 시 404.

### 수정
새 version 을 config 포함으로 생성:
```python
api('POST', '/v1beta1/sites/{SITE}/versions',
    body={'config': {rewrites, headers}})   # ← 핵심: config 본문에 포함
```

파일 map 은 직전 version (`1f674c8d5ae50dce`) 과 동일 20 path 를 populateFiles.
모든 hash 가 이미 CDN 에 존재 → upload 0건, 빠름. Finalize + Release.

### 영향
- ✅ SPA rewrites 복구 — `/login` 외 모든 client-side route 새로고침 200
- ✅ `/assets/**` immutable cache + `/index.html` no-cache 복구
- ✅ Landing V2 redirect 패치 (`to:/hospitals/select`) 유지
- ✅ 패치된 JS 파일명 (`/assets/index-v2fix1.js`) 유지

### 교훈
REST API 로 `POST /versions` 생성 시 `config` 를 빈 body 로 보내면 default 가
아닌 **빈 config** 로 생성된다. Firebase Hosting CLI 는 `firebase.json` 을
읽어 자동으로 config 를 채우지만, REST API 직접 호출 시 명시해야 함.
surgical patch 스크립트 재활용 시 이 체크리스트 확인:
- [ ] config.rewrites 포함?
- [ ] config.headers 포함?
- [ ] populateFiles 호출 전 version body 에 config 삽입?

---

## 2026-04-24 — e2e HTML error banner 색상 브랜드 blue 롤백

- **Release**: `fb6c3ea4c03acbb8`
- **Previous**: `e425dbd4ec15af83`
- **Release time**: 2026-04-24T07:09:47Z (16:09 KST)

### 변경
5개 e2e HTML 의 error/fail 스타일을 Tailwind red-50 핑크 → MediWay primary blue 로.

```
.banner.error { background:#fef2f2; color:#b91c1c }   →   background:#eff6ff; color:#004e9f
.fail        { color:#c33 }                             →   color:#004e9f
.banner.fail { background:#fef2f2; color:#991b1b }      →   background:#eff6ff; color:#004e9f
```

Local 파일 수정 + Firebase Hosting REST API 로 3개 파일만 업로드:
- e2e-hospital-isolation.html
- e2e-visit-plan.html
- e2e-wait-queue.html

(e2e-chatbot.html, e2e-rules-v2.html 은 LIVE 미배포 — local commit 만)
(e2e-tab-session.html 은 해당 스타일 없음)

Landing V2 redirect 패치 (`to:/hospitals/select`) + SPA rewrites + cache headers
모두 그대로 유지.

### 검증
- `/e2e-hospital-isolation.html` LIVE fetch 시 `color:#004e9f` 확인
- `/login` 새로고침 여전히 200 (rewrites 정상)

---

## 2026-04-24 — Landing "환자" 버튼 데모 병원 직접 라우팅

- **Release**: `8da78dc2d7001b6c`
- **Previous**: `fb6c3ea4c03acbb8`
- **Release time**: 2026-04-24T07:20:36Z (16:20 KST)

### 문제
이전 surgical patch(`1f674c8d5ae50dce`)는 Landing "환자" 버튼을 `/hospitals/select`
로 보내도록 수정. 이 경로에서 로그인된 환자를 auto-redirect 할 것으로 기대했으나
실제로는 `_j()` 컴포넌트의 redirect 조건이 **URL query parameter `?hospital=<slug>`**
만 검사:

```js
let t = searchParams.get('hospital');        // user profile 과 무관
return t && hospitals.some(h => h.slug === t)
  ? <Navigate to={`/h/${t}/patient/home`} />
  : <picker>
```

→ `profile.hospitalId` 가 `demo` 여도 쿼리가 없으면 picker 에서 멈춤.

### 수정
현 LIVE 는 demo 단일 병원 환경이므로 Landing 버튼을 `/h/demo/patient/home` 으로
**직접** 라우팅. 중간 picker 단계 제거.

```
to:`/hospitals/select` → to:`/h/demo/patient/home`
```

원본 prod 번들 (`/assets/index-BGK9Zs9J.js`) 에서 새로 patch → 새 filename
`index-v3fix1.js`. 기존 `v2fix1.js` 는 버전에 같이 포함 (rollback 안전).

### 영향
- ✅ Landing → 환자 → 바로 데모 병원 V2 홈 (한 번에 이동)
- ✅ serving config (rewrites + cache headers) 유지
- ✅ e2e 색상 롤백 유지 (primary blue)
- ⚠️ 다병원 환경으로 확장 시 이 route 는 slug 조건부 처리로 재설계 필요

### 다음 세대 번들 교체 시 작업 순서
T0-1 Local Sync 완료 후 `firebase deploy --only hosting` 으로 전체 번들을 교체할 때
위 surgical patch 세 번 (`v2fix1` → `v3fix1` → 색상 롤백) 의 결과가 local 소스에 모두
반영돼 있는지 확인 필수:
- [ ] LandingPage "환자" 버튼이 auth 상태 기반으로 조건부 라우팅
- [ ] e2e HTML 에 primary blue 적용
- [ ] SPA rewrites + cache headers 가 firebase.json 에 설정됨

---

## 2026-04-24 — legacy hospitalId 상수 Lh 를 'demo' 로 정정

- **Release**: `770e5eeaddfb1ee9`
- **Previous**: `8da78dc2d7001b6c`
- **Release time**: 2026-04-24T07:31:19Z (16:31 KST)

### 문제
의료진 "동선 전송 및 관리 센터" 에서 QR 매칭 후 [동선 전송] 클릭 시
"동선 전송에 실패했습니다. 다시 시도해주세요." 오류.

### 원인
prod 번들에 남은 P1 시대 하드코딩 상수:
```js
var Lh = `demo-hospital`;      // 레거시 hospitalId
// ...
let a = { sessionId, patientUid, staffUid, qrToken, hospitalId: Lh, ... };
await wh(a);   // sessions/{sessionId} write
```

sessions 규칙은 `newData.hospitalId === auth.token.hospitalId` 요구.
현재 시스템의 hospitalId 는 `'demo'`. staff/admin 계정이 `Lh='demo-hospital'` 로
쓰려 하면 `'demo-hospital' !== 'demo'` 로 permission_denied. platformAdmin 만
bypass 조건으로 통과 (박준영 계정에서는 성공했을 것).

### 수정
번들 surgical patch 1건 — unique match 확인 후:
```
var Lh=`demo-hospital`,Rh=3;   →   var Lh=`demo`,Rh=3;
```
Δ = -9 bytes. 새 filename `index-v4fix1.js`.

남은 `demo-hospital` 2건은:
- `Fm.hospitalId` (floor map 정적 데이터)
- `Rm.id` (building metadata 정적 데이터)
→ RTDB rule과 무관한 로컬 참조 — 의도적으로 변경 없음.

### 영향
- ✅ Staff/admin 의 동선 전송 (`sessions/{sessionId}` write) 성공
- ✅ Landing → 환자 V2 redirect, SPA rewrites, e2e primary blue 모두 유지
- ⚠️ `Dh(uid, Lh)` mismatched 경고: 레거시 plan 에 `hospitalId='demo-hospital'` 가
  저장돼 있다면 이제 mismatched=true. 실제 DB 엔트리 보면 소수/없음 추정.

### 관련 수정 (RTDB 단일 write, 배포 불필요)
`hospitals/demo/profile/themeColor`: `#deadbe` (분홍) → `#004e9f` (primary blue).
오염 원인: e2e-hospital-isolation.html 시나리오 #7 이 platformAdmin 로 실행될 때
`#deadbe` 를 쓴 부작용.

