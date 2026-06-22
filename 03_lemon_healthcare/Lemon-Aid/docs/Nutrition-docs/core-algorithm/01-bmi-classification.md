# 01. BMI 분류 알고리즘 평가 및 수정안

> 본 문서는 Lemon-Aid 헬스케어 프로젝트의 BMI 분류 알고리즘(`07-core-algorithm.md`)을 공식 가이드라인과 학술 자료에 근거하여 평가하고, 우선순위가 있는 수정안을 제시합니다.
> 작성일: 2026-05-26 · 작성 기준: 한국어, 의학적 표현(진단/치료) 회피, 출처 명시

---

## 1. 현재 구현 요약

Lemon-Aid의 `07-core-algorithm.md`는 한국·아시아인 기준의 BMI 5단계 분류를 사용합니다.

| 구간 | BMI (kg/m²) | 라벨 |
|------|-------------|------|
| 저체중 | < 18.5 | `underweight` |
| 정상 | 18.5 ~ 22.9 | `normal` |
| 과체중 | 23.0 ~ 24.9 | `overweight` |
| 비만 1단계 | 25.0 ~ 29.9 | `obese_1` |
| 비만 2단계 | ≥ 30.0 | `obese_2` |

**의사 코드 (현재)**:

```python
def classify_bmi(weight_kg: float, height_m: float) -> str:
    bmi = weight_kg / (height_m ** 2)
    if bmi < 18.5:
        return "underweight"
    if bmi < 23.0:
        return "normal"
    if bmi < 25.0:
        return "overweight"
    if bmi < 30.0:
        return "obese_1"
    return "obese_2"
```

**즉시 식별되는 한계**:
- BMI ≥ 35.0 의 **3단계(고도) 비만**이 별도 라벨로 분리되어 있지 않음 — 대한비만학회(KSSO) 2022 진료지침과 불일치.
- WHO 표준 분류(서구권)와의 옵션 분기가 없음 — 글로벌 사용자/외국인 대응 불가.
- 허리둘레(WC), 허리-신장비(WHtR), 체지방률 같은 **보완 지표가 부재**.
- 사르코페니아 비만(근감소성 비만)과 노인 obesity paradox 가 알고리즘에 반영되지 않음.
- 만성질환자(당뇨·고혈압·CKD)에 대한 더 엄격한 BMI 목표 구간이 없음.

---

## 2. 논문·공식 자료 근거

### 2.1 WHO Expert Consultation 2004 (Lancet)

- **문헌**: WHO Expert Consultation. "Appropriate body-mass index for Asian populations and its implications for policy and intervention strategies." *Lancet*. 2004;363(9403):157-163.
- **DOI**: 10.1016/S0140-6736(03)15268-3 · **PMID**: 14726171

**핵심 결론**:
1. 아시아인은 동일한 BMI에서 서구인보다 체지방률이 높고, **BMI 25 미만에서도 제2형 당뇨·심혈관질환의 위험이 유의하게 증가**한다.
2. 그러나 아시아 국가 간 편차가 커서 "모든 아시아인에 단일한 컷오프"를 제시하기 어렵다고 판단.
3. **WHO 표준 BMI 분류(<18.5 / 18.5–24.9 / 25–29.9 / ≥30)는 국제 비교를 위해 유지**하되, 공중보건 행동 지점(public health action points)으로 **23.0, 27.5, 32.5, 37.5 kg/m²**를 추가 권고.
4. 각국이 자국 데이터를 근거로 23 또는 25 중 어디를 "과체중" 진입선으로 쓸지 결정하도록 함.

> 즉, 23/27.5 는 "아시아인용 새 표준"이 아니라 **추가 위험 평가점**이라는 점이 중요. Lemon-Aid의 23.0 컷오프 사용은 KSSO·아시아·태평양 기준에 부합하지만, "WHO 공식 표준 분류"라고 표기하면 오해의 소지가 있음.

