# dev-guides/26 — 운영 매뉴얼 (모니터링·백업·스케일링)

> **Phase**: 4 | **선행 작업**: [`25-handover-checklist.md`](./25-handover-checklist.md) | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

발주처가 인수인계 후 시스템을 안정적으로 운영할 수 있도록 일상 운영 절차, 모니터링 방법, 백업·복원, 스케일링 가이드를 정리한다. 학생 팀의 PoC를 운영 환경으로 발전시키기 위한 매뉴얼.

---

## 📋 산출물

```
operations/
├── README.md                       # 운영 진입점
├── daily/
│   ├── morning_checklist.md        # 매일 오전 체크 항목
│   └── monitoring_review.md        # 일일 모니터링 리뷰
├── weekly/
│   ├── performance_review.md       # 주간 성능 리뷰
│   └── feedback_analysis.md        # 사용자 피드백 분석
├── monthly/
│   ├── cost_review.md              # 비용 리뷰
│   └── data_quality_audit.md       # 데이터 품질 감사
└── procedures/
    ├── deploy_procedure.md          # 배포 절차
    ├── backup_procedure.md          # 백업 절차
    ├── restore_procedure.md         # 복원 절차
    ├── scaling_procedure.md         # 스케일링 절차
    └── data_update_procedure.md     # KDRIs·식약처 데이터 갱신
```

---

## 📐 운영 주기 정리

```
일일 (오전 9시)
  ├→ 시스템 헬스체크
  ├→ 로그 에러 빈도 확인
  ├→ API 사용량·비용 모니터링
  └→ 사용자 피드백 신규 항목

주간 (월요일 오전)
  ├→ 응답시간 SLA 검토
  ├→ 사용자 증가 추이
  ├→ 피드백 평균 평점
  └→ 알려진 이슈 우선순위 갱신

월간 (1일)
  ├→ 비용 대비 사용자 수
  ├→ 데이터 품질 감사
  ├→ 보안 취약점 스캔
  └→ KDRIs·식약처 데이터 갱신 검토

분기 (3개월)
  ├→ 부하 테스트 재실시
  ├→ 외부 API 의존성 검토
  └→ 인프라 비용 최적화
```

---

## 🔧 일일 운영 체크리스트

### `operations/daily/morning_checklist.md`

```markdown
# 일일 오전 체크 (5~10분)

## 1. 시스템 헬스체크
```bash
# 백엔드 헬스
curl https://api.health-god.lemonhc.com/health
# → {"status": "ok", "uptime_sec": ...} 정상

# DB 연결
docker exec backend python -c "import asyncio; \
  from src.db.session import async_session_maker; \
  asyncio.run(async_session_maker().__aenter__())"
# → 에러 없음 = 정상

# Redis 연결
redis-cli -u $REDIS_URL ping
# → PONG
```

## 2. 에러 로그 확인 (Sentry / Logtail)
- [ ] 지난 24시간 신규 에러 알림 확인
- [ ] 빈도가 급증한 에러 (>10/h) 우선순위
- [ ] Critical 알림은 슬랙 즉시 알림 통합

## 3. 외부 API·로컬 LLM 상태
- [ ] Ollama 서버 상태 확인 (`ollama list`, `/api/chat` smoke test)
- [ ] 기본 모델(`qwen3.5` 또는 `gemma4`) 로딩·응답 시간 확인
- [ ] Google Cloud Vision 콘솔 → 어제 사용량
- [ ] 한도 80% 초과 시 알람 발송 사전 설정

## 4. 신규 사용자 피드백
- [ ] 백엔드 DB 쿼리:
  ```sql
  SELECT type, AVG(rating), COUNT(*)
  FROM feedbacks
  WHERE created_at > NOW() - INTERVAL '24 hours'
  GROUP BY type;
  ```
- [ ] 평균 평점 < 3.5인 종류 우선 검토

## 5. 응답 시간 SLA
- [ ] 영양제 등록 API: P95 < 6초
- [ ] 캐시 hit ratio: > 70%
- [ ] DB 응답 시간: P95 < 100ms

## 비상 알림 채널
- Slack `#prod-alerts`
- 카카오톡 운영자 단체방
- 긴급: 운영 책임자 휴대폰
```

---

## 🔧 모니터링·관측 가능성

### 핵심 지표 (Golden Signals)

| 지표 | 목표 | 알람 임계 | 도구 |
|------|------|---------|------|
| **응답 시간 (Latency)** | P50 < 2s, P95 < 6s | P95 > 8s 5분 지속 | Datadog APM |
| **에러율 (Errors)** | < 0.5% | > 2% 5분 지속 | Sentry |
| **트래픽 (Traffic)** | 정상 범위 ±50% | 급격한 변화 | Datadog |
| **포화도 (Saturation)** | CPU < 70%, Mem < 80% | > 90% 10분 | Cloud 모니터링 |

### 비즈니스 지표

```sql
-- 일일 활성 사용자 (DAU)
SELECT COUNT(DISTINCT user_id) AS dau
FROM (
  SELECT user_id FROM supplements WHERE registered_at > NOW() - INTERVAL '24 hours'
  UNION
  SELECT user_id FROM meals WHERE created_at > NOW() - INTERVAL '24 hours'
  UNION
  SELECT user_id FROM feedbacks WHERE created_at > NOW() - INTERVAL '24 hours'
) active;

