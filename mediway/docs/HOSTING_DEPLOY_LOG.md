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
