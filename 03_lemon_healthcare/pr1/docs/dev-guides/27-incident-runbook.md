# dev-guides/27 — 장애 대응 런북

> **Phase**: 4 | **선행 작업**: [`26-operations-manual.md`](./26-operations-manual.md) | **예상 소요**: 3~4시간

---

## 🎯 작업 목표

운영 중 발생 가능한 장애 유형별 대응 절차를 표준화하여, 누구든 같은 절차로 빠르게 복구할 수 있도록 한다. P0~P3 우선순위, 에스컬레이션, 사후 분석(Postmortem)까지 포함.

---

## 📋 산출물

```
incidents/
├── README.md                       # 런북 진입점
├── severity_levels.md              # P0~P3 정의
├── escalation_policy.md            # 에스컬레이션 정책
├── runbooks/
│   ├── R001_backend_down.md           # 백엔드 다운
│   ├── R002_db_connection_failure.md  # DB 연결 실패
│   ├── R003_external_api_outage.md    # 외부 API 장애
│   ├── R004_high_error_rate.md        # 에러율 급증
│   ├── R005_slow_response.md          # 응답 시간 지연
│   ├── R006_disk_full.md              # 디스크 가득
│   ├── R007_security_breach.md        # 보안 사고
│   └── R008_data_loss.md              # 데이터 유실
├── templates/
│   ├── incident_report.md          # 장애 보고서 템플릿
│   └── postmortem.md               # 사후 분석 템플릿
└── history/
    └── (실제 장애 발생 시 기록)
```

---

## 📐 장애 우선순위 (P0~P3)

### 정의

| Level | 정의 | 예시 | 응답 시간 | 알림 |
|-------|------|-----|---------|------|
| **P0 (Critical)** | 전체 서비스 중단, 데이터 손실 위험 | 백엔드 완전 다운, DB 다운, 보안 침해 | 15분 내 | 운영자 + CTO + 슬랙 |
| **P1 (High)** | 핵심 기능 장애, 다수 사용자 영향 | 영양제 등록 실패율 50%+ | 1시간 내 | 운영자 + 슬랙 |
| **P2 (Medium)** | 부분 기능 장애, 일부 사용자 영향 | 푸시 알림 미발송, 식단 인식 정확도 저하 | 4시간 내 | 운영자 |
| **P3 (Low)** | 미미한 영향, 단일 사용자 | 특정 영양제 라벨 인식 실패 | 1일 내 | 다음 영업일 |

### 에스컬레이션 흐름

```
[알람 발생]
   ↓
[운영 책임자 접수] (15분 내)
   ↓
[초동 대응] — Severity 판단
   │
   ├─ P0/P1 → 슬랙 #incidents 채널 + 운영팀 + CTO 알림
   ├─ P2     → 슬랙 #incidents
   └─ P3     → 다음 영업일 처리
   │
   ↓
[복구 작업] — 런북 따라 진행
   │
   ↓
[복구 완료] — 헬스체크 정상 확인
   │
   ↓
[사후 보고] — P0/P1은 24시간 내 Postmortem
```

---

## 🚨 런북: 백엔드 다운 (R001)

### `incidents/runbooks/R001_backend_down.md`

```markdown
# R001: 백엔드 서버 다운

## 트리거
- Health check 5분 이상 실패
- 모든 API 호출 503/504
- 모니터링 대시보드 "Backend Down" 알람

## Severity: P0

## 즉시 대응 (5분)

### Step 1: 상태 파악
```bash
# 컨테이너 상태
docker ps --filter "name=backend"

# 로그 마지막 100줄
docker logs --tail 100 backend-prod

# 시스템 리소스
docker stats --no-stream
```

### Step 2: 빠른 복구 시도
```bash
# 컨테이너 재시작
docker compose restart backend

# 헬스체크 (10초 후)
sleep 10
curl https://api.health-god.lemonhc.com/health
```

### Step 3: 재시작 실패 시
```bash
# 컨테이너 강제 재생성
docker compose down backend
docker compose up -d backend

# 다시 헬스체크
curl https://api.health-god.lemonhc.com/health
```

## 30분 내 정밀 진단

### 원인별 대응

#### 원인 1: OOM Killed
```bash
# 메모리 부족으로 강제 종료된 경우
dmesg | grep -i "killed process"

