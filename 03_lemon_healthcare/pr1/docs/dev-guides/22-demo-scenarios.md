# dev-guides/22 — 시연 시나리오 (페르소나 A/B별)

> **Phase**: 4 | **선행 작업**: Phase 1-3 모두 완료 | **예상 소요**: 4~5시간

---

## 🎯 작업 목표

발주처(레몬헬스케어) 시연 발표를 위한 시나리오를 작성한다. 1차 페르소나 B(만성질환자)와 2차 페르소나 A(예방 직장인) 각각의 5종 출력을 자연스럽게 보여주는 데모 스크립트 + 백업 영상 + 시연 데이터 시드.

---

## 📋 산출물

```
demo/
├── scenarios/
│   ├── persona_a_park_jikjang.md      # 38세 박직장 시나리오
│   ├── persona_b_kim_geongang.md      # 52세 김건강 시나리오 (메인)
│   └── differentiation_message.md     # 필라이즈 차별화 메시지
├── seeds/
│   ├── persona_a_seed.json             # 시연용 데이터 (걸음수·영양제·식단)
│   ├── persona_b_seed.json
│   └── load_demo_data.py               # 시연 환경 초기화 스크립트
├── backup_videos/
│   ├── persona_a_full_flow.mp4         # 백업 시연 영상 (네트워크 장애 대비)
│   └── persona_b_full_flow.mp4
└── checklists/
    ├── pre_demo_checklist.md           # 시연 시작 30분 전
    └── live_demo_script.md             # 실시간 진행 큐 카드
```

---

## 📐 시연 구조

### 전체 시연 흐름 (15~20분)

```
[1] 도입 (2분)
    └→ 현재 디지털 헬스케어 시장 + 필라이즈 한계
[2] 차별화 메시지 (1분)
    └→ "만성질환자 + 의료데이터" 차별화
[3] 페르소나 B 시연 (8분)  ← 메인
    └→ 김건강(52세 만성질환자) 5종 출력 흐름
[4] 페르소나 A 시연 (4분)  ← 보조
    └→ 박직장(38세 예방) 차이점만 강조
[5] 기술·확장성 (3분)
    └→ Adapter 패턴, Hall 모델, 의료법 컴플라이언스
[6] Q&A (2~5분)
```

### 시연 우선순위

| 우선순위 | 시연 항목 | 이유 |
|---------|---------|-----|
| **★★★** | 영양제 사진 등록 → 5종 출력 | 발주처가 가장 궁금한 부분 |
| **★★★** | 부족 영양소 + 목적별 분석 | 만성질환자 핵심 가치 |
| **★★** | Hall 모델 체중 예측 | 7-step과 차이 강조 |
| **★★** | 식단 인식 (이미지·텍스트) | 일상 사용성 |
| **★** | 피드백 + 알림 | 운영 측면 |

---

## 🔧 페르소나 B 시나리오: 김건강 (메인)

> 🎯 **타겟**: 발주처가 "이거 우리 환자에게 쓰겠다" 라고 느끼게 만들기

### 페르소나 B 프로필

```yaml
이름: 김건강
나이: 52세
성별: 남성
키/체중: 172cm / 78kg (BMI 26.4 — 과체중)
직업: 자영업
만성질환:
  - 제2형 당뇨병 (5년차)
  - 고혈압 (3년차)
복용 영양제:
  - 종합비타민 (1정/일)
  - 오메가-3 (1캡슐/일)
  - 마그네슘 (1정/일)
일상:
  - 평균 걸음수: 4,500보 (권장 미달)
  - 평균 심박: 72 bpm
  - 식단: 한식 위주, 짠 음식 선호
관심사: 만성질환 관리, 약-영양제 상호작용
```

### 시연 스크립트

