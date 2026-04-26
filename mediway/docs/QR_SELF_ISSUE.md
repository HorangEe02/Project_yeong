# QR 코드 자가 발급 + Rate Limit (옵션 B)

> 작성일: 2026-04-26 (GuideTab 모드 부활 직후)
> 사용자 요청: 환자 home 탭에서 의료진 데스크 거치지 않고 자가 QR 발급 가능하도록
> 결정: 옵션 B (자가 발급 버튼 + RTDB rule + transaction-based 시간당 30회 cap)

---

## 1. 결정 배경

LIVE 시각 검증 중 발견:
- GuideTab 「QR 안내」 모드는 placeholder 안내만 표시 (3단계 step)
- 실제 QR 코드 화면은 `/h/:slug/patient/:sessionId` 진입 시에만 마운트되는 PatientDashboard 안에 있음
- 사용자가 sessionId 모르는 home 진입 시 자가 발급 진입점 없음

비범위로 분류했던 항목:
> 비범위: QR 코드 자가 발급 — `PatientDashboard` 의 QRDisplay 를 home 에 마운트하면
> localStorage / useSession 으로 인한 부작용 위험

⇒ 사용자 요구로 본 sprint 진행 — **자가 발급 + 어뷰즈 방지 cap** 동시 도입.

---

## 2. 구현 요약

### 2.1 인프라 (commit `4ef9147`)
- **`src/services/qrToken.ts`** — `issueSelfQRToken(token, uid, now)`
  - epoch-hour bucket: `Math.floor(now / 3_600_000)`
  - `runTransaction` 으로 `/qr_token_usage/{uid}/{epochHour}` ++  
    초과 시 `undefined` 반환 → committed=false → `QRTokenRateLimitError` throw
  - 통과 시 `/qr_tokens/{token}` 에 `{ patientUid, status:'waiting', createdAt }` set
- **`database.rules.json`** — `/qr_token_usage` 신규 path
  - self-only read/write (`auth.uid === $uid`)
  - `$epochHour` validate: number + `0..30` (RTDB 측 hard cap — 클라이언트 우회 차단)
  - platformAdmin 모니터링용 read

### 2.2 UI (commit `0711b72`)
- **`src/components/patient/QRGuidePlaceholder.tsx`** — `'placeholder' | 'displaying'` mode 머신
  - placeholder: 기존 3단계 안내 + 「내 QR 코드 발급」 primary 버튼
  - displaying: 「다시 안내 보기」 back 버튼 + `<QRDisplay onTokenGenerated={...} />`
  - `handleTokenGenerated` 콜백: getCurrentUid → initAnonymousAuth fallback → `issueSelfQRToken`
  - 에러 분기:
    - `QRTokenRateLimitError` → "약 N분 후" 안내 + placeholder 복귀
    - 일반 에러 → "토큰 발급에 실패했습니다" + placeholder 복귀
  - 버튼 disabled 조건: `!useAuthStore.initialized`

### 2.3 테스트 (commit `b90ccf1`)
- **`src/services/__tests__/qrToken.test.ts`** — 9 케이스
  - 정상 / transaction 함수 동작 (cur=null/29/30) / rate-limit / Firebase 미설정 / 상수 회귀
- **`src/components/patient/__tests__/QRGuidePlaceholder.test.tsx`** — 15 케이스
  - placeholder 모드 8 (기존 6 + 버튼 활성·비활성)
  - 모드 토글 2
  - 토큰 발급 흐름 5 (성공 / 일반 에러 / rate-limit 분 단위 안내 / retry 1초 → 1분 보장)

---

## 3. Rate Limit 정책

| 파라미터 | 값 | 근거 |
|----------|-----|------|
| Cap | 시간당 30 회 | 정상 사용량 ~20/h (3분 자동 갱신 + 수동 갱신 ~몇 회) — 30 cap 은 어뷰즈 방어용 |
| Bucket | `epochHour = floor(now / 3_600_000)` | UTC 시 단위 — chatbot/triage rate-limit 와 동일 패턴 |
| 강제 layer | RTDB rule (`<= 30` validate) + Transaction abort | 두 layer 이중 — 클라이언트 우회 시도 차단 |
| Retry 안내 | `nextHour - now` 초 | 분 단위 (`Math.ceil(seconds/60)`) — 최소 1분 보장 |

### 어뷰즈 시나리오 차단
- DevTools 에서 `set('/qr_tokens/...', ...)` 직접 호출 — `/qr_token_usage` 증분 없으면 cap 검증 못 함 → 단, qr_tokens write 자체는 여전히 허용됨 (기존 rules 유지)
- DevTools 에서 `/qr_token_usage` 직접 31 로 set — RTDB rule `validate <= 30` 거부
- DevTools 에서 transaction 우회 — set 으로 카운터 임의값 시도 가능하지만 30 초과는 거부

⇒ 본 cap 은 **합리적 사용자에 대한 제한** + **악성 봇의 RTDB DoS 방어**. 100% 안전은 아니며 진정한 보안은 Cloud Function 게이트웨이가 필요 (별도 sprint).

---

## 4. 진행 추적

| # | Commit | 상태 | 결과 요약 |
|---|--------|------|-----------|
| 1 | `4ef9147` | ✅ 완료 | RTDB rules /qr_token_usage + qrToken service (9 unit test) |
| 2 | `0711b72` | ✅ 완료 | QRGuidePlaceholder 자가 발급 모드 + QRDisplay 통합 |
| 3 | `b90ccf1` | ✅ 완료 | QRGuidePlaceholder 자가 발급 단위 테스트 (15 케이스) |
| 4 | (이 commit) | ✅ 완료 | docs |

### 메트릭
- vitest: 279 → **297 passed** (+18: 9 service + 9 widget 신규 케이스)
- tsc 0 errors, vite build 성공
- LIVE 영향 0 — rules deploy + hosting redeploy 별도

---

## 5. 후속 (별도 승인)

### 5.1 Rules + Hosting deploy
- `firebase deploy --only database` (RTDB rules — `/qr_token_usage` 신규 적용)
- `npx vite build && firebase deploy --only hosting` (UI 번들 갱신)
- `HOSTING_DEPLOY_LOG.md` + 새 entry

### 5.2 시각 검증 체크리스트
1. 환자 (또는 platformAdmin) `/h/demo/patient/home?tab=guide` 진입
2. 「QR 안내」 활성 → 3단계 안내 + 「내 QR 코드 발급」 primary 버튼 노출
3. 버튼 클릭 → QRDisplay 마운트 (uuid QR + 3분 자동 갱신 + 수동 갱신)
4. 「다시 안내 보기」 → placeholder 복귀
5. RTDB Console → `/qr_token_usage/<uid>/<epochHour>` 카운터 증가 확인
6. RTDB Console → `/qr_tokens/<token>` 에 새 entry 확인 (status='waiting', patientUid)
7. (선택) 31번째 발급 시도 → "약 N분 후" 안내 표시

### 5.3 향후 개선 옵션 (별도 sprint)
- Cloud Function `requestQRToken` gateway — server-side 인증 cap (현 cap 보다 강력)
- `/qr_tokens/<token>` 자동 만료 (createdAt + 30분 후) — RTDB cron 또는 client TTL
- 의료진이 환자 QR 발급 (위임) — staff role 만 가능한 발급 경로 추가
- Rate-limit cap 을 hospital features 매트릭스로 분기 (hospital 별 정책)
