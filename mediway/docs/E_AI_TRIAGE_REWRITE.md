# Scenario E — `triageSymptoms` 재작성 + AI Triage Widget 설계

> 작성일: 2026-04-26 (B-3.10 + F1 본 배포 직후)
> 전제: B-3.10 hospital slug routing + F1 wait queue UI 통합 완료, prod parity LIVE 도달
> 선행 컨텍스트: [LOCAL_SYNC_GAPS §1.1](./LOCAL_SYNC_GAPS.md), [F1 §10 남은 작업](./F1_WAIT_QUEUE_UI_INTEGRATION.md)
> 목표: prod e2e (`public/e2e-wait-queue.html`) 시나리오 E "AI 진료과 추천" 을 local source 가 만족시키는 함수 + UI 재작성
> 범위: 본 문서는 **설계 + commit 단위 계획**. 실제 구현은 사용자 승인 후 step-by-step.

---

## 0. 목적

LOCAL_SYNC_GAPS §1.1 에 기록된 사고 — `triageSymptoms` 함수 가 실수로 삭제됨 — 의 source-level 복구.
prod 번들이 호출하는 callable 인터페이스를 spec 그대로 재현하고, local 이 보유한 chatbot 인프라
(rateLimit / safety / Gemini provider / audit) 를 재사용.

| e2e §E 기대 | 본 sprint 도달 |
|------------|---------------|
| `features.aiTriage=true` 전제 | ✅ (HospitalShell + useFeature 가 이미 가드) |
| 환자 홈 "AI 진료과 추천" 위젯 노출 | ✅ TriageWidget |
| 증상 입력 → 진료과 3개 + 신뢰도 + "진단 아님" disclaimer | ✅ Gemini structured output |
| 5초 이내 응답 | ✅ Gemini 2.5 flash (chatbot 과 동일 모델) |
| 시간당 10회 초과 → `resource-exhausted` | ✅ epoch-hour bucket rate limit |

---

## 1. 현 상태 분석

### 함수 측
- **삭제된 원본**: `triageSymptoms` (asia-northeast3, on-call). source 없음.
- **재사용 가능한 인프라**:
  - `functions/src/chatbot/providers/gemini.ts` — Gemini API 래퍼 (chatbot 이 사용 중)
  - `functions/src/chatbot/safety.ts` — `checkEmergency`, `checkPiiRequest`, `sanitizeUserText`, `applyDisclaimer`, `STANDARD_DISCLAIMER`
  - `functions/src/chatbot/intent.ts` — emergency intent 감지
  - `functions/src/util/auditLog.ts` — `appendAuditLog` (T1-1b dual-write)
- **공통 secret**: `GEMINI_API_KEY` 가 functions/.env 에 이미 설정됨 (chatbot 운영 중)

### RTDB rules (이미 정의됨, 추가 작업 없음)
```jsonc
"triage_usage": {
  ".read": "auth != null && role === 'platformAdmin'",
  "$uid": {
    ".read": "auth.uid === $uid || role === 'platformAdmin'",
    ".write": "auth.uid === $uid"
  }
},
"triage_audit": {
  ".read": "auth != null && role === 'platformAdmin'",
  "$id": {
    ".write": "auth != null && !data.exists() && actorUid === auth.uid"
  }
}
```
→ Admin SDK (Cloud Function) 는 rules 우회. 클라이언트 측 직접 write 는 불필요.

### 프런트 측
- **부재**: `src/services/triage.ts`, `src/types/triage.ts`, `TriageWidget`
- **HomeTab**: 현재 WaitQueueWidget + ChatbotWidget 만. `features.aiTriage` 분기는 미존재.
- **참고 패턴**: `src/services/chatbot.ts` (callable wrapper + error normalize) + `ChatbotWidget` (입력→로딩→결과→에러 라이프사이클).

---

## 2. 인터페이스 명세

### Callable Request (Zod)
```ts
{
  hospitalId: string (1..64),
  symptomText: string (10..500),  // 너무 짧으면 의미 없는 추천 방지
}
```