# 대응:
# 1. 메모리 사용량 모니터링 강화
# 2. 인스턴스 메모리 증설 (수직 확장)
# 3. 메모리 누수 의심 시 코드 리뷰
```

#### 원인 2: DB 연결 풀 소진
```bash
# 활성 연결 확인
docker exec postgres-prod psql -U lemon -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'lemon_hc'"

# 대응:
# 1. 연결 풀 사이즈 일시 증가
# 2. Idle 연결 정리
# 3. 장기 실행 쿼리 종료
```

#### 원인 3: 디스크 가득
```bash
df -h
# 90% 이상이면 R006 런북 참조
```

#### 원인 4: 코드 배포 직후
```bash
# 직전 배포 시각 확인
git log --oneline -1

# 즉시 롤백 (가이드 26 배포 절차)
git checkout HEAD~1
make deploy-prod
```

## 사용자 커뮤니케이션
- 슬랙 #user-support 알림
- 카카오 채널 공지 (다운타임 30분 이상 지속 시)
- 복구 후 "정상화" 공지

## 사후 분석 (24시간 내)
- 장애 보고서 작성 (templates/incident_report.md)
- Postmortem 미팅 (R001은 P0이므로 필수)
- 재발 방지 액션 아이템
```

---

## 🚨 런북: 외부 API 장애 (R003)

### `incidents/runbooks/R003_external_api_outage.md`

```markdown
# R003: 외부 API 장애 (Cloud Vision / Claude / FCM)

## Severity
- 주력 API 다운: P1
- 백업 API도 다운: P0

## 트리거
- 영양제 등록 실패율 급증
- LLM 응답 timeout 빈도 ↑
- Cloud Vision 5xx 응답 다수

## 즉시 대응 (5분)

### Step 1: 어떤 API가 문제인지 파악
```bash
# 로그에서 어떤 API가 실패하는지
docker logs --tail 200 backend-prod 2>&1 | grep -E "OCR|LLM|FCM" | tail -20

# 외부 상태 페이지 확인:
# - Anthropic: https://status.anthropic.com/
# - Google Cloud: https://status.cloud.google.com/
# - Naver Cloud: https://status.ncloud.com/
```

### Step 2: Adapter 폴백 동작 확인
```python
# OCR 백업이 작동하는지
from src.ocr.pipeline import OCRPipeline
# 로그에 "Fallback OCR called" 확인
```

### Step 3: 폴백마저 실패하면
```bash
# 사용자에게 친절한 에러 메시지 표시
# 모바일 앱: "잠시 후 다시 시도해주세요"

# 슬랙 #incidents 알림:
# "외부 API 장애 감지. 영양제 등록·식단 분석 일시 불가능. 30분 후 재시도 안내."
```

## 1시간 내 대응

### 외부 장애 → 대기
- 외부 서비스 복구 대기
- 사용자에게 "임시 장애" 안내
- 큐잉 시스템 도입 검토 (Phase 5)

### 자체 문제 → 코드 수정
- API 키 만료 → 갱신
- Rate Limit 초과 → 동시 요청 제한
- 잘못된 요청 형식 → 코드 패치

## 외부 API별 상태 페이지

| API | 상태 페이지 | 평균 다운타임 |
|------|------------|---------|
| Anthropic | status.anthropic.com | < 15분/월 |
| Google Cloud Vision | status.cloud.google.com | < 5분/월 |
| Naver CLOVA | status.ncloud.com | 가변 |
| Firebase FCM | status.firebase.google.com | < 10분/월 |
```

---

## 🚨 런북: 보안 사고 (R007)

### `incidents/runbooks/R007_security_breach.md`

```markdown
# R007: 보안 사고 (의심·확정)

## ⚠ Severity: P0 (즉시 대응)

## 트리거
- 비정상적 API 호출 패턴
- 의심스러운 DB 쿼리
- 시크릿 유출 의심
- WAF 알람

## 즉시 대응 (15분 내, 절대 우선순위)

### Step 1: 격리
```bash
# 1. 의심스러운 IP 차단 (Cloud Armor / WAF)
# 2. 영향받은 서비스 일시 중단 (필요 시)
# 3. 모든 외부 노출 점검