### 2.2 KSSO 한국인 비만 진료지침 (2022, 8판)

- **문헌**: Haam J-H, et al. "Diagnosis of Obesity: 2022 Update of Clinical Practice Guidelines for Obesity by the Korean Society for the Study of Obesity." *J Obes Metab Syndr*. 2023;32(2):121-129.
- **DOI**: 10.7570/jomes23031 · **PMID**: 37386771
- 동반 문헌: Kim B-Y, et al. "Evaluation and Treatment of Obesity and Its Comorbidities: 2022 Update…". *J Obes Metab Syndr*. 2023;32(1):1-24. DOI: 10.7570/jomes23016

**KSSO 2022 BMI 분류**:

| 구간 | BMI (kg/m²) |
|------|-------------|
| 저체중 | < 18.5 |
| 정상 | 18.5 ~ 22.9 |
| 비만 전 단계(과체중) | 23.0 ~ 24.9 |
| 비만 1단계 | 25.0 ~ 29.9 |
| 비만 2단계 | 30.0 ~ 34.9 |
| **비만 3단계(고도 비만)** | **≥ 35.0** |

**복부비만 기준(허리둘레)**: 남성 ≥ 90 cm, 여성 ≥ 85 cm.

**근거 데이터**:
- 국민건강보험공단 2009–2015 자료에서 BMI 23–25 구간부터 제2형 당뇨, 고혈압, 이상지질혈증 위험이 선형 증가.
- KSSO는 **사망률(mortality)이 아닌 동반질환 발생률(morbidity)**을 기준으로 컷오프를 설정. → 고령자 obesity paradox 와 충돌하는 부분을 의식한 선택.

**보완 지표 권고**:
- 허리둘레는 BMI 와 함께 측정해야 함(특히 저근육량 환자에서 BMI 만으로는 위험 과소평가됨).
- 체지방률: **남성 ≥ 26%, 여성 ≥ 36%** 를 비만 동반 심혈관 위험 참고치로 제시(임상 적용 한계 명시).

### 2.3 WHO 표준 vs Asia-Pacific 비교 표

| 구간 | WHO 국제 표준 (2000) | WHO Asia-Pacific / IDI-WPRO (2000) | KSSO 2022 (한국) |
|------|----------------------|------------------------------------|------------------|
| 저체중 | < 18.5 | < 18.5 | < 18.5 |
| 정상 | 18.5 ~ 24.9 | 18.5 ~ 22.9 | 18.5 ~ 22.9 |
| 과체중 / 비만전단계 | 25.0 ~ 29.9 | 23.0 ~ 24.9 | 23.0 ~ 24.9 |
| 비만 1단계 | 30.0 ~ 34.9 | 25.0 ~ 29.9 | 25.0 ~ 29.9 |
| 비만 2단계 | 35.0 ~ 39.9 | ≥ 30.0 | 30.0 ~ 34.9 |
| 비만 3단계(고도) | ≥ 40.0 | (분류 없음) | **≥ 35.0** |

> 참고: WHO Asia-Pacific 분류는 IASO/IOTF/WPRO (2000)의 *The Asia-Pacific Perspective: Redefining Obesity and Its Treatment* 에서 정의됨. KSSO 는 이를 토대로 "비만 3단계(≥35)"를 추가했다는 점에서 차이.

### 2.4 BMI의 한계

BMI 는 키 대비 체중만 측정하므로 다음 상황에서 위험을 잘못 추정합니다.