```markdown
## Scene 1: 첫 진입 (30초)

[모바일 화면] 앱 첫 실행

🎙 진행자:
"안녕하세요. 만성질환자 중심의 AI 헬스케어 서비스, 건강의 신을 소개합니다.
지금 보시는 화면이 김건강 님의 홈입니다. 김건강 님은 52세 자영업자로,
제2형 당뇨와 고혈압을 5년째 관리하고 계신 분입니다."

[화면] 홈 화면에서 4가지 메뉴 카드 + 활동 요약
- 오늘의 활동점수: 65/100 (개선 필요)
- 면책 고지 위젯이 화면 하단에 보임 ← 강조

🎙 강조 포인트:
✅ 모든 화면에 의료법 면책 고지 — 학생 팀 차원에서도 컴플라이언스 의식
✅ 만성질환자 컨텍스트가 즉시 반영됨 (활동점수 v4 적용)


## Scene 2: 영양제 등록 (90초)

[화면] "영양제 등록" 메뉴 탭

🎙 진행자:
"김건강 님이 어머니가 새로 사 주신 영양제 라벨을 등록하려고 합니다."

[화면] 카메라/갤러리 선택 → 갤러리 → 종합비타민 이미지 선택 → 크롭 → 업로드

[로딩] 진행률 표시 (약 5초)

[결과 화면] 영양제 분석 결과
- 제품명: 종합비타민 컴플렉스
- 성분: 비타민C 1000mg, 비타민D 25μg, 칼슘 600mg, ...

🎙 강조 포인트:
✅ Cloud Vision OCR + Claude LLM Tool Use 백업 폴백 동작
✅ 식약처 인정 원료 DB 매칭 — 표준 영양소 코드 변환
✅ 단위 자동 환산 (IU → μg)


## Scene 3: 부족 영양소 결과 ① (90초)

[화면] 자동으로 "부족 영양소 분석" 화면 표시

[중요] 화면 상단에 빨간 경고 배너:
⚠ 비타민 D 섭취량이 권장량의 25% — 결핍

[화면 중간] 부족 영양소 카드
┌─────────────────────────────┐
│ 비타민 D            25%      │
│ ⚪⚪░░░░░░░░░░░             │
│ 25 μg / 권장 100 μg          │
│                              │
│ "비타민 D 섭취량이 권장량의   │
│  25% 수준입니다.              │
│  관련 식품 섭취를 늘리는       │
│  것을 고려해보세요."           │
│                              │
│ 권장 식품: 연어, 계란노른자,   │
│           햇볕 노출           │
└─────────────────────────────┘

🎙 강조 포인트:
✅ 만성질환자 + 50대 남성의 KDRIs로 정확한 진단
✅ 의료법 표현 가이드 — "진단", "처방" 단어 0건
✅ 식약처 인정 식품만 권장 (영양제 추천 X)


## Scene 4: 목적별 분석 ⑤ (60초)

🎙 진행자:
"김건강 님은 최근 피로감을 자주 느끼셔서, 목적별 분석을 살펴보십니다."

[화면] 홈 → 목적별 분석 → 7개 카드 그리드 → "💪 피로 회복" 선택

[결과 화면]
┌─────────────────────────────┐
│ 💪 피로 회복                  │
├─────────────────────────────┤
│ ⚠ 피로 회복과 관련된 영양소   │
│   4종 중 2종 부족             │
│                              │
│ 비타민 B1     [핵심]         │
│ ⚪⚪░░░░░ 30% (결핍)          │
│ ✓ 식약처 인정 기능성:         │
│   "비타민 B1은 에너지 생산에  │
│    필요"                      │
│                              │
│ 철분          [핵심]         │
│ ⚪⚪⚪⚪⚪░░ 60% (부족)        │
│ ✓ 식약처 인정 기능성:         │
│   "철은 체내 산소 운반과       │
│    혈액 생성에 필요"           │
│                              │
│ 권장 식품:                   │
│ 현미, 통밀, 견과류,           │
│ 시금치, 콩, 적색육            │
└─────────────────────────────┘

🎙 강조 포인트:
✅ 식약처 인정 표시 강조 (파란 배경 + ✓ 마크)
✅ 의료법 표현 가이드 자동 검증 통과
✅ 만성질환자가 자주 묻는 "왜 피곤할까" 질문에 데이터 기반 답변


## Scene 5: 체중 변화 예측 ③ (Hall 모델) (60초)

[화면] 홈 → 체중 변화 예측

🎙 진행자:
"김건강 님은 당뇨 관리를 위해 체중 감량 목표를 세우셨습니다."

[화면] 라인 차트
시작: 78.0 kg
1주 후: 77.4 kg (-0.6)
1개월 후: 76.0 kg (-2.0)
3개월 후: 73.5 kg (-4.5)

🎙 강조 포인트:
✅ Hall 동적 모델 — 단순 7-step보다 정확
✅ 일별 BMR 자기조정 (체중 감소 시 대사 적응 반영)
✅ 정체기(plateau) 예측 가능 → 무리한 다이어트 방지
✅ 면책 고지 — "급격한 체중 변화는 건강에 해로울 수 있으니 의료진과 상담하세요"


## Scene 6: 운동 권고 ④ (30초)

[화면] 운동 권고 → 권장 걸음수 7,524보 (성별·만성질환·BMI 반영)

🎙 짧게:
"v1~v4 4가지 활동점수가 모두 표시됩니다.
v4는 만성질환자용 보정으로, 김건강 님 같은 분께
무리하지 않는 활동 강도를 안내합니다."


## Scene 7: 식단 입력 (60초)

[화면] 식단 입력 → 텍스트 입력 모드

🎙 진행자:
"점심 식사를 텍스트로 빠르게 입력하시면..."

[입력] "점심 — 공기밥 1개, 김치찌개 1그릇, 계란말이 1개"

[로딩 → 결과]
✓ 공기밥 1공기 (210g)
✓ 김치찌개 1그릇 (300g)
✓ 계란말이 1개 (80g)

→ 사용자가 양 수정 가능 + 음식 추가/삭제

🎙 강조 포인트:
✅ Claude Vision으로 사진도 인식 가능 (텍스트가 더 저렴해서 기본값)
✅ 농진청 식품성분 DB 매칭 → 영양소 자동 합산
✅ 사용자 수정 UI — LLM이 100% 정확하지 않다는 정직한 인정


## Scene 8: 피드백 + 알림 (45초)

[화면] 영양제 등록 완료 후 자동 모달
"성분 인식이 정확했나요?"
별점 1~5 + (선택) 코멘트

🎙 진행자:
"피드백 데이터는 자동 집계되어 OCR·LLM 정확도 모니터링에 활용됩니다.
LDB 의료기관 네트워크와 연계하면, 의사가 환자의 영양 패턴을 함께 볼 수 있는
가능성도 열립니다."

[화면 전환] 시연 디바이스에 푸시 알림 도착
🔔 "오늘 권장 걸음수의 65%를 채우셨어요. 잠깐 산책 어떠세요?"

🎙 강조 포인트:
✅ FCM (Android) + APNs (iOS) Adapter 패턴
✅ 의료법 표현 가이드 자동 검증된 알림 템플릿
✅ 야간(22~07시) 발송 차단 — 사용자 친화


## Scene 9: 마무리 메시지 (30초)

🎙 진행자 (강조):
"필라이즈가 건강한 직장인을 위한 영양제 추천에 강하다면,
저희가 만든 건강의 신은 만성질환자와 의료데이터 영역에 특화되어 있습니다.
LDB 네트워크의 130여 의료기관이 보유한 임상 데이터를
이 플랫폼과 연결하면, 후발주자가 따라올 수 없는 해자가 됩니다."

[화면] 닫기 → 홈
```