# 모든 진행 중 세션 종료
docker exec redis-prod redis-cli FLUSHDB  # 캐시·세션 삭제
```

### Step 2: 시크릿 즉시 회전
```bash
# ALL secrets immediately rotate
# - Anthropic API key (콘솔에서 재발급)
# - Google Cloud key (서비스 계정 키 재발급)
# - DB password (강력한 새 패스워드)
# - JWT signing key (새로 생성)
# - FCM/APNs keys (재발급)

# 새 시크릿으로 백엔드 재시작
docker compose restart backend
```

### Step 3: 영향 범위 파악
```sql
-- 의심 시간대 활동 분석
SELECT user_id, COUNT(*), MAX(created_at)
FROM access_logs
WHERE created_at BETWEEN 'YYYY-MM-DD HH:MM' AND 'YYYY-MM-DD HH:MM'
GROUP BY user_id
ORDER BY COUNT(*) DESC;

-- 비정상 데이터 변경 감지
SELECT * FROM audit_logs
WHERE action_type IN ('DELETE', 'UPDATE')
AND created_at > NOW() - INTERVAL '24 hours';
```

## 24시간 내 보고

### 법적 의무
- **개인정보 유출 시**:
  - 정보주체에게 5일 이내 통지 (개인정보보호법 §34)
  - 개인정보보호위원회 신고 (1만 명 이상이면 필수)
- **의료 데이터 포함 시**:
  - 보건복지부 신고 (의료법 §23 의 5)

### 외부 자문
- 보안 전문 업체 연락 (KISA, KrCERT)
- 법무팀 즉시 통보
- PR 대응 (필요 시)

## 사후 분석 (D+7)
- 침투 경로 완전 파악
- 모든 자산 보안 강화
- 침투 테스트 (Penetration Test) 의뢰
- 직원 보안 교육 강화

## 예방 수칙 (평소)
- [ ] 시크릿 분기별 rotate
- [ ] WAF 활성화
- [ ] DDoS 방어
- [ ] 보안 감사 분기 1회
- [ ] 의심 활동 자동 알람
```

---

## 🚨 런북: 데이터 유실 (R008)

### `incidents/runbooks/R008_data_loss.md`

```markdown
# R008: 데이터 유실

## Severity: P0

## 시나리오
1. **부분 유실**: 특정 테이블/사용자 데이터 사라짐
2. **전체 유실**: DB 자체 손상
3. **백업 자체 손상**: 백업 복원 실패

## 즉시 대응

### Step 1: 추가 손실 방지
```bash
# DB 쓰기 차단 (필요 시)
# 백엔드를 read-only 모드로 전환

# 서비스 중단이 필요하면
docker stop backend-prod
```

### Step 2: 손실 범위 파악
```sql
-- 직전 백업 시각 확인
ls -la /backups/postgres/ | head

-- 영향 사용자 수 추정
SELECT COUNT(DISTINCT user_id) FROM (
  -- 손실된 데이터 파악 쿼리
) AS affected_users;
```

### Step 3: 복원 시도
```bash
# 가이드 26의 복원 절차 따름
# 가장 최근 무결성 확인된 백업 사용
```

## 사용자 영향 보고
- 영향 사용자에게 24시간 내 이메일 통지
- 손실된 데이터 종류 명시
- 보상 정책 (해당 시)

## 재발 방지
1. 백업 빈도 증가 (일일 → 시간별)
2. 멀티 리전 백업
3. PITR (Point-in-Time Recovery) 도입
4. 정기 복원 검증 강화
```

---

## 📋 장애 보고서 템플릿

### `incidents/templates/incident_report.md`

```markdown
# 장애 보고서

## 메타데이터
- **장애 ID**: INC-2026-XX-XXX
- **발생 시각**: YYYY-MM-DD HH:MM (KST)
- **인지 시각**: YYYY-MM-DD HH:MM
- **복구 시각**: YYYY-MM-DD HH:MM
- **Severity**: P0 / P1 / P2 / P3
- **담당자**: XX
- **참여자**: XX, XX

## 영향 범위
- **사용자 수**: XX명 / 전체의 X%
- **영향 기능**: 영양제 등록 / 식단 분석 / 푸시 알림 / ...
- **데이터 손실**: 없음 / X 건

## 타임라인
| 시각 | 이벤트 |
|------|------|
| HH:MM | 알람 발생 |
| HH:MM | 운영 책임자 인지 |
| HH:MM | 초동 대응 시작 |
| HH:MM | 원인 파악 |
| HH:MM | 복구 시도 |
| HH:MM | 정상화 확인 |

## 원인
- **직접 원인**: ...
- **근본 원인**: ...

## 대응 액션
- [x] 즉시 조치: ...
- [x] 단기 패치: ...

## 재발 방지 액션
- [ ] 액션 1 (담당: XX, 기한: YYYY-MM-DD)
- [ ] 액션 2

## 학습 사항
- 잘된 점: ...
- 개선할 점: ...
```

