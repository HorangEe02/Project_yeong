# P3 선결 항목 체크리스트

> **상태**: 사용자 결정·계정 개설 대기 (2026-04-23)
> **목적**: P3 착수 전에 확보해야 할 외부 계정·키·벤더 결정을 한 곳에 모음.
> **다음 세션에서**: 이 문서 체크박스 전부 완료되면 `mediway/plusultra/p3` 브랜치 생성 후 C1부터 순차 구현.

---

## 1. 🥇 AI Triage 벤더 결정 (F19)

### 후보 3개 비교

| 벤더 | 모델 | 비용 (월 10k 호출) | 한국어 품질 | 권장 사유 |
|---|---|---|---|---|
| **OpenAI** | gpt-4o-mini | ~$20 | 우수 | 범용, 한국어 품질 안정 |
| **Anthropic** | claude-3-5-haiku | ~$25 | 우수 | 안전성·"진단 아님" 고지 자연스러움 |
| **Google** | gemini-1.5-flash | ~$10 | 양호 | 최저 비용 |

### 의료 도메인 관점

- **권장: Anthropic Claude Haiku** — 의료·법무 민감 주제에서 "진단 아님" 안전장치 내재화, prompt injection 방어 우수
- 비용 차이 크지 않음 (월 $25 ≈ 월 3만원)

### 결정 필요
- [ ] **벤더 확정**: ☐ OpenAI / ☐ Anthropic / ☐ Gemini
- [ ] 계정 개설 + API key 발급
- [ ] 월 사용 한도 설정 (안전망): 예 $50/mo

### 링크
- OpenAI: https://platform.openai.com/api-keys
- Anthropic: https://console.anthropic.com/settings/keys
- Google AI: https://aistudio.google.com/apikey

---

## 2. 💳 카카오페이 (F8)

**가장 오래 걸리는 항목** — 심사·가맹점 계약 7~14일.

### 단계