1. **체지방률 vs BMI 불일치**: 같은 BMI 라도 아시아인이 서구인보다 체지방률이 약 3–5%p 높음 (WHO 2004, Deurenberg 2002, Obes Rev). 운동선수·근육량이 많은 남성은 BMI 가 과체중·비만으로 분류되지만 체지방률은 낮음.
2. **사르코페니아 비만(Sarcopenic obesity)**: 근감소와 비만이 공존하는 상태. BMI 가 정상 범위여도 근육량이 감소하면 신체기능 저하·낙상·사망률 증가.
   - 정의: ESPEN & EASO Consensus 2022 (Donini LM, et al. *Clin Nutr*. 2022;41(4):990-1000. DOI: 10.1016/j.clnu.2021.11.014) — 핸드그립 약화 + 골격근량 감소(ASM/체중) + 체지방률 증가의 3요소.
   - 한국 노인 유병률: 정의에 따라 6–48%로 큰 편차 (Kim TN, et al. *J Korean Med Sci*. 2012;27(7):748-754. DOI: 10.3346/jkms.2012.27.7.748).
3. **고령자 obesity paradox**: 한국 코호트(Yi SW, et al. *PLoS One*. 2015;10(10):e0139924, DOI: 10.1371/journal.pone.0139924)에서 65세 이상 또는 만성질환자에서 **BMI 25.0–26.4 가 사망률 최저점**으로 관찰. 즉, 노인에게 "비만 1단계"를 무조건 위험으로 표시하면 부적절.
4. **임신·소아·청소년**: 별도 기준 사용(WHO Growth Standard, 2007년 한국 소아청소년 신체발육표준치 등). 본 알고리즘은 성인 전용임을 명시해야 함.

### 2.5 보완 지표

| 지표 | 핵심 컷오프 | 강점 | 근거 |
|------|-------------|------|------|
| 허리둘레(WC) | 남 ≥90 cm / 여 ≥85 cm (KSSO) | 내장지방·심대사 위험 반영 | KSSO 2022 |
| WHtR (허리/키) | **≥ 0.5** (전 인구 공통, 아시아 일부 0.48 권고) | 키 보정으로 인종·성별 영향 적음; BMI 보다 심대사 위험 예측력 우수(메타분석) | Ashwell M, et al. *Obes Rev*. 2012;13(3):275-286. DOI: 10.1111/j.1467-789X.2011.00952.x · Browning LM, et al. *Nutr Res Rev*. 2010;23(2):247-269. DOI: 10.1017/S0954422410000144 |
| 체지방률(BF%) | 남 ≥26%, 여 ≥36% (KSSO 참고치) | 근육량 차이 보정 | KSSO 2022 |
| 핸드그립 근력 | 남 <28 kg, 여 <18 kg (AWGS 2019) | 사르코페니아 동반 평가 | Chen LK, et al. *J Am Med Dir Assoc*. 2020;21(3):300-307.e2. DOI: 10.1016/j.jamda.2019.12.012 |

> Lemon-Aid 가 사용자에게 "키·체중"만 입력받는 MVP 단계에서도, **WHtR 만큼은 허리둘레 1개 입력만 추가하면 즉시 산출 가능**하다는 점이 중요.

---

## 3. 평가

### 3.1 현재 알고리즘의 강점

- **KSSO 2022 1–2단계 컷오프(23/25/30)와 정확히 일치** — 한국인 대상 정상~중등도 비만 분류에 적합.
- 단순한 5단계 라벨로 UI/UX 가 깔끔하며, 한국 국가건강검진(KDCA·국가건강정보포털)에서 일반인이 접하는 표현과 호환.
- 분기 로직이 명확해 단위 테스트가 쉬움(`< 18.5 / < 23 / < 25 / < 30` 4개 비교).

### 3.2 개선이 필요한 영역