---

## 🔧 페르소나 A 시나리오: 박직장 (보조)

### 박직장 프로필

```yaml
이름: 박직장
나이: 38세
성별: 여성
키/체중: 165cm / 56kg (BMI 20.6 — 정상)
직업: IT 회사 직장인
질환: 없음 (예방 목적)
복용 영양제:
  - 멀티비타민
  - 오메가-3
  - 칼슘+비타민D
일상:
  - 평균 걸음수: 8,200보 (양호)
  - 헬스장 주 3회
  - 식단: 다이어트·예방 중심
관심사: 면역력, 피부, 피로 회복
```

### 차이점만 강조 시연 (4분)

```markdown
## 박직장 시연 핵심 차이점

[Scene 1: 활동점수 v3 ↔ v4 비교]
- 박직장: v3 (백분위) 점수가 92점 (양호)
- 김건강: v4 (만성질환 보정) 점수가 65점 (개선 필요)
→ 같은 8,000보여도 만성질환 유무에 따라 다른 평가

[Scene 2: 목적별 분석 차이]
- 박직장: "면역력" 선택 → 비타민 C, D, 아연이 적정
- 김건강: "피로 회복" 선택 → B1, 철분 부족

[Scene 3: 체중 예측]
- 박직장: 거의 변화 없음 (이미 적정 BMI)
- 김건강: -4.5kg/3개월 (감량 목표)

[Scene 4: 면책 고지 차이 X]
→ 두 페르소나 모두 동일하게 면책 고지 표시
   "법적·의료적 안전성은 사용자 유형 무관 — 일관성"
```