### Callable Response
```ts
interface TriageResult {
  recommendations: Array<{
    /** 부서 canonical key — 한국어 (예: '내과', '소아청소년과') */
    department: string;
    /** 0..1 신뢰도. 합이 1 이 아닐 수 있음 (Top-3 후보) */
    confidence: number;
    /** 1-2 문장 추천 근거 */
    reason: string;
  }>;
  disclaimer: string;     // STANDARD_DISCLAIMER
  model: string;          // 'gemini-2.5-flash' 등
  tokensIn: number;
  tokensOut: number;
  rateLimit: { remainingHour: number };
}
```

### 에러 (HttpsError code → 클라이언트 normalize)
| 서버 code | 클라이언트 매핑 (TriageError.code) | 사용자 문구 |
|-----------|----------------------------------|------------|
| `unauthenticated` | `unauthenticated` | "로그인 후 다시 시도해 주세요" |
| `failed-precondition` (features.aiTriage=false / GEMINI_API_KEY 미설정) | `feature_disabled` / `internal` | "이 병원에서는 사용할 수 없습니다" / "서비스 일시 중단" |
| `invalid-argument` | `invalid_argument` | "증상 설명을 다시 확인해 주세요 (10~500자)" |
| `resource-exhausted` | `rate_limited` | "시간당 10회를 초과했습니다. {N}분 후 다시 시도해 주세요" |
| `internal` | `internal` | "AI 응답 생성 실패" |

---

## 3. RTDB 데이터 형태

### `/triage_usage/{uid}/{epochHour}`
- 값: 정수 카운트
- `epochHour` = `Math.floor(now / 3_600_000)` (UTC 시 단위 epoch hour)
- 12시간 이상 지난 bucket 은 garbage, 별도 cron 로 제거 가능 (본 sprint 비범위)

### `/triage_audit/{pushId}`
```ts
{
  actorUid: string;
  hospitalId: string;
  symptomLen: number;            // PII 보호 — 원문은 80자만 snippet
  symptomSnippet: string;        // 최대 80자
  recommendations: Array<{department, confidence}>;
  model: string;
  tokensIn: number;
  tokensOut: number;
  outcome: 'ok' | 'rate_limited' | 'emergency' | 'pii_refuse' | 'feature_disabled';
  timestamp: number;
}
```

### `audit_logs_v2` (T1-1b dual-write — 표준)
- action: `triage.recommend`
- target: hospitalId
- meta: `{ confidenceTop, departmentTop, intent, tokens, dispatchLogId? }`

---

## 4. 안전 / 정책 분기

| 케이스 | 처리 |
|--------|------|
| `features.aiTriage=false` | `failed-precondition` 즉시 거절 (LLM 호출 없음) |
| `checkEmergency()` true | LLM 우회. 응급의학과 1건 + `emergencyResponse()` 안내 + `outcome='emergency'` |
| `checkPiiRequest()` true | LLM 우회. 빈 recommendations + `PII_REFUSAL_RESPONSE` 사유 + `outcome='pii_refuse'` |
| 빈 / 너무 짧은 입력 | `invalid-argument` (Zod min 10) |
| Gemini 호출 실패 | `internal` (audit 기록 후) |
| Gemini 응답 JSON 파싱 실패 | fallback: 일반 진료과 1건만 + `outcome='ok'` (audit 에 raw error 기록) |

---

## 5. Gemini 프롬프트 설계 (`functions/src/triage/prompt.ts`)

```
SYSTEM:
당신은 환자가 작성한 증상 설명을 분석해 가장 적합한 진료과를 추천하는 의료 도우미입니다.
다음 규칙을 반드시 따르세요:
1. 진단을 내리지 않습니다. "추천"으로만 표현하세요.
2. 응답은 다음 JSON 스키마를 따르세요 (그 외 텍스트 금지):
   {
     "recommendations": [
       { "department": "<진료과 한국어>", "confidence": <0..1>, "reason": "<1-2문장>" }
     ]
   }
3. 정확히 3개의 추천을 반환하세요. 신뢰도는 가장 적합한 진료과부터 내림차순으로.
4. 다음 진료과 중에서만 선택하세요: 내과, 외과, 정형외과, 소아청소년과, 가정의학과,
   응급의학과, 영상의학과, 이비인후과, 안과, 피부과, 산부인과, 비뇨의학과, 정신건강의학과, 신경과, 재활의학과.
5. 응급 상황(가슴 통증·심한 출혈·의식 저하 등)이면 응급의학과를 1순위로 권하고
   reason 에 "즉시 응급실 또는 119 권장"을 명시하세요.

USER: <symptomText>
```