-- 5종 출력 사용 빈도
SELECT 'supplement' AS type, COUNT(*) FROM supplements WHERE registered_at > NOW() - INTERVAL '7 days'
UNION ALL
SELECT 'meal', COUNT(*) FROM meals WHERE created_at > NOW() - INTERVAL '7 days'
UNION ALL
SELECT 'goal_analysis', COUNT(*) FROM goal_analysis_logs WHERE created_at > NOW() - INTERVAL '7 days';

-- OCR 백업 폴백 비율 (높으면 주력 API 문제)
SELECT
  ocr_engine,
  COUNT(*) AS count,
  COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () AS pct
FROM supplements
WHERE registered_at > NOW() - INTERVAL '7 days'
GROUP BY ocr_engine;
```

---

## 🔧 배포 절차

### `operations/procedures/deploy_procedure.md`

```markdown
# 배포 절차

## 사전 준비
- [ ] 변경사항 PR 리뷰 통과 (최소 2명)
- [ ] CI 모든 테스트 통과
- [ ] 마이그레이션 reversible 검증
- [ ] CHANGELOG.md 업데이트
- [ ] 배포 시간 사용자 영향 적은 시간대 (예: 새벽 3~5시)

## 배포 전 검증
```bash
# 1. 로컬에서 마이그레이션 dry-run
alembic upgrade head --sql > migration.sql
# 검토 후 이상 없으면 진행

# 2. 스테이징 환경 배포 + 검증
make deploy-staging
make test-staging  # E2E 테스트

# 3. 사용자 피드백 마지막 24시간 검토
# (긴급 이슈 없는지 확인)
```

## 배포 실행
```bash
# 백엔드
git checkout main
git pull
make build
make deploy-prod

# 마이그레이션 (필요 시)
docker exec backend-prod alembic upgrade head

# 헬스체크
curl https://api.health-god.lemonhc.com/health
```

## 모바일 배포 (스토어)
- iOS: TestFlight → App Store
- Android: Internal testing → Production

배포 주기: 1~2주 1회 권장 (긴급 핫픽스 외)

## 배포 후 모니터링 (배포 후 1시간)
- [ ] 에러율 0.5% 이내 유지
- [ ] 응답 시간 SLA 준수
- [ ] 사용자 피드백 신규 항목 모니터링

## 롤백 절차
```bash
# 직전 버전 태그 확인
git log --tags --oneline | head -5

# 롤백
git checkout v1.2.3  # 직전 태그
make deploy-prod

# 마이그레이션 다운 (필요 시)
docker exec backend-prod alembic downgrade -1
```
```

---

## 🔧 백업·복원 절차

### `operations/procedures/backup_procedure.md`

```markdown
# 백업 절차

## 백업 빈도
| 대상 | 빈도 | 보존 |
|------|------|------|
| PostgreSQL | 일일 자동 | 30일 |
|             | 주간 | 90일 |
|             | 월간 | 1년 |
| 파일 (이미지·설정) | 일일 | 30일 |
| Redis | 백업 X (재생성 가능) | - |

