# dev-guides/25 — 인수인계 체크리스트

> **Phase**: 4 | **선행 작업**: Phase 1-3 모두 완료 | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

학생 팀이 떠난 후 발주처(레몬헬스케어)가 **즉시 운영을 이어받을 수 있도록** 모든 산출물을 정리·문서화·검증한다. 코드, 문서, 계정, 데이터, 비밀키 모두 포함.

---

## 📋 산출물

```
handover/
├── README.md                          # 인수인계 진입점
├── 01_code_handover.md                # 코드 저장소 인계
├── 02_documentation_index.md          # 문서 인덱스
├── 03_credentials_handover.md         # 계정·시크릿 인계
├── 04_data_handover.md                # 데이터·DB 인계
├── 05_infrastructure.md               # 인프라·배포 정보
├── 06_known_issues.md                 # 알려진 문제·기술 부채
├── 07_contact_info.md                 # 연락처·지원 채널
└── checklists/
    ├── pre_handover.md                # 인수인계 전 학생 팀 자체 검증
    ├── handover_session.md            # 대면 인수인계 절차
    └── post_handover.md               # 인수인계 후 1~30일 점검
```

---

## 📐 인수인계 항목 분류

### 5대 영역

| 영역 | 항목 | 책임자 |
|------|------|------|
| **1. 코드** | Git 저장소, CI/CD, 의존성 | 백엔드/모바일 리드 |
| **2. 문서** | 가이드 22개, 명세서, README | 문서 담당자 |
| **3. 계정·시크릿** | API 키, DB 자격증명, FCM/APNs | 인프라 담당자 |
| **4. 데이터** | DB 스냅샷, 시드, 마이그레이션 | DBA 담당자 |
| **5. 인프라** | 클라우드 설정, 모니터링, 도메인 | 인프라 담당자 |

### 인수인계 단계

```
[D-14] 학생 팀 자체 검증 시작
  └→ 모든 항목 누락 없는지 확인
[D-7] 발주처와 대면 인수인계 회의 1차
  └→ 코드·문서 워크스루
[D-3] 2차 회의 (계정·인프라)
  └→ 시크릿 전달 (오프라인)
[D-1] 최종 검증
  └→ 발주처 측 신규 개발자가 코드 빌드·실행 가능?
[D] 공식 인수인계 완료
[D+30] 사후 지원 종료
```

---

## 🔧 영역 1: 코드 저장소 인계

### `handover/01_code_handover.md`

```markdown
# 코드 인수인계

## 저장소 위치
- **백엔드**: github.com/lemon-hc/health-god-backend
- **모바일**: github.com/lemon-hc/health-god-mobile
- **인프라(IaC)**: github.com/lemon-hc/health-god-infra

## 권한 이전
- [ ] GitHub Org 소유권 → 발주처 계정으로 이전
- [ ] 학생 팀 계정 → 외부 협력자(read-only)로 강등
- [ ] Branch protection rules 유지 (main 직접 push 금지)
- [ ] Secrets 갱신 (GITHUB_TOKEN, GCP_KEY 등)

## CI/CD 설정
| 항목 | 도구 | 위치 |
|------|------|------|
| CI | GitHub Actions | .github/workflows/ |
| 코드 품질 | mypy, flake8, dart analyze | .github/workflows/quality.yml |
| 테스트 | pytest, flutter test | .github/workflows/test.yml |
| 배포 | (학생 팀에서 미구축) | TODO Phase 5 |

## 빌드 가능성 검증

발주처 신규 개발자가 처음 빌드까지의 최소 단계:

### 백엔드
```bash
git clone https://github.com/lemon-hc/health-god-backend
cd health-god-backend
cp .env.example .env  # 시크릿 채우기 (별도 전달)
docker compose up -d
make install
make test
make run
```
→ **검증**: 신규 개발자 5명이 위 단계로 30분 내 실행 가능?

### 모바일
```bash
git clone https://github.com/lemon-hc/health-god-mobile
cd health-god-mobile
flutter pub get
dart run build_runner build --delete-conflicting-outputs
flutter run
```

## 의존성 정리
- [ ] requirements.txt / pubspec.yaml 버전 고정 (^ 제거 또는 명시)
- [ ] Outdated 패키지 0개 (Phase 5에서 점진 업그레이드 권장)
- [ ] 보안 취약점 0개 (npm audit, pip-audit 통과)

## 코드 컨벤션 (CLAUDE.md 활용)
- 백엔드: src/CLAUDE.md
- 모바일: mobile/CLAUDE.md
- 데이터: data/CLAUDE.md
→ Claude Code 사용 시 즉시 일관된 코드 작성 가능
```