| # | 항목 | 심각도 | 근거 |
|---|------|--------|------|
| 1 | **비만 3단계(≥35.0) 누락** — KSSO·서울대병원·KDCA 모두 분리 | 높음 | KSSO 2022 (DOI: 10.7570/jomes23031) |
| 2 | WHO 표준(서구권) 분기 옵션 없음 — 외국인·여행자 대응 불가 | 중간 | WHO/Lancet 2004 |
| 3 | WHtR 등 보완 지표 부재 — 키·체중만으로는 내장비만 식별 불가 | 높음 | Ashwell 2012 |
| 4 | 사르코페니아 비만 미반영 — 노인층에서 BMI=정상이어도 고위험 누락 | 중간 | ESPEN/EASO 2022 |
| 5 | 만성질환자(당뇨·고혈압·CKD)에 더 엄격한 권장 범위 미적용 | 높음 | Yi SW 2015, KSSO 2022 |
| 6 | 고령자 obesity paradox 미반영 — 65+ 사용자에게 동일 기준 적용 시 오해 유발 | 중간 | Yi SW 2015, Kim YH 2018 |
| 7 | 라벨이 한국어/영어 혼재 가능성 — `obese_1`, `obese_2` 가 KSSO 의 "비만 1단계"와 매핑되지만 `severely_obese` 가 없음 | 낮음 | — |

---

## 4. 수정 권고

### 4.1 우선 수정 (즉시 반영 가능, MVP 영향 최소)

1. **비만 3단계 추가**: `obese_3` (≥35.0) 분리 → KSSO 2022 와 라벨 1:1 매칭.
2. **지역 옵션 분기**: `region: 'asia_kr' | 'who_standard'` 파라미터 추가, 기본값 `'asia_kr'`.
3. **출처 표기**: 결과 객체에 `criteria_source: 'KSSO_2022'` 같은 메타 필드 포함 → 사용자 신뢰도 및 추후 가이드라인 업데이트 추적 가능.
4. **65세 이상 안내문**: 분류 결과와 별도로 `note` 필드에 "고령자는 BMI 25–27 구간이 사망률 최저로 보고됨(Yi SW 2015). 단순 BMI 만으로 판단하지 마세요." 추가.

### 4.2 Phase 2 권고 (추가 입력 필요)

1. **WHtR 보완 지표** (허리둘레 입력 추가 시):
   - 산출: `WHtR = waist_cm / height_cm`
   - 컷오프: `≥ 0.5` → `central_obesity = True`
   - BMI 가 정상이어도 WHtR ≥ 0.5 면 "정상 체중·복부 비만 위험" 메시지.
2. **체지방률 보정** (인바디 등 입력 시):
   - 남 ≥26% / 여 ≥36% 면 BMI 무관하게 "체지방 과다" 플래그.
   - BMI 가 비만이어도 BF% 가 정상이면 "근육량으로 인한 BMI 상승 가능성" 플래그(운동선수 케이스).
3. **사르코페니아 의심 플래그**: 65세 이상 + BMI 정상 + 핸드그립 약화(남<28kg, 여<18kg) → `sarcopenic_obesity_suspected = True`.
4. **만성질환자 분기**: 별도 섹션 5 참조.

### 4.3 수정된 의사 코드 (Python)