---

## 🔧 시연 데이터 시드

### `demo/seeds/load_demo_data.py`

```python
"""시연 환경 초기화 스크립트.

실행 전 이 스크립트로 페르소나 A/B의 데이터를 DB에 삽입.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, UTC, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import async_session_maker
from src.models.db.user import User
from src.models.db.supplement import Supplement


SEED_DIR = Path(__file__).parent


async def load_persona_b() -> None:
    """페르소나 B (김건강) 데이터 시드."""
    seed_path = SEED_DIR / "persona_b_seed.json"
    with seed_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    async with async_session_maker() as session:
        # 1. 사용자 생성
        user = User(
            id=uuid4(),
            email="kim_geongang@demo.lemonhc.com",
            name="김건강",
            age=52,
            sex="male",
            height_cm=172,
            weight_kg=78,
            chronic_conditions=["type2_diabetes", "hypertension"],
            is_pregnant=False,
            is_lactating=False,
        )
        session.add(user)
        await session.flush()

        # 2. 영양제 등록 이력 (3개월간)
        for supp_data in data["supplements"]:
            registered_at = datetime.now(UTC) - timedelta(days=supp_data["days_ago"])
            session.add(Supplement(
                id=uuid4(),
                user_id=user.id,
                product_name=supp_data["product_name"],
                manufacturer=supp_data["manufacturer"],
                ingredients=supp_data["ingredients"],
                ocr_engine="google_vision_v1",
                llm_engine="claude:claude-sonnet-4-6",
                registered_at=registered_at,
            ))

        # 3. 걸음수·체중 (HealthSync 시뮬레이션)
        # ... (DailySteps, WeightRecord 모델에 따라)

        await session.commit()
        print(f"✓ Loaded persona B: {user.email}")


async def main() -> None:
    await load_persona_b()
    # await load_persona_a()


if __name__ == "__main__":
    asyncio.run(main())
```

### `demo/seeds/persona_b_seed.json`

```json
{
  "user_profile": {
    "name": "김건강",
    "age": 52,
    "sex": "male",
    "height_cm": 172,
    "weight_kg": 78,
    "chronic_conditions": ["type2_diabetes", "hypertension"]
  },
  "supplements": [
    {
      "days_ago": 30,
      "product_name": "종합비타민 컴플렉스",
      "manufacturer": "데모제약",
      "ingredients": [
        {"code": "vitamin_c_mg", "amount": 1000, "unit": "mg"},
        {"code": "vitamin_d_ug", "amount": 25, "unit": "ug"},
        {"code": "calcium_mg", "amount": 600, "unit": "mg"}
      ]
    },
    {
      "days_ago": 60,
      "product_name": "오메가-3",
      "manufacturer": "데모제약",
      "ingredients": [
        {"code": "epa_mg", "amount": 600, "unit": "mg"},
        {"code": "dha_mg", "amount": 400, "unit": "mg"}
      ]
    }
  ],
  "daily_steps_30days": {
    "average": 4500,
    "data_points": "see steps_history.csv"
  },
  "weight_history_90days": {
    "starting_weight": 80,
    "current_weight": 78,
    "data_points": "see weight_history.csv"
  }
}
```

---

## 📋 시연 시작 30분 전 체크리스트

### `demo/checklists/pre_demo_checklist.md`