---

## 🔧 영역 2: 문서 인덱스

### `handover/02_documentation_index.md`

```markdown
# 문서 인덱스

## 1단계: 기획·합의 문서
- docs/Nutrition-docs/01-product-vision-and-strategy.md
- docs/Nutrition-docs/02-personas-and-scenarios.md
- docs/Nutrition-docs/03-feature-and-output-spec.md
- docs/Nutrition-docs/04-success-metrics-and-differentiation.md

## 2단계: 협업 시스템
- docs/Nutrition-docs/05-collaboration-charter.md
- .github/ (PR/Issue 템플릿, CODEOWNERS, Branch 정책)

## 3단계: 실행 설계
- docs/Nutrition-docs/06-tech-stack.md (외부 API, 라이브러리 의사결정 근거)
- docs/Nutrition-docs/07-core-algorithm.md (BMI, BMR, KDRIs, Hall, 활동점수 v1~v4)
- docs/Nutrition-docs/08-roadmap.md (Phase 1~4 일정)

## 추가 문서
- docs/Nutrition-docs/09-data-catalog.md (데이터 출처·라이선스·갱신 주기)
- docs/Nutrition-docs/10-compliance-checklist.md (의료법·약사법·건기식법·개인정보)

## 개발 가이드 (22개)
### Phase 1 — 환경 + 기본 산출
- 00-setup-environment.md
- 01-bmi-and-activity-v1.md
- 02-activity-score-v2-v4.md
- 03-bmr-tdee-and-energy-balance.md
- 04-weight-prediction-7step.md
- 05-kdris-lookup.md

### Phase 2 — OCR + LLM + 모바일 기반
- 06-deficient-nutrient-diagnosis.md
- 07-ocr-pipeline.md
- 08-llm-supplement-parsing.md
- 09-supplement-registration-api.md
- 10-mobile-flutter-setup.md
- 11-mobile-camera-screen.md
- 12-mobile-healthkit-integration.md
- 13-mobile-dashboard.md

### Phase 3 — Hall + 5종 출력 + 식단 + 피드백
- 14-hall-dynamic-model.md
- 15-goal-based-analysis.md
- 16-meal-recognition.md
- 17-feedback-and-notifications.md
- 18-mobile-deficient-screen.md
- 19-mobile-goal-analysis-screen.md
- 20-mobile-meal-input-screen.md
- 21-mobile-feedback-ui.md

### Phase 4 — 인수인계
- 22-demo-scenarios.md
- 23-presentation-deck.md
- 24-demo-day-rehearsal.md
- 25-handover-checklist.md (이 문서)
- 26-operations-manual.md
- 27-incident-runbook.md
- 28-retrospective.md
- 29-final-deliverables-index.md

## CLAUDE.md (Tier 1, 2)
- /CLAUDE.md (루트)
- /backend/CLAUDE.md
- /mobile/CLAUDE.md
- /data/CLAUDE.md

## 진입점·빠른 시작
- README.md (프로젝트 개요)
- getting-started-with-claude-code.md (Claude Code 활용)

## 발표·시연 자료
- demo/scenarios/ (페르소나 A/B 시나리오)
- presentation/건강의신_시연발표_v1.pptx
- demo/backup_videos/ (백업 영상)

## 발주처 신규 개발자 첫 1주 추천 읽기 순서

### Day 1 (1시간)
1. README.md (전체 개요)
2. docs/Nutrition-docs/01-product-vision (왜 만들었나)
3. docs/Nutrition-docs/03-feature-and-output-spec (5종 출력)

### Day 2-3 (3시간)
4. docs/Nutrition-docs/06-tech-stack (왜 이 기술)
5. docs/Nutrition-docs/07-core-algorithm (어떻게 계산)
6. docs/Nutrition-docs/10-compliance-checklist (안전성)

### Day 4-5 (4시간)
7. CLAUDE.md (코드 작성 컨벤션)
8. 관심 트랙별 dev-guides 읽기 (백엔드 vs 모바일)

### Week 2+
9. 실제 코드 베이스 탐색
10. 작은 이슈 처리로 익숙해지기
```