응답 검증: JSON parse → 3개 정확히 / department 가 허용 목록 / confidence 0..1 / reason 0<len<200 — 실패 시 fallback.

---

## 6. Rate limit 설계 (`functions/src/triage/rateLimit.ts`)

chatbot 의 chatbot_usage 와 다른 schema (epoch-hour bucket 단순 카운터) 를 따른다 (LOCAL_SYNC_GAPS §1.1 spec):

```ts
const TRIAGE_LIMIT_PER_HOUR = 10;

export async function checkTriageRateLimit(uid: string, nowMs: number) {
  const epochHour = Math.floor(nowMs / 3_600_000);
  const ref = admin.database().ref(`triage_usage/${uid}/${epochHour}`);
  const snap = await ref.get();
  const count = (snap.val() ?? 0) as number;
  const remaining = Math.max(0, TRIAGE_LIMIT_PER_HOUR - count);
  return { allowed: remaining > 0, remaining, retryAfterSeconds: 3600 - (Math.floor(nowMs / 1000) % 3600) };
}

export async function incrementTriageUsage(uid: string, nowMs: number) {
  const epochHour = Math.floor(nowMs / 3_600_000);
  await admin.database()
    .ref(`triage_usage/${uid}/${epochHour}`)
    .transaction((c) => (typeof c === 'number' ? c : 0) + 1);
}
```

---

## 7. 추가/변경 파일 목록

### 신규 (functions/)
| 파일 | 역할 |
|------|------|
| `functions/src/triage/types.ts` | `TriageRequest`, `TriageResult`, `TriageAuditEntry` |
| `functions/src/triage/rateLimit.ts` | epoch-hour bucket |
| `functions/src/triage/prompt.ts` | Gemini system instruction + 응답 검증 |
| `functions/src/triage/triageSymptoms.ts` | callable handler |
| `functions/src/__tests__/triageSymptoms.test.ts` | unit + scenarios |

### 신규 (frontend)
| 파일 | 역할 |
|------|------|
| `src/types/triage.ts` | `TriageRequest`, `TriageResult`, `TriageError*` |
| `src/services/triage.ts` | callable wrapper + error normalize |
| `src/services/__tests__/triage.test.ts` | wrapper + normalize |
| `src/components/patient/TriageWidget.tsx` | 위젯 UI |
| `src/components/patient/__tests__/TriageWidget.test.tsx` | render/제출/결과/에러/feature gate |

### 변경
| 파일 | 변경 |
|------|------|
| `functions/src/index.ts` | `export { triageSymptoms } from './triage/triageSymptoms'` |
| `src/components/patient/tabs/HomeTab.tsx` | `useFeature('aiTriage') && <TriageWidget/>` 마운트 |
| `src/contexts/HospitalContext.tsx` (FEATURE_DEFAULTS) | aiTriage default 변경 없음 (false 유지 — admin 가 명시 enable 해야 노출) |
| `docs/LOCAL_SYNC_GAPS.md` | §1.1 → ✅ 완료 표시 |
| `docs/E_AI_TRIAGE_REWRITE.md` | 본 문서 — §10 추적 |