## 자동 백업 스크립트

### `scripts/backup_daily.sh`
```bash
#!/bin/bash
set -euo pipefail

DATE=$(date +%Y%m%d_%H%M)
BACKUP_DIR="/backups/postgres"
mkdir -p "$BACKUP_DIR"

# DB 덤프
docker exec postgres-prod pg_dump -U lemon -F c -f /tmp/backup.dump lemon_hc

# 컨테이너 → 호스트 복사
docker cp postgres-prod:/tmp/backup.dump "$BACKUP_DIR/db_${DATE}.dump"

# 클라우드 스토리지 업로드 (S3 / GCS)
gsutil cp "$BACKUP_DIR/db_${DATE}.dump" gs://lemon-hc-backups/postgres/

# 30일 이전 로컬 백업 삭제
find "$BACKUP_DIR" -mtime +30 -delete

echo "✓ Backup completed: $DATE"
```

### Cron 등록
```cron
0 3 * * * /opt/scripts/backup_daily.sh > /var/log/backup.log 2>&1
0 3 * * 0 /opt/scripts/backup_weekly.sh
0 3 1 * * /opt/scripts/backup_monthly.sh
```

## 백업 무결성 검증 (월 1회)

```bash
# 임시 컨테이너에 복원 시도
docker run --rm -d --name pg_test postgres:16
docker cp /backups/db_latest.dump pg_test:/tmp/backup.dump
docker exec pg_test pg_restore -U postgres -d test /tmp/backup.dump

# 복원된 데이터 검증
docker exec pg_test psql -U postgres -d test -c "SELECT COUNT(*) FROM users"
```
```

### `operations/procedures/restore_procedure.md`

```markdown
# 복원 절차 (재해 시)

## 복원 시나리오
1. **부분 데이터 손실**: 특정 테이블만 복원
2. **전체 손실**: DB 전체 복원
3. **신규 환경 구축**: 백업으로 새 환경 셋업

## 시나리오 1: 부분 복원
```bash
# 백업에서 특정 테이블만 추출
pg_restore -t supplements -f supplements_only.sql backup.dump
psql -U lemon -d lemon_hc -f supplements_only.sql
```

## 시나리오 2: 전체 복원
```bash
# 1. 운영 중지 (다운타임 있음)
docker stop backend-prod

# 2. 기존 DB 백업 (안전망)
pg_dump -U lemon lemon_hc > pre_restore_backup.sql

# 3. DB 초기화 + 복원
docker exec postgres-prod dropdb -U lemon lemon_hc
docker exec postgres-prod createdb -U lemon lemon_hc
docker exec -i postgres-prod pg_restore -U lemon -d lemon_hc < backup.dump

# 4. 마이그레이션 정합성 확인
alembic current
alembic upgrade head

# 5. 운영 재개
docker start backend-prod

# 6. 검증
curl https://api.health-god.lemonhc.com/health
```

## RTO·RPO 목표
- **RTO (복구 시간)**: 4시간 이내
- **RPO (데이터 손실)**: 24시간 이내 (일일 백업 기준)

→ Phase 5+에서 streaming replication 도입 시 RPO < 1분 가능
```

---

## 🔧 스케일링 절차

### `operations/procedures/scaling_procedure.md`

```markdown
# 스케일링 절차

## 트리거 조건
| 지표 | 임계 | 액션 |
|------|------|------|
| CPU > 70% | 15분 지속 | 인스턴스 1개 추가 |
| 응답 시간 P95 > 8s | 10분 지속 | DB 쿼리 분석 + 인스턴스 추가 |
| DB 연결 > 80% | 5분 지속 | DB 풀 사이즈 증가 |

## 수평 확장 (Backend 인스턴스 추가)
```bash
# Docker Swarm / Kubernetes 환경
kubectl scale deployment backend --replicas=5

# 또는 docker compose
docker compose up -d --scale backend=5
```

## DB 확장
- **Read Heavy**: Read Replica 1~3개 추가
- **Write Heavy**: 샤딩 검토 (Phase 5+)

## API 비용 폭증 시
- **Ollama 로컬 LLM**: 동시 요청 제한, 모델 크기 조정, 큐 기반 처리
- **Cloud Vision**: 이미지 전처리로 호출 횟수 ↓
- **CLOVA 폴백**: 주력 API 신뢰도 확인 후 임계 조정