---

## 🔧 영역 3: 계정·시크릿 인계

### `handover/03_credentials_handover.md`

```markdown
# 계정·시크릿 인계

## ⚠ 보안 주의사항
- 이 문서 자체에는 시크릿 값을 절대 적지 않음
- 시크릿 전달은 **오프라인** (대면 + USB) 또는 **암호화 채널** (1Password Share Link)
- 인계 후 **모든 시크릿 즉시 회전(rotate)** — 학생 팀 접근 불가능하게

## 인계 시크릿 목록

### 1. 외부 API 키와 로컬 LLM 설정
| 서비스 | 환경변수 | 인계 방법 | 비용 모델 |
|--------|---------|---------|---------|
| Ollama Local | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` | `.env.example` + 운영 문서 | 로컬/서버 운영비 |
| Google Cloud Vision | `GOOGLE_APPLICATION_CREDENTIALS` (JSON) | USB | 종량제 |
| CLOVA OCR (백업) | `CLOVA_OCR_SECRET` | 1Password | 종량제 |
| FCM | `firebase-adminsdk.json` | USB | 무료 |
| APNs | `AuthKey_XXX.p8` | USB | (Apple Dev) |

### 2. 인프라 자격증명
| 항목 | 인계 방법 |
|------|---------|
| GitHub Org 소유권 | GitHub 설정에서 직접 이전 |
| Cloud Provider (GCP/AWS) | 별도 회의에서 전달 |
| 도메인 등록 (있다면) | DNS 관리자 권한 이전 |
| Apple Developer 계정 | 발주처 계정 사용 권장 |
| Google Play Console | 발주처 계정 사용 권장 |

### 3. DB 자격증명
| 항목 | 환경변수 |
|------|---------|
| PostgreSQL | `DATABASE_URL` |
| Redis | `REDIS_URL` |

⚠ 인계 후 즉시 패스워드 변경 권장.

### 4. 모니터링·로깅 (구축된 경우)
| 항목 | 환경변수/URL |
|------|---------|
| Sentry (에러 추적) | `SENTRY_DSN` |
| Logtail / Datadog | `LOG_TOKEN` |

## 인계 절차

### Step 1: 학생 팀 측
1. 모든 시크릿 → `.env.handover.encrypted` (GPG 암호화)
2. 발주처 인계 담당자에게 **대면 + USB 전달**
3. 1Password 공유 링크로 보조 전달

### Step 2: 발주처 측
1. 시크릿 수신 확인
2. 즉시 모든 시크릿 회전 (rotate):
   - Ollama 모델·서버 접근권한 재확인
   - GCP 서비스 계정 키 재발급
   - DB 패스워드 변경
   - JWT 시크릿 키 재발급
3. 학생 팀 계정 → GitHub 권한 강등

### Step 3: 검증
- [ ] 회전된 시크릿으로 백엔드 정상 동작
- [ ] 모바일 앱에서 푸시 알림 수신
- [ ] 학생 팀 계정으로는 접근 불가
```

---

## 🔧 영역 4: 데이터·DB 인계

### `handover/04_data_handover.md`

```markdown
# 데이터·DB 인계

