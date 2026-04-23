# scripts/

MediWay 운영·검증 스크립트 모음.

## test-rules.mjs — RTDB 보안 규칙 테스트

P1에서 도입한 tenant 격리 규칙의 회귀 방지용 Emulator 기반 단위 테스트.

### 실행

터미널 1 — Emulator 시작:

```bash
cd 02_MediWay/mediway
firebase emulators:start --only database
# Emulator 로그에 "Database: http://127.0.0.1:9000" 노출 확인
```

터미널 2 — 테스트 실행:

```bash
node scripts/test-rules.mjs
```

### 검증 시나리오

| # | 시나리오 | 기대 |
|---|---|---|
| 1 | demo 환자 → demo profile · pois 읽기 | ✅ |
| 2 | demo 환자 → smch profile 읽기 (공개) | ✅ |
| 3 | demo 환자 → smch pois 읽기 | ❌ 차단 |
| 4 | demo 환자 → smch visit_plans 읽기 | ❌ 차단 |
| 5 | demo staff → demo visit_plans/user-a 읽기 | ✅ |
| 6 | smch 환자 → demo visit_plans/user-a 읽기 | ❌ 차단 |
| 7 | platformAdmin → 임의 병원 pois 읽기 | ✅ |
| 8 | 일반 유저 → profile 쓰기 | ❌ 차단 |
| 9 | platformAdmin → profile 쓰기 | ✅ |
| 10 | 레거시 `visit_plans/{uid}` 본인 쓰기 | ✅ (P2 호환) |
| 11 | 환자 → 타인 `hospitals/demo/visit_plans/other-uid` 쓰기 | ❌ 차단 |

### 배포 게이트

**이 테스트가 통과해야만 `firebase deploy --only database`로 배포합니다.**
Commit 9(마이그레이션) 실행 전 반드시 이 스크립트로 검증.

실패 시 `database.rules.json`을 백업(`database.rules.json.p1-backup`)으로 롤백.

---

## migrate-demo-hospital.mts — 데모 병원 RTDB 마이그레이션 (Commit 9, 1회성)

정적 번들 데이터(`src/data/hospital/*`)와 기존 유저·visit_plans를 Multi-Tenant 구조(`/hospitals/demo/*`)로 이관.

### 전제 조건

1. **백업 필수**: 실행 전 전체 RTDB 스냅샷

   ```bash
   firebase database:get / > backup-pre-p1-migration.json
   ```

2. **서비스 계정 자격증명**: Firebase Console → 프로젝트 설정 → 서비스 계정 → 새 비공개 키 생성 → JSON 다운로드.
   환경변수로 경로 지정:

   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=~/path/to/service-account.json
   ```

3. **Emulator 규칙 테스트 선행**: `npm run test:rules` 통과 확인.

### 실행 순서 (안전 경로)

```bash
# 0. 필수 백업
firebase database:get / > backup-pre-p1-migration.json

# 1. DRY-RUN — 변경 예상만 출력 (실제 쓰기 X)
npx tsx scripts/migrate-demo-hospital.mts --dry-run

# 2. 단계별 확인이 필요하면
npx tsx scripts/migrate-demo-hospital.mts --dry-run --step=2   # POIs만
npx tsx scripts/migrate-demo-hospital.mts --dry-run --step=4   # users 백필만

# 3. 결과 검토 후 실제 반영
npx tsx scripts/migrate-demo-hospital.mts --commit

# 4. Cloud Functions 배포 (Commit 7 회로 활성)
firebase deploy --only functions

# 5. RTDB 규칙 배포 (Commit 8 규칙 활성)
firebase deploy --only database

# 6. 사후 검증: public/e2e-hospital-isolation.html 브라우저로 열어 11 시나리오 통과 확인
```

### Step 내역

| # | 대상 | 설명 |
|---|---|---|
| 1 | `/hospitals/demo/profile` | 프로필 신규 생성 (name·slug·themeColor·features) |
| 2 | `/hospitals/demo/pois/{id}` | 31개 POI (src/data/hospital/pois.ts) |
| 3 | `/hospitals/demo/floor-plans/{n}` | 4개 층 평면도 데이터 |
| 4 | `/users/{uid}` | `primaryHospitalId='demo'`, `hospitalIds=['demo']` 백필 |
| 5 | `/visit_plans/{uid}` | `hospitalId='demo'` 필드 주입 (레거시 경로 유지) |

### 멱등성

모든 step은 재실행 안전 — 이미 존재하면 skip. 부분 실패 시 재실행 가능.

### 환경변수

| 이름 | 기본 | 용도 |
|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | — | 서비스 계정 JSON 경로 (필수) |
| `MEDIWAY_DB_URL` | `https://mediway-demo-default-rtdb.firebaseio.com` | 대상 RTDB URL 오버라이드 |
| `VERBOSE` | — | 모든 skip 경로 상세 로그 |

### 롤백

1. 마이그레이션 직후 문제 발견 시:
   ```bash
   firebase database:update / backup-pre-p1-migration.json
   ```
2. 규칙 배포가 완료된 상태라면:
   ```bash
   cp database.rules.json.p1-backup database.rules.json
   firebase deploy --only database
   ```
