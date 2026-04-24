# Firebase Hosting 배포 이력 (surgical patch 전용)

Local source가 production 수준에 도달하기 전까지 `firebase deploy --only hosting`
전체 배포는 금지. 이 문서는 prod 번들에 최소 패치를 가하기 위한 surgical
배포만 기록한다.

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