```python
from dataclasses import dataclass, field
from typing import Literal, Optional

Region = Literal["asia_kr", "who_standard"]
BMICategory = Literal[
    "underweight", "normal", "overweight",
    "obese_1", "obese_2", "obese_3"
]

@dataclass
class BMIResult:
    bmi: float
    category: BMICategory
    region: Region
    criteria_source: str
    notes: list[str] = field(default_factory=list)
    central_obesity: Optional[bool] = None         # WHtR 기반
    body_fat_flag: Optional[str] = None            # 'high' | 'normal' | None
    sarcopenic_obesity_suspected: Optional[bool] = None


# ── 컷오프 테이블 (출처 명시) ─────────────────────────────
_CUTOFFS = {
    "asia_kr": {  # KSSO 2022, DOI: 10.7570/jomes23031
        "underweight": 18.5,
        "normal":      23.0,
        "overweight":  25.0,
        "obese_1":     30.0,
        "obese_2":     35.0,
        # ≥ 35.0 → obese_3
    },
    "who_standard": {  # WHO 2000, retained by WHO Expert Consultation 2004
        "underweight": 18.5,
        "normal":      25.0,
        "overweight":  30.0,
        "obese_1":     35.0,
        "obese_2":     40.0,
        # ≥ 40.0 → obese_3
    },
}

_SOURCE = {
    "asia_kr":      "KSSO 2022 (J Obes Metab Syndr. 2023;32(2):121-129)",
    "who_standard": "WHO 2000 / Lancet 2004;363:157-163",
}


def classify_bmi(
    weight_kg: float,
    height_m: float,
    *,
    region: Region = "asia_kr",
    age: Optional[int] = None,
    sex: Optional[Literal["male", "female"]] = None,
    waist_cm: Optional[float] = None,
    body_fat_pct: Optional[float] = None,
    has_chronic_disease: bool = False,
) -> BMIResult:
    if height_m <= 0 or weight_kg <= 0:
        raise ValueError("height_m, weight_kg 는 0보다 커야 합니다.")

    bmi = round(weight_kg / (height_m ** 2), 2)
    cuts = _CUTOFFS[region]

    if bmi < cuts["underweight"]:
        category: BMICategory = "underweight"
    elif bmi < cuts["normal"]:
        category = "normal"
    elif bmi < cuts["overweight"]:
        category = "overweight"
    elif bmi < cuts["obese_1"]:
        category = "obese_1"
    elif bmi < cuts["obese_2"]:
        category = "obese_2"
    else:
        category = "obese_3"

    result = BMIResult(
        bmi=bmi,
        category=category,
        region=region,
        criteria_source=_SOURCE[region],
    )

    # ── 부가 플래그 ───────────────────────────────────────
    # 1) WHtR (허리/키)  — 컷오프 0.5
    if waist_cm is not None and height_m > 0:
        whtr = waist_cm / (height_m * 100)
        result.central_obesity = whtr >= 0.5
        if category in ("underweight", "normal") and result.central_obesity:
            result.notes.append(
                "BMI 는 정상 범위이나 허리-신장비(WHtR) ≥ 0.5 로 "
                "복부 비만 위험 신호가 있어요. (참고: Ashwell 2012)"
            )

    # 2) 체지방률 (KSSO 참고치)
    if body_fat_pct is not None and sex is not None:
        threshold = 26.0 if sex == "male" else 36.0
        if body_fat_pct >= threshold:
            result.body_fat_flag = "high"
            if category in ("underweight", "normal"):
                result.notes.append(
                    f"BMI 는 정상이나 체지방률이 높은 편이에요 "
                    f"({sex} ≥ {threshold}%). 근육량 점검을 권장합니다."
                )
        else:
            result.body_fat_flag = "normal"
            if category in ("obese_1", "obese_2", "obese_3"):
                result.notes.append(
                    "BMI 상 비만 범위이지만 체지방률은 정상이에요. "
                    "근육량이 많은 체형일 가능성이 있어요."
                )

    # 3) 65세 이상 obesity paradox 안내
    if age is not None and age >= 65 and category == "obese_1":
        result.notes.append(
            "65세 이상 한국인 코호트에서 BMI 25–27 구간이 "
            "사망률 최저로 보고된 바 있어요(Yi SW 2015). "
            "단순 BMI 만으로 판단하지 않는 게 좋아요."
        )

    # 4) 만성질환 보유자에게 더 엄격한 권장 범위 안내
    if has_chronic_disease and category == "overweight":
        result.notes.append(
            "당뇨·고혈압 등 만성질환이 있는 경우 "
            "BMI 23 미만 유지가 더 유익할 수 있어요(KSSO 2022)."
        )

    # 5) 사르코페니아 비만 의심 (정보 부족 시 None)
    if age is not None and age >= 65 and category == "normal" \
            and body_fat_pct is not None and result.body_fat_flag == "high":
        result.sarcopenic_obesity_suspected = True
        result.notes.append(
            "고령·BMI 정상·체지방률 높음 패턴은 "
            "근감소성 비만 가능성을 시사해요(ESPEN/EASO 2022). "
            "악력·근육량 측정을 권장합니다."
        )

    return result
```

