# MediWay 배포 체크리스트

> **작성일**: 2026-04-24 (Phase A-1, T0-2 대응)
> **동기**: 2026-04-24 hosting 배포 시 local source가 production 이전 버전이어서 환자 UI·VisitPlan이 퇴행한 사건(root cause: local≠prod 간과) 재발 방지용.

## 0. 핵심 원칙 3가지

1. **Local ≠ Deployed 가능성을 항상 의심하라** — 특히 여러 dev 환경·브랜치·동시 작업이 있을 때.
2. **Hosting 배포는 preview channel 먼저, live는 검증 후** — 한 스텝으로 끝나는 deploy는 롤백 리스크가 너무 크다.
3. **Rules/Functions는 frontend와 배포 분리 가능** — 한 장소에 묶을 이유 없음. 상호 영향 없는 변경은 따로 배포.

---

## 1. Hosting 배포 Pre-flight (최중요)

### 1.1 Local/Production 동기화 검사
```bash
# 현재 live 중인 version 파일 해시 가져오기
TOKEN=$(gcloud auth print-access-token)
SITE=mediway-demo
CUR_VER=$(curl -s -H "Authorization: Bearer $TOKEN" -H "X-Goog-User-Project: $SITE" \
  "https://firebasehosting.googleapis.com/v1beta1/sites/$SITE/releases?pageSize=1" \
  | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d['releases'][0]['version']['name'].split('/')[-1])")

# 해당 버전의 assets 파일명 출력
curl -s -H "Authorization: Bearer $TOKEN" -H "X-Goog-User-Project: $SITE" \
  "https://firebasehosting.googleapis.com/v1beta1/sites/$SITE/versions/$CUR_VER/files?pageSize=50" \
  | python3 -c "import json,sys;print('\n'.join([f['path'] for f in json.loads(sys.stdin.read())['files']]))" | sort

# 로컬 dist/ 동일 구조 확인
( cd mediway && ls dist/ dist/assets 2>/dev/null | sort )
```

**⚠️ 이 파일 리스트가 근본적으로 다르면 STOP.** local이 production 이전 빌드일 가능성. T0-1 Local Sync 먼저 수행.

### 1.2 Preview Channel 선행 배포

```bash
cd mediway
# 새 preview 채널 (7일 TTL)
firebase hosting:channel:deploy "preview-$(date +%Y%m%d-%H%M)" --project mediway-demo --expires 7d
```

위 명령 출력의 preview URL (예: `https://mediway-demo--preview-20260424-1430-XXXXX.web.app`)에서:
- 🧪 환자 QR 플로우 (익명): `/patient` → `/patient/:sessionId`
- 🧪 환자 로그인 플로우: `signIn → /account/visits → /patient`
- 🧪 Staff: 로그인 → `/staff` → 방문 계획 생성·전송
- 🧪 Admin 대시보드: `/admin` 6지표 모두 수치 표시 여부
- 🧪 Admin 병원관리: `/admin/hospitals` → 상세 진입 가능 여부

### 1.3 Live 배포

preview 이상 없을 때만:
```bash
firebase deploy --only hosting --project mediway-demo --non-interactive
```

배포 직후:
- ✋ **2분 대기** (CDN 전파)
- 🧪 로그아웃 상태로 live URL 접근 → 랜딩 페이지 렌더 확인
- 🧪 `Cmd+Shift+R` 하드 리프레시 후 `/admin` 정상 동작 확인
- 🧪 Sentry/Firebase console "Hosting" 섹션에서 에러율 5분 관측

---

## 2. Cloud Functions 배포 Pre-flight

### 2.1 Orphan function 점검
```bash
# 현재 배포된 함수 vs 로컬 소스 diff
firebase functions:list --project mediway-demo

# 로컬 export 확인
cd mediway/functions
grep -E "^export " src/index.ts
```

양쪽 리스트가 일치하지 않으면:
- **production 있는데 local 없음** → `firebase functions:delete <NAME> --region <REGION>` (소스 없음 확인 후)
- **local 있는데 production 없음** → 정상, deploy 시 생성

### 2.2 Secrets 바인딩 확인
```bash
# 각 secret 존재 여부
for S in KAKAO_CLIENT_ID KAKAO_CLIENT_SECRET KAKAO_ADMIN_KEY NAVER_CLIENT_ID NAVER_CLIENT_SECRET; do
  firebase functions:secrets:access "$S" --project mediway-demo 2>&1 | tail -1
done
```