### 변경 안 함 (의도적)
- RTDB rules — 이미 `triage_usage`, `triage_audit` 정의됨
- chatbot/* — 재사용만, 변경 없음
- `audit_logs_v2` — 기존 dual-write helper 사용

---

## 8. Commit 단위 계획 (총 7 commit + 1 옵션)

각 commit 빌드 + 테스트 그린 보장.

### Commit 1 — `feat(E.1a): triage types + Zod schema`
- 신규: `functions/src/triage/types.ts`, `src/types/triage.ts`
- 검증: tsc 0 errors (양쪽 workspace)
- LIVE 영향: 0

### Commit 2 — `feat(E.1b): triageSymptoms cloud function 본체`
- 신규: `functions/src/triage/{rateLimit,prompt,triageSymptoms}.ts`
- 변경: `functions/src/index.ts` export 추가
- 신규: `functions/src/__tests__/triageSymptoms.test.ts`
- 검증: vitest functions workspace 의 triage 단위 테스트 (Gemini mock + emergency / PII / rate limit / JSON parse fail / OK)
- LIVE 영향: 0 (배포 전)

### Commit 3 — `feat(E.1c): src/services/triage.ts callable wrapper`
- 신규: `src/services/triage.ts`, `src/services/__tests__/triage.test.ts`
- 검증: vitest frontend
- LIVE 영향: 0

### Commit 4 — `feat(E.2a): TriageWidget UI`
- 신규: `src/components/patient/TriageWidget.tsx`
- 신규: `src/components/patient/__tests__/TriageWidget.test.tsx`
- 검증: 단위 테스트 — 입력/제출/결과/에러/feature gate / IME 안전 / 진단 아님 disclaimer 노출
- LIVE 영향: 0

### Commit 5 — `feat(E.2b): HomeTab 통합 + features.aiTriage 가드`
- 변경: `src/components/patient/tabs/HomeTab.tsx`
- 검증: useFeature('aiTriage') 가 false 면 미마운트 / true 면 마운트
- LIVE 영향: 0

### Commit 6 — `test(E.3): scenario E 통합 smoke`
- 신규: `src/__tests__/triageIntegration.test.tsx` 또는 기존 waitQueueIntegration 확장
- 검증: features 토글 / 입력 → 결과 / rate-limit / emergency 분기

### Commit 7 — `docs(E): triage 재작성 완료 + LOCAL_SYNC_GAPS 정리`
- 변경: `docs/LOCAL_SYNC_GAPS.md` §1.1 → ✅
- 변경: 본 문서 §10 진행 추적 채움
- LIVE 영향: 0

### (옵션) Commit 8 — Functions deploy + Hosting redeploy
- 사용자 명시 승인 시:
  - `firebase deploy --only functions:triageSymptoms` (asia-northeast3)
  - `firebase deploy --only hosting` (TriageWidget 포함)
  - `HOSTING_DEPLOY_LOG.md` 추가 entry
- LIVE 영향: features.aiTriage=true 인 hospital 만 위젯 노출. demo 는 default false 유지 → admin 토글 후 활성

---

## 9. 테스트 전략

### Functions (vitest functions workspace)
| 케이스 | 모킹 |
|--------|------|
| OK 경로 — Gemini 정상 JSON | geminiChat → mock JSON 응답 |
| Rate limit 도달 — 11번째 호출 | RTDB ref mock |
| Emergency 키워드 — LLM 우회 | sanitize+intent mock |
| PII 키워드 — LLM 우회 | sanitize+intent mock |
| features.aiTriage=false — failed-precondition | RTDB hospital profile mock |
| Gemini JSON 파싱 실패 → fallback 1건 | invalid JSON 응답 mock |
| 5번째 호출 후 audit 기록 검증 | appendAuditLog spy |

### Frontend (vitest)
- service 측: payload 정규화 / HttpsError code → TriageError code 매핑 (8 매핑 케이스)
- TriageWidget: 미로그인/익명 미렌더 / aiTriage off 미렌더 / 입력 → submit → 로딩 → 결과 / rate_limited 시 안내 / emergency 응급실 안내 / disclaimer prominent
- 통합 smoke: HomeTab + TriageWidget 시나리오 E

### 회귀 보장
- 기존 222 vitest 그대로 그린
- chatbot 동작 영향 없음 (별도 함수 / 별도 rate limit / 별도 audit)

---

## 10. 진행 추적

| # | Commit | 상태 | 결과 요약 |
|---|--------|------|-----------|
| 1 | `b2ebbb0` | ✅ 완료 | functions/src/triage/types.ts + src/types/triage.ts (Zod schema + ALLOWED_DEPARTMENTS 15개) |
| 2 | `15e1dd4` | ✅ 완료 | triageSymptoms cloud function — rateLimit (epoch-hour bucket, 시간당 10회) + prompt (system instruction + JSON parse + emergency/generic fallback) + handler (auth/Zod/sanitize/feature/emergency/PII/rate-limit/Gemini/JSON/usage+1/audit dual-write) + 19 unit test |
| 3 | `d78ffe6` | ✅ 완료 | src/services/triage.ts wrapper — payload 정규화 + HttpsError → TriageError normalize (15 unit test) |
| 4 | `1773eb8` | ✅ 완료 | TriageWidget UI — 입력/결과 카드/emergency 배너/disclaimer/에러 (18 unit test) |
| 5 | `9c4c57a` | ✅ 완료 | HomeTab 통합 + features.aiTriage 가드 — 배치 순서 (WaitQueue → Triage → Chatbot) |
| 6 | `3fc095e` | ✅ 완료 | scenario E 통합 smoke (8 케이스 — E1/E2/E3/E4/E5 + 다른 위젯 격리) |
| 7 | (이 commit) | ✅ 완료 | 본 문서 progress 갱신 + LOCAL_SYNC_GAPS §1.1 정리 |

### 최종 메트릭

- **6 feat/test commit + 1 docs commit = 7 커밋**
- **vitest frontend**: 222 → 263 passed (+41 신규: 15 service + 18 widget + 8 integration; types 단위는 별도 변화 없음)
- **vitest functions**: 90 → 109 passed (+19: triageSymptoms.test)
- **tsc 0 errors** (양쪽 workspace), **vite build 성공**
- **LIVE 영향 0** — Functions deploy + Hosting redeploy 별도 승인

### Prod-parity 도달 여부 (e2e §E)

| 기대 | 충족 | 자동 검증 |
|------|------|----------|
| `features.aiTriage=true` 전제 | ✅ | E1 / E2 |
| 환자 홈 "AI 진료과 추천" 위젯 노출 | ✅ | TriageWidget.test 가시성 |
| 증상 입력 → Top-3 진료과 + 신뢰도% + reason | ✅ | E3 + service unit test |
| "진단 아님" disclaimer | ✅ | TriageWidget.test |
| 시간당 10회 → resource-exhausted | ✅ | E5 + functions unit test (rate limit 카운트 10) |
| 응급 키워드 → 응급의학과 + 119 안내 | ✅ | E4 + functions unit test (emergency 분기) |

### 남은 작업 (별도 승인)

#### Functions deploy (commit 8 옵션)
- `firebase deploy --only functions:triageSymptoms` (asia-northeast3)
- 사전 조건: `GEMINI_API_KEY` 가 functions/.env 에 설정 (chatbot 운영 중이라 이미 OK)

#### Hosting redeploy (TriageWidget 포함)
- `npx vite build`
- `firebase deploy --only hosting`
- LIVE bundle 갱신 → demo 병원의 admin 가 features.aiTriage=true 토글 시 위젯 노출

#### Admin 토글 후 시각 검증 체크리스트
1. platformAdmin 로그인 → `/admin/hospitals/demo` → features.aiTriage 체크 → 저장
2. 환자 계정 (`p0107044@gmail.com`) 로 `/h/demo/patient/home` 진입
3. 홈 탭에 "AI 진료과 추천" 위젯 노출 확인
4. "2일째 기침과 미열이 있어요" 입력 → 5초 이내 Top-3 카드 + disclaimer
5. 동일 사용자가 11번째 호출 시 "약 N분 후" 안내
6. "갑자기 가슴이 아파서 숨이 안 쉬어져요" → emergencyNotice + 응급의학과 1순위
7. Firebase Console → Functions → `triageSymptoms` 로그 확인
8. RTDB `/triage_audit/<pushId>` 와 `/triage_usage/<uid>/<epochHour>` 갱신 확인

---

## 11. 합의 요청 항목

사용자 승인 필요:

1. **재사용 vs 격리**: chatbot 의 safety / Gemini provider 를 직접 import 해 재사용 (코드 중복 0). 동의?
2. **Rate limit shape**: epoch-hour bucket (`/triage_usage/{uid}/{epochHour}=count`) 으로 LOCAL_SYNC_GAPS §1.1 spec 그대로. 동의?
3. **응답 schema**: §2 의 `TriageResult` (recommendations[3] + confidence + reason + disclaimer + tokens + rateLimit). 동의?
4. **Emergency 분기**: LLM 우회 + 응급의학과 1건 + 119 안내. 동의?
5. **PII 분기**: LLM 우회 + 빈 recommendations + 거절 사유. 동의?
6. **Default features.aiTriage**: false 유지 (admin 가 명시 enable 후 노출). 동의?
7. **Commit 분할**: 6 feat/test + 1 docs (총 7) OK?
8. **Commit 8 (deploy)**: 본 sprint 외 별도 승인 단계. 동의?

승인되면 commit 1 부터 순차 진행.