---

## 5. 만성질환자 분기 (사용자 핵심 질문)

> **"왜 만성질환자와 일반 사용자를 BMI 기준에서 분리해야 하는가?"**

### 5.1 의학적 근거

1. **만성질환자에서 BMI–위험 곡선이 일반인보다 좌측·하방으로 이동**
   - Yi SW, et al. (*PLoS One*. 2015;10(10):e0139924) — 한국 153,484명 7.9년 추적. 일반 인구에서는 BMI 25–26.4 가 사망률 최저였지만, **당뇨·고혈압·CKD 보유군에서도 BMI 25–29.9 가 사망률 측면에선 보호적(obesity paradox)**. 다만 합병증(망막증·신증·심혈관 이벤트) 발생률은 BMI 23 이상부터 선형 증가.
   - KSSO 2022 (DOI: 10.7570/jomes23031) — 동반질환 발생률 기준으로 컷오프를 정했음을 명시. 즉, "BMI 23–25 라도 당뇨 등 동반질환이 있다면 적극적인 체중 관리 권고".

2. **사르코페니아 비만의 임상적 중요도**
   - Donini LM, et al. ESPEN-EASO Consensus 2022 (DOI: 10.1016/j.clnu.2021.11.014) — BMI 정상 + 근육량 감소 + 체지방 증가 = 사망·기능 저하 위험이 단순 비만보다 큼.
   - Kim TN, et al. (*J Korean Med Sci*. 2012;27(7):748) — 한국 노인 사르코페니아 비만 유병률 6.1%(남)·7.3%(여); 정의에 따라 최대 48% 보고.

3. **고령자 obesity paradox**
   - 한국 강화 코호트(*PLoS One*. 2015) — 농촌 고령자에서 남 BMI 21.0–27.4 / 여 20.0–27.4 가 사망률 최저.
   - Living Profiles of Older People 추적연구도 유사 패턴 확인.
   - 시사점: **65세 이상에 "비만 1단계 = 위험"이라는 단순 메시지는 부적절**. "체중 감량보다 근육량 유지가 우선" 안내 필요.

4. **당뇨·고혈압 환자의 권장 BMI 범위**
   - KSSO 2022 동반질환 챕터 — 제2형 당뇨/고혈압 환자는 BMI 23 미만 유지 또는 **체중의 5–10% 감량**이 1차 권고.
   - ADA Standards of Care 2024 (DOI: 10.2337/dc24-S008) — 과체중·비만 당뇨 환자에게 ≥5% 체중 감량 권고; 아시아인은 BMI 23 이상부터 위험군.

### 5.2 Lemon-Aid 권고 분기 로직

```
사용자 프로필
├─ 일반 성인 (18~64세, 만성질환 없음)
│   └─ KSSO 2022 기본 5+1 단계 분류 그대로 사용
│
├─ 만성질환 보유자 (당뇨·고혈압·이상지질혈증·CKD 등)
│   ├─ BMI 23.0–24.9 → "관리 권장 구간" (일반인은 단순 과체중이지만 위험 메시지 강화)
│   ├─ BMI ≥ 25.0  → "체중 5–10% 감량 권장" 메시지 우선
│   └─ 허리둘레·WHtR 동시 측정 권고
│
├─ 65세 이상
│   ├─ BMI < 21 → "저체중 위험" 강조 (영양·근감소)
│   ├─ BMI 21–27 → "양호 구간" (obesity paradox 반영)
│   ├─ BMI ≥ 28 → 일반 기준대로 표시하되 "근육량 유지하며 천천히 감량" 메시지
│   └─ 가능하면 핸드그립·종아리둘레 추가 측정 안내
│
└─ 임신부 / 19세 미만
    └─ 본 알고리즘 적용 제외 — 별도 라우팅 필요
```