```markdown
# 🎯 시연 30분 전 체크리스트

## 환경
- [ ] 백엔드 서버 정상 동작 확인 (헬스체크 GET /health)
- [ ] PostgreSQL + Redis Docker 컨테이너 가동
- [ ] 시연 데이터 시드 적재 완료 (persona_a, persona_b)
- [ ] Google Cloud Vision API 키 유효성 확인
- [ ] Anthropic API 키 + 잔액 확인 (≥ $5)
- [ ] FCM 서비스 계정 인증 정상

## 디바이스
- [ ] iPhone 시연용 (충전 100%, 비행기 모드 OFF)
- [ ] Android 시연용 (충전 100%)
- [ ] 백업 디바이스 1대 (네트워크 장애 대비)
- [ ] 시연용 사진 갤러리에 미리 저장:
  - [ ] 종합비타민 라벨 (선명한 사진)
  - [ ] 점심 식사 사진
  - [ ] 백업 영양제 라벨 (Plan B)

## 네트워크
- [ ] 시연 장소 Wi-Fi 연결 확인
- [ ] 모바일 LTE/5G 백업 연결
- [ ] VPN 종료 (속도 저하 방지)

## 자료
- [ ] PPTX 발표 자료 최종본 (가이드 23 산출물)
- [ ] 백업 시연 영상 (네트워크 장애 시 재생)
- [ ] Q&A 예상 질문지 (가이드 24 산출물)
- [ ] 명함 / 연락처

## 사람
- [ ] 진행자 1명 (메인 발표)
- [ ] 시연자 1명 (디바이스 조작)
- [ ] 백업 1명 (Q&A 보조, 트러블슈팅)
- [ ] 학생 팀 도착 시각 — 시연 시작 1시간 전

## 비상 대응
- [ ] 백엔드 다운 시 → 백업 영상 재생
- [ ] OCR 실패 시 → "이 케이스는 미세조정이 필요합니다" 멘트 + 다른 사진
- [ ] LLM 응답 지연 시 → "5초 정도 소요됩니다" 멘트 + 사이드 토픽
```

---

## ✅ Definition of Done

- [ ] `demo/scenarios/persona_b_kim_geongang.md` (메인 시나리오, 9 Scene)
- [ ] `demo/scenarios/persona_a_park_jikjang.md` (보조, 차이점만)
- [ ] `demo/scenarios/differentiation_message.md` (필라이즈 차별화)
- [ ] `demo/seeds/persona_b_seed.json` + `persona_a_seed.json`
- [ ] `demo/seeds/load_demo_data.py` (DB 적재 스크립트)
- [ ] `demo/checklists/pre_demo_checklist.md`
- [ ] `demo/checklists/live_demo_script.md` (실시간 큐 카드)
- [ ] `demo/backup_videos/` 폴더 (시연 녹화본 2개)
- [ ] 백엔드 + 모바일 양쪽에서 시드 데이터 정상 표시 확인
- [ ] 페르소나 B 시나리오 9개 Scene 모두 디바이스에서 시연 성공
- [ ] 면책 고지가 모든 화면에 표시되는지 최종 검증

---

## 💡 구현 팁

### 시연 데이터의 "현실감"

```
❌ 너무 완벽한 데이터 (의심받음)
   - 모든 영양소가 정확히 권장량
   - 걸음수가 매일 10,000보

✅ 현실적인 데이터 (공감받음)
   - 비타민 D 부족, B1 부족 (한국 만성질환자 흔한 패턴)
   - 평균 4,500보 (실제 50대 남성 평균)
   - 가끔 야식 데이터
```

### 시연 흐름 다듬기

- 첫 1분이 가장 중요 — 차별화 메시지 명확히
- "와우" 모먼트 1~2개 (예: 사진 → 즉시 분석 → 5종 출력 자동 표시)
- 마지막에 "다음 단계" 제시 (Phase 5 로드맵 1~2 키워드)

### 백업 영상의 활용

```
시연 중 네트워크 장애 발생 시:
  "지금 네트워크 상태가 좋지 않은 듯한데,
   시연 영상으로 빠르게 보여드리겠습니다."
  → 미리 녹화한 영상 재생 (라이브 시연 + 영상 = 100% 커버)
```

---

## 🚫 이 작업에서 하지 말 것

- ❌ 의료적 진단 표현 시연 ("당뇨가 의심됩니다")
- ❌ 효능 단정 ("이 영양제 먹으면 100% 좋아짐")
- ❌ 라이브 시연 강행 (백업 영상 없이) — 위험
- ❌ 페르소나 데이터에 실제 환자 정보 사용

---

## 🔗 관련 문서

- [`/docs/02-personas-and-scenarios.md`](../02-personas-and-scenarios.md) — 페르소나 정의
- [`/docs/04-success-metrics-and-differentiation.md`](../04-success-metrics-and-differentiation.md) — 차별화
- [`/docs/10-compliance-checklist.md`](../10-compliance-checklist.md) — 시연 시 컴플라이언스
- 다음: [`23-presentation-deck.md`](./23-presentation-deck.md)