---

## 📋 Postmortem 템플릿 (P0/P1)

### `incidents/templates/postmortem.md`

```markdown
# Postmortem — INC-XXXX

> Blameless: 사람을 비난하지 않고 시스템·프로세스 개선에 집중

## 요약 (2-3 문장)
"YYYY-MM-DD HH:MM 부터 X분 동안 백엔드가 다운되어 N명의 사용자가 영양제 등록 실패를 경험했습니다.
원인은 DB 연결 풀 소진이었고, 풀 사이즈 증가와 모니터링 강화로 재발 방지합니다."

## 타임라인
... (상세)

## 5 Whys (근본 원인)
1. 왜 백엔드가 다운됐나? → DB 연결 부족
2. 왜 DB 연결 부족이었나? → 동시 사용자 급증
3. 왜 풀 사이즈가 부족했나? → 초기 설정값이 학생 프로젝트 단계 그대로
4. 왜 사전 인지 못했나? → 부하 테스트가 1만 명까지만
5. 왜 알람이 늦었나? → DB 연결 모니터링 임계 미설정

## 근본 원인
- 학생 프로젝트의 PoC 설정이 운영에 그대로 사용됨
- 부하 테스트 부족
- 모니터링 사각지대

## 액션 아이템
| # | 액션 | 담당 | 기한 | 상태 |
|---|------|------|------|------|
| 1 | DB 풀 사이즈 50 → 200 | 인프라팀 | D+1 | 완료 |
| 2 | 연결 풀 모니터링 알람 | 운영팀 | D+3 | 진행 |
| 3 | 100만 부하 테스트 | QA | D+30 | 계획 |

## 학습 (블레임리스)
- ✅ 빠른 인지 (5분 내 알람)
- ✅ 런북 따라 차분한 대응
- ❌ 사전 부하 검증 부족
- ❌ 모니터링 임계 미설정
```

---

## ✅ Definition of Done

- [ ] Severity 정의 (P0~P3) + 응답 시간 SLA
- [ ] 에스컬레이션 정책
- [ ] 런북 8개 (R001~R008) 작성
- [ ] 장애 보고서 + Postmortem 템플릿
- [ ] 슬랙 알림 채널 설정 (#incidents, #user-support)
- [ ] 운영팀 연락망 (Phone tree)
- [ ] 모의 장애 대응 훈련 (Game Day) 계획
- [ ] 24/7 on-call 담당자 (운영자 1명, 백업 1명)
- [ ] 인계 후 발주처 측 운영자와 런북 워크쓰루 완료

---

## 💡 구현 팁

### 블레임리스 문화

```
❌ "XX이 잘못해서 다운됐다"
✅ "시스템·프로세스가 이런 실수를 가능하게 했다"

목표: 같은 실수가 반복되지 않게 하는 것
사람 비난 → 모두가 실수 숨기게 됨 → 시스템 개선 X
```

### 런북은 살아있는 문서

```
- 매번 장애 발생 후 런북 업데이트
- 신규 장애 유형 → 새 런북 추가
- 분기별 모든 런북 재검토
```

### 모의 장애 훈련 (Game Day)

```
분기 1회:
  - 의도적으로 환경에 문제 발생
  - 운영팀이 런북으로 복구
  - 시간 측정 + 개선점 도출
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 런북 없이 운영 인계
- ❌ 사람 비난 (Postmortem은 블레임리스)
- ❌ 장애 숨기기 (학습 기회 상실)
- ❌ 알람 피로 (너무 많은 알람 → 무시)

---

## 🔗 관련 문서

- 이전: [`26-operations-manual.md`](./26-operations-manual.md)
- 다음: [`28-retrospective.md`](./28-retrospective.md)