### 5.3 UI/UX 시사점

- 사용자 온보딩 단계에서 **연령, 만성질환 보유 여부**를 1회 입력받으면 위 분기를 자동 적용 가능.
- 결과 화면은 **(1) 숫자 BMI, (2) 라벨, (3) 맥락 메시지(notes)** 의 3단 구성으로 분리하는 것을 권장. 라벨만으로는 "비만 1단계"가 고령자에게 위험을 과장할 수 있음.
- 의학적 단어("진단", "처방", "치료")는 회피하고, "참고", "관리 권장", "전문가 상담 권유" 같은 비임상 표현을 사용.

---

## 6. 근거 수준 재평가 (A / B / C)

> A = 다수 무작위/대규모 코호트 + 공식 가이드라인 일치, B = 단일 대형 코호트 또는 합의 권고, C = 소규모/관찰 연구 근거.

| 항목 | 근거 수준 | 비고 |
|------|-----------|------|
| KSSO 2022 BMI 5+1 단계 (18.5/23/25/30/35) | **A** | 국가 가이드라인 + NHIS 대규모 코호트 |
| WHO 표준 분류(서구권) 옵션 분기 | **A** | WHO 공식 분류 |
| 허리둘레 보완 측정 (남 90 / 여 85) | **A** | KSSO 2022 공식 채택 |
| WHtR ≥ 0.5 컷오프 | **B** | 14개국 메타분석(Ashwell 2012); 국내 가이드라인 미채택이나 학술적 합의 강함 |
| 체지방률 남 ≥26% / 여 ≥36% | **B** | KSSO "참고치"로 제시, 임상 적용 제한 명시 |
| 65세 이상 obesity paradox 안내 | **B** | 다중 한국 코호트 일치, 가이드라인은 미반영 |
| 사르코페니아 비만 플래그 | **B** | ESPEN/EASO 2022 합의는 강하나 일차 진료지침 채택은 진행 중 |
| 만성질환자 BMI 23 미만 권고 | **B** | KSSO 동반질환 챕터 + 한국 코호트 |
| 임신부/소아 제외 | **A** | 모든 가이드라인이 별도 기준 사용 |

---

## 7. 참고 문헌