## 1. 데이터베이스 스냅샷

### PostgreSQL 백업
```bash
# 학생 팀 측에서
docker exec postgres pg_dump -U user lemon_hc > handover_db_backup.sql

# 발주처 측에서 복원
docker exec -i postgres psql -U user lemon_hc < handover_db_backup.sql
```

### Redis (캐시)
- 캐시 데이터는 인계 X (재생성 가능)
- 단, 키 패턴 문서화: `ocr:{hash}`, `kdris:{code}` 등

## 2. 마이그레이션 이력

### Alembic 버전 확인
```bash
alembic current
# → "abc123 (head)" — 발주처도 동일 버전이어야
```

### 마이그레이션 정상성 검증
```bash
# 발주처 환경에서
alembic upgrade head
alembic check  # 미반영 마이그레이션 0개 확인
```

## 3. 데이터 시드

### KDRIs 룩업 데이터
- 위치: `data/rda/kdris.csv`
- 라이선스: 농진청 공공데이터 (CC BY)
- 최종 갱신: 2026-XX-XX (가이드 05 참조)

### 식약처 인정 원료
- 위치: `data/nutrition_reference/mfds/functional_ingredients.csv`
- 라이선스: 식약처 공공데이터
- 갱신 주기: 분기 1회 (가이드 09-data-catalog.md 참조)

### 농진청 식품성분 DB
- 위치: `data/rda/korean_foods.csv`
- 라이선스: 농진청 공공데이터
- 현재 50종 (Phase 5에서 확장 권장)

### 건강 목적 정의
- 위치: `data/nutrition_reference/nutrient/health_goals.json`
- 7가지 목적 정의 + 식약처 인정 기능성 표시
- 갱신: 식약처 공식 표시 변경 시

### 시연 데이터 (페르소나 A/B)
- 위치: `demo/seeds/persona_*.json`
- 운영 환경에는 적재하지 말 것 (테스트 환경만)

## 4. 데이터 품질 보증

### 인계 직전 검증
- [ ] DB 스키마 docs/Nutrition-docs/09-data-catalog.md와 일치
- [ ] 모든 외래키 무결성 (orphan rows 0건)
- [ ] 마이그레이션 reversible (down 함수 동작)
- [ ] 백업 파일 복원 테스트 완료
- [ ] 가명처리 검증 (PII가 분석 테이블에 없는지)

## 5. 사용자 데이터 처리

### 학생 프로젝트 단계 사용자
- 베타 테스터 N명 (있다면)
- 인계 시 동의 갱신 필요 (개인정보 처리자 변경)
- 또는 모든 데이터 삭제 (GDPR 권장)

### 시연용 데이터
- 페르소나 A/B 가상 사용자만 운영 환경에 잔존 가능
- 실제 사용자 데이터는 인계 전 검토
```

---

## 🔧 영역 5: 인프라·배포

### `handover/05_infrastructure.md`

```markdown
# 인프라·배포 정보

## 현재 인프라 (학생 팀 단계)

### 개발 환경
- Docker Compose (로컬)
- 학생 개인 GCP 계정 (개발 테스트용)

### Production 환경
**현재 상태**: 학생 팀에서 미구축 — 인수 후 구축 필요

## 권장 인프라 (Phase 5+)

### 클라우드 선택
- **AWS**: 한국 리전 + Korea Cloud Service 협력
- **GCP**: Cloud Vision 같은 GCP 서비스 통합 시 유리
- **Naver Cloud**: 국내 데이터 보호 강점 (CLOVA, 한국 의료 규제)

→ 권장: GCP (Cloud Vision 의존도 + 데이터 영역 한국 리전)