missing secret으로 deploy하면 **실패** (2nd gen은 deploy time에 검증). [SECRETS_SETUP.md](./SECRETS_SETUP.md) 참고.

### 2.3 빌드 + 배포
```bash
cd mediway/functions
npm run build
cd ..
firebase deploy --only functions --project mediway-demo --non-interactive --force
```

`--force`는 CI 환경에서만 사용. 대화형은 생략해서 confirmation 받기.

---

## 3. RTDB Rules 배포 Pre-flight

### 3.1 JSON 문법 + 논리 사전 점검
```bash
python3 -c "import json; json.load(open('mediway/database.rules.json'))"
# '//' 최상위 주석 키 금지 — Firebase parser가 rules sibling을 거부함
grep -E '^\s*"//' mediway/database.rules.json && echo "❌ 주석 키 제거 필요" || echo "✅ OK"
```

### 3.2 Migration 선행 여부
Rules v2(Commit 8 이후) 배포 전 필수:
- `verifyMigration` 또는 `cli-verify-claims.ts` → `ready: true` 확인
- 모든 활성 유저의 `customClaims.role` 존재해야 401 방지

### 3.3 E2E 브라우저 검증
`public/e2e-rules-v2.html` 로드:
- platformAdmin / admin / staff / patient 각 role로 로그인 후 시나리오 실행
- Read/Write allow/deny 기대값과 실제값 일치 확인

### 3.4 배포 + 관측
```bash
firebase deploy --only database --project mediway-demo --non-interactive --force
```

배포 직후 15분간:
- Firebase Console > Realtime Database > Usage → error rate
- Functions logs에서 `PERMISSION_DENIED` 급증 여부

---

## 4. Rollback 매트릭스

| 대상 | 방법 | 소요 |
|---|---|---|
| Hosting | Firebase Console UI Rollback 또는 REST API `POST /sites/{id}/releases?versionName=sites/{id}/versions/{OLD_ID}` | 즉시 (~30초) |
| Rules | `cp database.rules.legacy.json database.rules.json && firebase deploy --only database` | 1~2분 |
| Functions | 구버전 소스로 checkout → rebuild → `firebase deploy --only functions` | 2~3분 |
| Secrets | `firebase functions:secrets:destroy <NAME>@<N>` + 재등록 | 즉시 |
| Claim 일괄 회수 | 별도 스크립트 필요 (setCustomUserClaims(uid, {}) 전체 루프) | ~5분/1000유저 |

### 4.1 Hosting REST API Rollback (실전 검증됨)

```bash
TOKEN=$(gcloud auth print-access-token)
OLD_VER="<target_version_id>"  # releases list에서 확인
curl -s -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Goog-User-Project: mediway-demo" \
  -H "Content-Type: application/json" \
  "https://firebasehosting.googleapis.com/v1beta1/sites/mediway-demo/releases?versionName=sites/mediway-demo/versions/$OLD_VER" \
  -d '{}'
```

---

## 5. 체크리스트 (배포 전 한 번씩 확인)

### Hosting
- [ ] Local `dist/assets/` 파일명이 현재 live release와 다른 이유를 알고 있다 (= 진짜 변경이 있다)
- [ ] Preview channel 배포 성공 + 3개 핵심 플로우 수동 smoke test 통과
- [ ] 로컬 `git status` 깨끗, 커밋 완료
- [ ] 배포 후 2분 대기 후 live URL 정상 렌더

### Functions
- [ ] `firebase functions:list`와 `src/index.ts` export 집합 일치 (orphan/missing 없음)
- [ ] 모든 secret 등록됨 (`defineSecret` 참조 파일 전부 검사)
- [ ] `npm run build` 0 errors
- [ ] vitest 전체 통과
- [ ] 이전 커밋에서 변경된 onCall의 signature 파괴적이지 않음

### Rules
- [ ] `database.rules.legacy.json` 백업 최신 상태
- [ ] `verifyMigration ready: true` 확인
- [ ] JSON valid, 최상위 `rules` key 외 sibling 없음
- [ ] E2E HTML 테스트 시나리오 전원 pass
- [ ] 배포 후 15분 PERMISSION_DENIED rate 관측

### 공통
- [ ] git push (local 반영)
- [ ] Slack/Notion 배포 공지
- [ ] Rollback 절차 손닿는 위치에 열어둠