1. WHO Expert Consultation. Appropriate body-mass index for Asian populations and its implications for policy and intervention strategies. *Lancet*. 2004;363(9403):157-163. DOI: [10.1016/S0140-6736(03)15268-3](https://doi.org/10.1016/S0140-6736(03)15268-3) · PMID: 14726171.
2. Haam J-H, Kim B-Y, Kang JH, et al. Diagnosis of Obesity: 2022 Update of Clinical Practice Guidelines for Obesity by the Korean Society for the Study of Obesity. *J Obes Metab Syndr*. 2023;32(2):121-129. DOI: [10.7570/jomes23031](https://doi.org/10.7570/jomes23031) · PMC: [PMC10327686](https://pmc.ncbi.nlm.nih.gov/articles/PMC10327686/).
3. Kim B-Y, Kang SM, Kang JH, et al. Evaluation and Treatment of Obesity and Its Comorbidities: 2022 Update of Clinical Practice Guidelines for Obesity by the Korean Society for the Study of Obesity. *J Obes Metab Syndr*. 2023;32(1):1-24. DOI: [10.7570/jomes23016](https://doi.org/10.7570/jomes23016).
4. 대한비만학회. 『비만 진료지침 2022 (8판) 요약본』. [PDF](https://general.kosso.or.kr/html/user/core/view/reaction/main/kosso/inc/data/guideline2022_vol8.pdf).
5. 질병관리청 국가건강정보포털. "비만". [https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=5292](https://health.kdca.go.kr/healthinfo/biz/health/gnrlzHealthInfo/gnrlzHealthInfo/gnrlzHealthInfoView.do?cntnts_sn=5292).
6. International Diabetes Institute / WHO Western Pacific Region / IASO / IOTF. *The Asia-Pacific Perspective: Redefining Obesity and Its Treatment*. Health Communications Australia, 2000.
7. Yi SW, Ohrr H, Shin SA, Yi JJ. Body Mass Index and Mortality in the General Population and in Subjects with Chronic Disease in Korea: A Nationwide Cohort Study (2002-2010). *PLoS One*. 2015;10(10):e0139924. DOI: [10.1371/journal.pone.0139924](https://doi.org/10.1371/journal.pone.0139924) · PMC: [PMC4604086](https://pmc.ncbi.nlm.nih.gov/articles/PMC4604086/).
8. Kim YH, Kim SM, Han KD, et al. Association between body mass index and mortality in the Korean elderly: A nationwide cohort study. *PLoS One*. 2018;13(11):e0207508. DOI: [10.1371/journal.pone.0207508](https://doi.org/10.1371/journal.pone.0207508).
9. Ashwell M, Gunn P, Gibson S. Waist-to-height ratio is a better screening tool than waist circumference and BMI for adult cardiometabolic risk factors: systematic review and meta-analysis. *Obes Rev*. 2012;13(3):275-286. DOI: [10.1111/j.1467-789X.2011.00952.x](https://doi.org/10.1111/j.1467-789X.2011.00952.x).
10. Browning LM, Hsieh SD, Ashwell M. A systematic review of waist-to-height ratio as a screening tool for the prediction of cardiovascular disease and diabetes: 0·5 could be a suitable global boundary value. *Nutr Res Rev*. 2010;23(2):247-269. DOI: [10.1017/S0954422410000144](https://doi.org/10.1017/S0954422410000144).
11. Donini LM, Busetto L, Bischoff SC, et al. Definition and diagnostic criteria for sarcopenic obesity: ESPEN and EASO consensus statement. *Clin Nutr*. 2022;41(4):990-1000. DOI: [10.1016/j.clnu.2021.11.014](https://doi.org/10.1016/j.clnu.2021.11.014) · PMC: [PMC9210010](https://pmc.ncbi.nlm.nih.gov/articles/PMC9210010/).
12. Kim TN, Yang SJ, Yoo HJ, et al. Prevalence Rate and Associated Factors of Sarcopenic Obesity in Korean Elderly Population. *J Korean Med Sci*. 2012;27(7):748-754. DOI: [10.3346/jkms.2012.27.7.748](https://doi.org/10.3346/jkms.2012.27.7.748).
13. Chen LK, Woo J, Assantachai P, et al. Asian Working Group for Sarcopenia: 2019 Consensus Update on Sarcopenia Diagnosis and Treatment. *J Am Med Dir Assoc*. 2020;21(3):300-307.e2. DOI: [10.1016/j.jamda.2019.12.012](https://doi.org/10.1016/j.jamda.2019.12.012).
14. Deurenberg P, Deurenberg-Yap M, Guricci S. Asians are different from Caucasians and from each other in their body mass index/body fat percent relationship. *Obes Rev*. 2002;3(3):141-146. DOI: [10.1046/j.1467-789X.2002.00065.x](https://doi.org/10.1046/j.1467-789X.2002.00065.x).
15. American Diabetes Association. Obesity and Weight Management for the Prevention and Treatment of Type 2 Diabetes: Standards of Care in Diabetes—2024. *Diabetes Care*. 2024;47(Supplement_1):S145-S157. DOI: [10.2337/dc24-S008](https://doi.org/10.2337/dc24-S008).

---

*문서 책임 범위 안내: 본 문서는 알고리즘 설계 평가용 기술 자료로, 의료적 진단·처방·치료를 대체하지 않습니다. 실제 사용자 적용 시 의료 전문가의 자문을 받으세요.*