### 필수 구성 요소
```
[CloudFront / CDN]
        │
        ▼
[Load Balancer]
        │
   ┌────┴─────┐
   ▼          ▼
[Backend]   [Backend]   ← 최소 2개 인스턴스 (HA)
   │
   ├─→ [PostgreSQL Primary] + [Read Replica]
   ├─→ [Redis Cluster]
   └─→ [External APIs]
```

### 비용 추산 (월간)
- Cloud (서버·DB·네트워크): ₩300,000 ~ 500,000
- Ollama 로컬/사내 LLM 서버: 운영 방식에 따라 별도 산정
- Cloud Vision: ₩200,000
- FCM/APNs: 무료 (한도 내)
- 도메인·SSL: ₩30,000
**합계**: 월 ₩2,030,000 ~ 2,230,000

### 모니터링 권장 도구
- **APM**: Datadog 또는 New Relic
- **로그**: Logtail 또는 Cloud Logging
- **에러**: Sentry
- **알림**: Slack 통합

## 도메인·SSL
- 도메인 (예: `health-god.lemonhc.com`) 등록 필요
- SSL: Let's Encrypt (무료) 또는 클라우드 제공

## 백업 전략
- DB 일일 백업 (자동, 30일 보존)
- 주간 풀 백업 (90일 보존)
- 월간 콜드 스토리지 (1년 보존)

## 보안 권장
- WAF (Cloud Armor 등)
- DDoS 방어
- API Rate Limiting
- 정기 보안 감사 (분기 1회)
```

---

## 🔧 영역 6: 알려진 문제·기술 부채

### `handover/06_known_issues.md`

```markdown
# 알려진 문제·기술 부채

## ⚠ 학생 팀이 알고 있으나 미해결인 항목

### Critical (인수 후 즉시 처리 권장)
1. **JWT 인증 미구현**
   - 가이드 09에 명세만, 실제 코드 미작성
   - 우선 발주처에서 백엔드 인증 모듈 추가 필요

2. **백엔드 운영 환경 미구축**
   - 학생 팀은 로컬 Docker만 사용
   - Phase 5에서 클라우드 배포 필요

3. **모바일 앱 스토어 등록 미완료**
   - iOS/Android 빌드는 검증, 등록은 발주처 계정 필요
   - 개인정보 처리방침 작성 필요

### High (1-3개월 내 처리)
4. **에러 추적·로깅 미통합**
   - Sentry, Logtail 등 통합 안 됨
   - Phase 5 초기 작업 권장

5. **부하 테스트 부족**
   - 1만 명까지만 검증
   - 100만 명 대상 부하 테스트 필요

6. **국제화 (i10n) 미지원**
   - 한국어 하드코딩
   - Flutter intl 패키지 도입 권장

### Medium (3-6개월 내)
7. **백그라운드 데이터 동기화 미구현**
   - HealthKit/Health Connect 데이터를 앱 활성화 시만 동기화
   - 백그라운드 작업 (Background Tasks) 추가 권장

8. **광범위한 일관성 검증 부족**
   - 단위·통합 테스트는 충실하나, 카오스 엔지니어링 X
   - 실 환경에서 발견할 가능성 있음

### Low (사업 우선순위에 따라)
9. **농진청 식품 DB 50종만**
   - 점진 확장 필요 (200~500종)
   - 데이터 입력 자원 필요

10. **Hall 모델 단순화 버전**
    - 단백질·탄수화물·지방 분리 추적 X
    - 글리코겐 변동 미반영
    - 단기(2~3주) 정확도는 7-step과 비슷 가능

## 기술 부채 우선순위 매트릭스

```
영향도 ↑    [JWT]              [부하 테스트]
            [운영 배포]

            [백그라운드 동기화]   [DB 확장]
            [국제화]

            [농진청 확장]        [Hall 정밀화]
영향도 ↓
            긴급도 ↑                    긴급도 ↓
```