- [ ] [카카오페이 온라인 결제 가맹점 신청](https://biz.kakaopay.com/service/payment) — 사업자등록증 필수
- [ ] 사업자등록증 없으면 **샌드박스 개발자 계정**만 먼저 발급받아 개발 진행
- [ ] Test CID (샌드박스) 수령: `TC0ONETIME`
- [ ] 실 CID 수령 (가맹점 승인 후)
- [ ] Admin Key 획득: 카카오 비즈계정 → 결제 탭

### Firebase Secret Manager 저장 예정
```
KAKAO_ADMIN_KEY   = "실제 키"
KAKAO_CID_TEST    = "TC0ONETIME"
KAKAO_CID_PROD    = "가맹점별 CID"
```

### 결정 필요
- [ ] **사업자 유무**: ☐ 있음 (실결제 가능) / ☐ 없음 (샌드박스만)
- [ ] 결제 대상 범위: 진료비만 / 검진비까지 / 처방비까지

---

## 3. 💬 카카오 알림톡 (F5)

**템플릿 심사 7-14일** — 병행 제출 필수.

### 단계

- [ ] [카카오 비즈니스 채널 개설](https://business.kakao.com/) (카카오톡 채널 생성)
- [ ] 비즈메시지 API 연동 신청 (Kakao i Connect API 또는 알림톡 파트너)
- [ ] 템플릿 5종 작성:
  1. 진료 예약 확인
  2. 다음 환자 호출 (5분 전)
  3. 결제 영수증
  4. 예약 취소 안내
  5. 내일 예약 리마인더
- [ ] 템플릿 심사 제출 → 반려 시 수정
- [ ] 발송 API key 수령

### 대안 (심사 지연 대비)

**3중 fallback**:
1. 알림톡 (승인 후)
2. **FCM Push** (Web / Android / iOS) — 즉시 가능
3. **SMS** (Twilio or NHN Cloud) — backup

### Secret Manager 예정
```
KAKAO_BIZMESSAGE_API_KEY = "..."
KAKAO_BIZMESSAGE_SENDER_KEY = "..."
SMS_PROVIDER_KEY = "..."   # 선택
```

### 결정 필요
- [ ] **발송 주체**: ☐ 병원별 (각 병원이 카카오 채널 보유) / ☐ 플랫폼 공용 (MediWay 운영사가 발송)
- [ ] SMS fallback 도입 여부

---

## 4. 🔑 Firebase Secret Manager 활성화

Cloud Functions v2에서 Secret 주입 방식 표준.

### 단계

- [ ] [Google Cloud Console → Secret Manager](https://console.cloud.google.com/security/secret-manager?project=mediway-demo) 접속
- [ ] Secret Manager API 활성화 (최초 1회)
- [ ] 각 secret을 CLI로 세팅:

```bash
firebase functions:secrets:set KAKAO_ADMIN_KEY
firebase functions:secrets:set KAKAO_CID_TEST
firebase functions:secrets:set LLM_API_KEY
firebase functions:secrets:set KAKAO_BIZMESSAGE_API_KEY
```

각 명령 실행 시 값 입력 프롬프트.

### Cloud Function 코드에서 접근

```typescript
import { defineSecret } from 'firebase-functions/params';
const kakaoAdminKey = defineSecret('KAKAO_ADMIN_KEY');
export const approvePayment = onCall(
  { secrets: [kakaoAdminKey] },
  async (req) => {
    const key = kakaoAdminKey.value();
    ...
  }
);
```

### 결정 필요
- [ ] Secret 저장소는 **Google Secret Manager 사용** (기본값, 권장)
- [ ] 비밀번호 rotation 주기 정책 (예: 90일)

---

## 5. ⚖️ 법무 검토

구현 착수 전 반드시 확인 필요.

### 확인 항목

| 주제 | 핵심 질문 |
|---|---|
| **대리결제** | 보호자가 환자 진료비 결제 — 개인정보 동의 범위? 금액 상한 필요? |
| **AI 증상 triage** | "추천" 수준의 LLM 응답 — 의료법 "진료 행위" 경계? 고지문 표준? |
| **알림톡 내용** | 진료·처방 관련 발송 — 광고성 정보 vs 정보성 구분 (정보통신망법) |
| **처방전 PDF 공유** | 환자 외 제3자 열람 가능성 (공유 링크 만료 정책) |
| **FCM 토큰 저장** | 기기 ID 수준의 개인정보 — PIPA 고지 필수 |

### 대안 (법무 없이 P3 진행 가능 여부)

- 대리결제: **Drop 또는 사전 승인 플로우 추가**
- AI triage: "진단 아님" 고지 UI 명시 + audit log
- 알림톡: 사용자 동의 스위치 (더보기 탭 알림 설정)

### 결정 필요
- [ ] 법무 검토 **선행** / **병행** / **skip (MVP는 고지문만)**
- [ ] 대리결제 범위: **사전 승인 필수** / **링크 공유 OK**

---

## 6. 🧪 샌드박스 vs 프로덕션 전략

### 권장 플로우

1. **Phase A (D1-D10)** — 샌드박스만
   - 카카오페이 Test CID
   - 알림톡 심사 대기 중 → FCM+SMS로 대체 테스트
   - LLM API key (dev 전용)

2. **Phase B (D11-D16)** — 프로덕션 전환
   - 실 CID · 실 템플릿 · 실 LLM 쿼터
   - Feature flag로 A → B 점진 전환

### Secret Manager 구조
```
DEV 환경:  KAKAO_CID_TEST, LLM_API_KEY_DEV
PROD 환경: KAKAO_CID_PROD, LLM_API_KEY_PROD
```

`features.payment` 플래그로 병원별 on/off.

---

## 7. 📋 최종 체크리스트 (다음 세션 진입 조건)

체크박스 전부 완료 시 P3 C1 착수 가능.

### 필수 (P3 C10 AI triage 이전에 완료)
- [ ] AI triage 벤더 확정 + API key 발급
- [ ] Firebase Secret Manager 활성화 + `LLM_API_KEY` 설정

### 중요 (P3 C7 카카오페이 이전에 완료)
- [ ] 카카오페이 샌드박스 계정 + Test CID
- [ ] Admin Key Secret Manager 저장

### 중요 (P3 C11 알림톡 이전에 완료)
- [ ] 카카오 비즈니스 채널 개설
- [ ] 템플릿 5종 심사 제출 (승인은 병행)

### 권장 (P3 전반에 영향)
- [ ] 법무 검토 질의 (최소 대리결제 · AI 고지 2건)
- [ ] 프로덕션 Secret 구조 결정 (`_TEST`/`_PROD` 분리 여부)

### 낮음 (필요 시)
- [ ] SMS provider 결정 (Twilio / NHN Cloud / Aligo)

---

## 8. 🚀 다음 세션에서 할 일 (예상)

위 체크박스 기준 완료도에 따라:

**Case A: 전부 완료**
→ `mediway/plusultra/p3` 브랜치 생성 + C1(대기 순번 스키마) 즉시 착수

**Case B: AI·Secret만 완료, 카카오 심사 대기**
→ C1-C5 (대기 순번·FCM) + C10 (AI triage) + C12 (주차·입원/검진) 먼저
→ C6-C9, C11은 카카오 승인 후 후속 작업

**Case C: 아무 것도 완료 안 됨**
→ C12 주차·입원/검진 실내용 + `public/e2e-*.html` 시나리오 정비 정도
→ 또는 P4 (고령자·가족 대리·OAuth) 먼저 — v2 기준 **MOAT #1**이 여기 있어 실은 P3보다 먼저 가능

---

## 9. 🔗 바로가기 (URL 모음)

### Firebase
- Console: https://console.firebase.google.com/project/mediway-demo
- Secret Manager: https://console.cloud.google.com/security/secret-manager?project=mediway-demo
- Functions Secrets 문서: https://firebase.google.com/docs/functions/config-env

### 카카오
- 개발자 콘솔: https://developers.kakao.com/
- 카카오페이 가맹점: https://biz.kakaopay.com/service/payment
- 비즈니스 채널: https://business.kakao.com/
- 알림톡 템플릿 가이드: https://kakaobusiness.gitbook.io/main/tool/chatbot/api-reference/alimtalk

### LLM 벤더
- OpenAI Platform: https://platform.openai.com/
- Anthropic Console: https://console.anthropic.com/
- Google AI Studio: https://aistudio.google.com/

### 현재 코드
- PR #1 (P1): https://github.com/HorangEe02/Project_yeong/pull/1
- PR #2 (P2): https://github.com/HorangEe02/Project_yeong/pull/2
- `mediway/develop` @ `caa89b0` — P3 계획 커밋 완료

---

_작성일: 2026-04-23 · 다음 세션 진입 전 이 체크리스트 완료 후 재개_