## 사용자 100만 명 대비 (Phase 5+)
1. CDN 도입 (CloudFront / Cloud CDN)
2. DB 샤딩 (user_id 기반)
3. 캐시 분리 (Redis Cluster)
4. 큐 도입 (RabbitMQ / Kafka, 비동기 처리)
5. 마이크로서비스 분리 (영양·체중·운동·식단)
```

---

## 🔧 데이터 갱신 절차

### `operations/procedures/data_update_procedure.md`

```markdown
# KDRIs·식약처 데이터 갱신

## 갱신 주기
- **KDRIs**: 5년마다 (한국영양학회 발표)
- **식약처 인정 기능성**: 분기 1회 (식약처 공시 변경 시)
- **농진청 식품성분 DB**: 분기 1회

## KDRIs 갱신 절차
1. 한국영양학회 신규 발표본 다운로드
2. `data/rda/kdris.csv` 비교 (diff 도구)
3. 변경 항목 분석:
   - 권장량 변경 → 기존 사용자 진단 결과 영향 평가
   - 신규 영양소 → 룩업 함수에 추가
4. 검증:
   ```bash
   pytest tests/integration/nutrition/test_kdris_lookup.py
   ```
5. 배포
6. 사용자 안내 (옵션):
   - "최신 KDRIs 기준 적용" 안내 메시지

## 식약처 인정 기능성 갱신
```bash
# 식약처 공식 사이트에서 최신 목록 다운로드
# https://www.foodsafetykorea.go.kr/portal/healthyfoodlife

# 1. 신규 인정 원료 추가
vim data/mfds/functional_ingredients.csv
vim data/reference/health_goals.json

# 2. 컴플라이언스 자동 검증
pytest tests/unit/nutrition/test_goal_definitions.py

# 3. 의료법 표현 가이드 검증
pytest tests/unit/nutrition/test_compliance.py
```

## 농진청 식품 DB 갱신
- 신규 음식 50종 추가 시 Ollama 모델별 LLM 인식 정확도 재테스트
- E2E 테스트로 기존 사용자 데이터 영향 없음 확인
```

---

## ✅ Definition of Done

- [ ] `operations/` 디렉토리 + 일일·주간·월간 체크리스트
- [ ] 배포 절차 문서 + 자동화 스크립트
- [ ] 백업·복원 절차 + 검증 스크립트
- [ ] 스케일링 절차 + 트리거 조건 명시
- [ ] 데이터 갱신 절차 (KDRIs, 식약처, 농진청)
- [ ] 모니터링 대시보드 설정 가이드 (Datadog/Sentry)
- [ ] RTO/RPO 목표 명시
- [ ] 비용 모니터링 알람 설정
- [ ] 모든 절차 발주처 운영 담당자와 합의

---

## 💡 구현 팁

### 자동화 우선순위

```
1. 일일 백업 — 수동 절대 X
2. 헬스체크 알림 — 다운타임 조기 발견
3. 비용 알림 — 폭증 방지
4. 에러 알림 — 사용자 영향 최소화
```

### 사람의 개입이 필요한 부분

```
✅ 마이그레이션 검토 (자동 적용 위험)
✅ 데이터 갱신 (KDRIs 변경 영향 평가)
✅ 보안 감사
✅ 비용 최적화 의사결정
```

### 운영 책임자 지정

- 시스템 다운 시 즉시 응답 가능한 1명
- 백업 운영자 1명 (휴가·병가 대비)
- 책임 매트릭스 (RACI) 명확

---

## 🚫 이 작업에서 하지 말 것

- ❌ 운영 절차 없이 인계 (시스템 방치)
- ❌ 백업 검증 안 함 (복원 시 실패 가능)
- ❌ 단일 운영자 (Bus Factor = 1 위험)
- ❌ 모니터링 알람 무시 (피로도 발생 → 진짜 알람 놓침)

---

## 🔗 관련 문서

- 이전: [`25-handover-checklist.md`](./25-handover-checklist.md)
- 다음: [`27-incident-runbook.md`](./27-incident-runbook.md)