## 해결 가이드 위치
- 각 항목 → 관련 dev-guide 참조
- Phase 5+ 로드맵에 우선순위 반영 권장
```

---

## 🔧 영역 7: 연락처·지원

### `handover/07_contact_info.md`

```markdown
# 연락처·지원 채널

## 학생 팀 연락처

| 역할 | 이름 | 이메일 | 전화 |
|------|------|------|------|
| 팀장 | XX | xx@knu.ac.kr | 010-XXXX-XXXX |
| 백엔드 리드 | XX | xx@knu.ac.kr | 010-XXXX-XXXX |
| 모바일 리드 | XX | xx@knu.ac.kr | 010-XXXX-XXXX |
| 데이터 리드 | XX | xx@knu.ac.kr | 010-XXXX-XXXX |
| 지도교수 | XX | xx@knu.ac.kr | (사무실) |

## 사후 지원 약정

### 인수인계 후 30일 (D+1 ~ D+30)
- 이메일 응답 (영업일 24시간 내)
- 긴급 문제 (시스템 다운) 4시간 내 응답 시도
- 주 1회 정기 동기화 미팅 (선택)

### 30일 이후
- 이메일 응답만 (best effort)
- 학생 팀의 후속 학업·취업 일정에 따라 가변

### 협업 종료 (D+90)
- 공식 협업 종료
- 발주처 자체 운영 체제로 전환

## 외부 의존성 연락처

### 위급 시 연락
- Ollama Docs: https://docs.ollama.com/
- Google Cloud Support: 콘솔에서 티켓
- Naver Cloud (CLOVA): 1588-XXXX
- Firebase: 콘솔 사용 가이드

### 컴플라이언스 자문
- 의료법 변호사: (별도 추천 X — 발주처 측 자문)
- 식약처 문의: 1577-1255
```

---

## ✅ Definition of Done

- [ ] `handover/` 디렉토리 7개 + 체크리스트 3개 모두 작성
- [ ] 발주처 신규 개발자 5명 → 30분 내 빌드·실행 검증
- [ ] 모든 시크릿 오프라인 전달 (USB) + 1Password 백업
- [ ] DB 백업·복원 검증
- [ ] 알려진 문제 솔직하게 문서화 (10개+)
- [ ] 사후 지원 약정서 발주처와 합의
- [ ] 학생 팀 GitHub 권한 강등 + 발주처 권한 부여
- [ ] 모든 시크릿 회전 후 동작 검증
- [ ] 인수인계 회의 의사록 작성 (3회 분량)

---

## 💡 구현 팁

### 인수인계의 황금 룰

```
✅ "발주처 개발자가 처음 합류하는 시점" 시뮬레이션
   → 그들이 막힐 수 있는 모든 지점에 답변 미리 작성

✅ 솔직하게 — 알려진 문제·미흡한 부분 모두 문서화
   → 나중에 들통나는 것보다 미리 알리는 게 신뢰

✅ 인계 후 30일 사후 지원 명시
   → 비상 문제 대응 가능한 라인 유지
```

### "체크리스트 검증" 강제

```
- [ ] (체크박스) 항목 100개 미만으로 끝나면 부실
- 발주처 측 체크리스트 통과 후에만 인계 완료 선언
```

### 인계 후 잘못 안 가도록

```
시크릿 회전 (rotate)이 가장 중요:
  학생 팀 GitHub 계정으로 접근 시도 → 실패 확인
  학생 팀 API 키로 호출 시도 → 401 확인
  → "학생 팀이 떠난 후에도 안전" 보장
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 시크릿 값을 문서에 직접 적기
- ❌ "알아서 할 수 있을 것" 가정 (절대 X)
- ❌ 알려진 문제 숨기기
- ❌ 인계 직후 전체 책임 회피 (30일 사후 지원)

---

## 🔗 관련 문서

- 이전: [`24-demo-day-rehearsal.md`](./24-demo-day-rehearsal.md)
- 다음: [`26-operations-manual.md`](./26-operations-manual.md)
