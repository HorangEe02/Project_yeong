# 09. 데이터·API 카탈로그 (Data & API Catalog)

> **문서 정보**  
> 버전: v1.0 | 작성일: 2026-05-03 | 상태: 초안 | 작성자: 경북대학교 AI/빅데이터 전문가 양성 과정 — TBD팀

---

## 📋 한 줄 요약

> 본 프로젝트가 사용하는 **공공 영양 데이터 5종 + AI 데이터셋 1종 + 외부 API 4종 + 모바일 헬스 SDK 2종** 의 출처·라이선스·비용·인증절차·호출 예시·사용 제약을 통합 정리. 각 자원이 07번 알고리즘 어디에서 사용되는지 명확히 매핑.

---

## 목차
- [1. 데이터·API 전체 지도](#1-데이터api-전체-지도)
- [2. 알고리즘 ↔ 데이터 매핑](#2-알고리즘--데이터-매핑)
- [3. 공공 영양 데이터](#3-공공-영양-데이터)
- [4. AI 학습용 데이터셋](#4-ai-학습용-데이터셋)
- [5. 외부 API](#5-외부-api)
- [6. 모바일 헬스 데이터 SDK](#6-모바일-헬스-데이터-sdk)
- [7. 향후 통합 가능성](#7-향후-통합-가능성)
- [8. 데이터 거버넌스](#8-데이터-거버넌스)
- [9. 비용 추정 통합](#9-비용-추정-통합)

---

## 1. 데이터·API 전체 지도

```
┌───────────────────────────────────────────────────────────────────┐
│                  📊 데이터 소스 카테고리 (12종)                    │
└───────────────────────────────────────────────────────────────────┘

🔵 공공 영양 데이터 (5종)
  ① KDRIs 2020 (한국영양학회)         — 권장 섭취량 기준
  ② 식약처 식품영양성분 Open API      — 식품 영양 정보
  ③ 식약처 건강기능식품 원료 DB        — 영양제 기능성 정보
  ④ 농진청 국가표준식품성분표          — 한식·전통식품 보강
  ⑤ 식품안전나라                       — 검수용 웹 DB

🟡 AI 학습용 데이터셋 (1종)
  ⑥ AI Hub 음식 이미지 데이터셋        — Phase 3 식단 인식

🟣 외부 API (4종)
  ⑦ Google Cloud Vision API           — OCR (주력)
  ⑧ Naver CLOVA OCR                   — OCR (백업)
  ⑨ Anthropic Claude API              — LLM (주력)
  ⑩ OpenAI GPT API                    — LLM (백업)

🟢 모바일 헬스 SDK (2종)
  ⑪ Apple HealthKit                   — iOS 헬스 데이터
  ⑫ Google Health Connect             — Android 헬스 데이터

🔴 향후 통합 (2종, Year 2~3)
  • LDB-E 마이데이터 (레몬헬스케어)    — 의료기관 연계
  • 건강정보 고속도로 (보건복지부)      — 마이데이터 표준
```

---

## 2. 알고리즘 ↔ 데이터 매핑

각 데이터·API가 07번 문서의 어떤 알고리즘에서 사용되는지 명시.

| 알고리즘 | 사용 데이터·API |
|---------|----------------|
| ② v1 권장걸음수 | (계산만, 외부 데이터 없음) |
| ③ v2 심박수 가중 | ⑪ HealthKit / ⑫ Health Connect |
| ④ v3 백분위 보너스 | (자체 사용자 DB) |
| ⑤ v4 만성질환 가중 | (사용자 입력) |
| ⑥ BMR / ⑦ TDEE / ⑧ 7-step | ⑪⑫ (걸음수) |
| **권장 섭취량 룩업** | ① KDRIs |
| **부족 영양소 진단 ⓒ** | ① KDRIs (RDI/UL) |
| **식단 변환 ⓑ** | ② 식약처 API + ④ 농진청 + ⑥ AI Hub (Phase 3) + ⑨ Claude |
| **영양제 OCR 파싱 ⓐ** | ⑦ Cloud Vision + ⑨ Claude + ③ 식약처 건기식 DB |
| **목적별 분석 ⓓ** | ① KDRIs + ③ 식약처 (기능성 인정 원료) |
| **식단 이미지 인식 (Phase 3)** | ⑥ AI Hub + ⑨ Claude (Vision) |

---

## 3. 공공 영양 데이터

### 3.1 KDRIs (한국인 영양소 섭취기준)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영 기관** | 한국영양학회 + 보건복지부 |
| **공식 명칭** | Dietary Reference Intakes for Koreans |
| **최신 버전** | KDRIs 2020 (2025년 개정 발표 예정) |
| **URL** | https://www.kns.or.kr (한국영양학회) |
| **라이선스** | 공공저작물 자유이용 |
| **API 제공** | ❌ 없음 — PDF 보고서 형식 |
| **비용** | 무료 |

#### 데이터 구성

| 영양소 카테고리 | 종류 |
|---------------|------|
| 에너지·거대영양소 | 열량, 탄수화물, 당류, 지방, 트랜스지방, 포화지방, 콜레스테롤, 단백질 |
| 식이섬유·수분·특수지방 | 식이섬유, 수분, 불포화지방, 아미노산 |
| 미네랄 7종 | 나트륨, 칼슘, 철, 칼륨, 인, 마그네슘, 아연 |
| 지용성 비타민 4종 | 비타민A, D, E, K |
| 수용성 비타민 7종 | 비타민C, B1, B2, B3, B6, B12, 엽산 |

연령·성별별 분류:
- 성별: 남 / 여
- 연령: 영유아 ~ 75세 이상 (12개 구간)
- 임신부 / 수유부 별도

#### 본 프로젝트 활용

```
07번 알고리즘 ⓒ (부족 영양소 진단) → KDRIs 룩업이 필수
07번 알고리즘 ⓓ (목적별 분석) → 비타민A·B군 등 권장량 인용
07번 Ch.02 영양 기준 → 30종 영양소 기준값 그대로 사용
```

#### 처리 절차

```
1. KDRIs 2020 PDF 다운로드 (한국영양학회 자료실)
2. 표 영역 OCR 또는 수동 전사
3. CSV/JSON 정형화 (스키마 예시 아래)
4. PostgreSQL 시드 데이터로 import
```

#### 데이터 스키마 예시

```json
{
  "version": "KDRIs-2020",
  "nutrients": [
    {
      "code": "vitamin_c_mg",
      "name_ko": "비타민 C",
      "name_en": "Vitamin C",
      "unit": "mg",
      "values": [
        {"sex": "male", "age_min": 19, "age_max": 29, "rda": 100, "ul": 2000},
        {"sex": "female", "age_min": 19, "age_max": 29, "rda": 100, "ul": 2000},
        {"sex": "female", "age_pregnant": true, "rda": 110, "ul": 2000},
        {"sex": "female", "age_lactating": true, "rda": 140, "ul": 2000}
      ]
    }
  ]
}
```

#### 주의사항

- ⚠️ **공식 API가 없으므로 PDF → CSV 디지털화 작업 필수** (Phase 0 산출물)
- ⚠️ 2025년 개정판 발표 시 즉시 갱신 정책 필요 (06번 문서 참조)
- ⚠️ 일부 영양소는 RDA가 아닌 AI(충분섭취량) 또는 EAR로만 제시됨

---

### 3.2 식약처 식품영양성분 Open API

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영 기관** | 식품의약품안전처 / 공공데이터포털 운영 |
| **URL** | https://www.data.go.kr/data/15127578 |
| **라이선스** | 공공데이터 (활용신청 후 이용) |
| **인증** | 공공데이터포털 회원가입 → API 키 발급 |
| **비용** | 무료 (1일 호출량 제한 있음) |
| **갱신 주기** | 분기 갱신 |

#### 주요 필드

```
식품코드 / 식품명 / 분류 / 제조사
1회 제공량 (g, ml)
에너지(kcal), 탄수화물(g), 단백질(g), 지방(g)
나트륨(mg), 콜레스테롤(mg)
비타민 군 (A, B1, B2, C, ...)
미네랄 (칼슘, 철, ...)
```

#### 호출 예시

```python
import httpx

API_KEY = os.environ["MFDS_API_KEY"]
BASE_URL = "http://openapi.foodsafetykorea.go.kr/api"

async def search_food(food_name: str, limit: int = 10):
    """식품명으로 영양 정보 검색"""
    url = f"{BASE_URL}/{API_KEY}/I2790/json/1/{limit}/DESC_KOR={food_name}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        data = response.json()
        return data["I2790"]["row"]

# 사용 예: 김치찌개 영양 정보
results = await search_food("김치찌개")
# [{"DESC_KOR": "김치찌개", "NUTR_CONT1": "65.4", ...}]
```

#### 본 프로젝트 활용

```
알고리즘 ⓑ (식단 변환) → 핵심 데이터 소스
- 텍스트 식단 → 영양소 변환 시 호출
- Phase 2~3 모두 사용
```

#### 사용 제약

- ⚠️ 1일 1만 회 호출 제한 (기본) → Redis 캐싱으로 대응
- ⚠️ 가공식품 위주, 자연식품 일부 누락 → 농진청 DB와 병합 권장
- ⚠️ 한식·전통식품은 부분적으로만 등록 → 한국 음식 인식엔 부족

---

### 3.3 식약처 건강기능식품 원료 DB

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영 기관** | 식품의약품안전처 |
| **URL** | https://www.foodsafetykorea.go.kr/portal/healthyfoodlife |
| **라이선스** | 공공데이터 |
| **API 제공** | △ 부분 (대부분은 웹 검색) |
| **비용** | 무료 |

#### 주요 데이터

- 기능성 인정 원료 (예: 루테인, 밀크씨슬, 코엔자임Q10, ...)
- 원료별 일일 섭취량 기준
- 인정된 기능성 표시 (예: "간 건강에 도움", "눈 건강에 도움")
- 주의사항 (예: 흡연자 루테인 주의)

#### 본 프로젝트 활용

```
알고리즘 ⓐ (영양제 OCR 파싱) → 매칭 단계에서 사용
알고리즘 ⓓ (목적별 분석) → 기능성 인정 원료만 추천 가능
컴플라이언스 (10번 문서) → 약사법 위반 회피
```

#### 처리 절차

```
1. 식약처 건강기능식품 원료 목록 수동 크롤링·정리
2. 원료별 권장량·기능성 매트릭스 CSV 작성
3. 알고리즘 ⓓ에서 룩업 테이블로 사용
```

---

### 3.4 농진청 국가표준식품성분표 (9개정판)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영 기관** | 농촌진흥청 국립농업과학원 |
| **URL** | https://koreanfood.rda.go.kr / data.go.kr/data/15123901 |
| **라이선스** | 공공저작물 자유이용 |
| **현재 버전** | 9개정판 (2021) |
| **비용** | 무료 (PDF + 데이터 파일) |

#### 데이터 구성

- 43개 영양소 (식약처 API보다 풍부)
- 한식·전통식품 특화 (예: 고들빼기 김치, 도라지정과)
- 약 3,000개 식품 (상시)

#### 본 프로젝트 활용

```
식약처 API의 한식 부족 부분 보강
- 김치류, 장류, 떡, 한과 등
- Phase 3 식단 이미지 인식 시 한국 음식 카테고리 보강
```

#### 주의사항

- ⚠️ 공공데이터포털 파일은 2021.12 갱신이 마지막 — **최신은 koreanfood.rda.go.kr 직접 확인**
- ⚠️ API가 아닌 파일 다운로드 형식

---

### 3.5 식품안전나라 (검수용 웹 DB)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영 기관** | 식품의약품안전처 |
| **URL** | https://www.foodsafetykorea.go.kr/fcdb |
| **API 제공** | ❌ (웹 UI만) |
| **비용** | 무료 |

#### 본 프로젝트 활용

- 식약처 API 결과 검수용
- 신규 식품 등록 확인용
- 영양사 자문 시 공식 출처 인용

---

## 4. AI 학습용 데이터셋

### 4.1 AI Hub 음식 이미지 데이터셋

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영 기관** | NIA(한국지능정보사회진흥원) AI Hub |
| **URL** | https://www.aihub.or.kr/aihubdata/data/view.do?dataSetSn=74 |
| **라이선스** | 공공저작물 + AI Hub 활용 동의 |
| **사용 신청** | AI Hub 회원가입 → 활용 신청서 제출 → 승인 (3~5일) |
| **비용** | 무료 (단, 학술·R&D 목적 명시) |

#### 데이터 구성

- 한국 음식 이미지 다수 (수십만 장)
- 카테고리별 분류 (한식·중식·일식·양식·분식·후식 등)
- 이미지 + 라벨 (식품명, 카테고리)
- 일부 데이터는 영양 정보 포함

#### 본 프로젝트 활용

```
Phase 3 (식단 이미지 인식) — 핵심 데이터
- Fine-tuning용 또는 Vision API 보강용
- 한국 음식 정확도 향상
```

#### 사용 제약

- ⚠️ 활용 신청 시 **데이터 사용 목적·재배포 금지** 동의 필수
- ⚠️ 학생 프로젝트는 학술 목적으로 신청 가능
- ⚠️ 발주처(레몬헬스케어)와 공유 시 별도 동의 필요할 수 있음
- ⚠️ 라벨 품질이 일정하지 않아 **수동 검증** 작업 필요

#### 신청 절차 (Phase 0 체크리스트)

```
☐ AI Hub 회원가입
☐ 활용 신청서 작성 (목적: AI 헬스케어 R&D, 학술 프로젝트)
☐ 지도교수 또는 학과 확인서 첨부 (요구 시)
☐ 승인 대기 (3~5 영업일)
☐ 다운로드 후 무결성 검증 (체크섬)
```

---

## 5. 외부 API

### 5.1 Google Cloud Vision API (OCR — 주력)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영사** | Google Cloud |
| **URL** | https://cloud.google.com/vision |
| **공식 문서** | https://cloud.google.com/vision/docs |
| **라이선스** | 상용 API (사용량 과금) |
| **비용** | 첫 1,000건/월 무료 → 이후 $1.50 / 1,000건 |
| **인증** | Google Cloud 계정 + Service Account JSON |

#### 사용 모드

| 모드 | 용도 | 본 프로젝트 |
|------|------|---------|
| TEXT_DETECTION | 짧은 텍스트 (간판, 표지판) | ❌ |
| **DOCUMENT_TEXT_DETECTION** | 문서·라벨 (영양제 라벨) | ✅ 채택 |
| LABEL_DETECTION | 객체 인식 | ❌ |
| OBJECT_LOCALIZATION | 객체 위치 | (선택) 영양제 영역 검출 |

#### 호출 예시

```python
from google.cloud import vision

client = vision.ImageAnnotatorClient()

with open("supplement.jpg", "rb") as image_file:
    content = image_file.read()

response = client.document_text_detection(
    image=vision.Image(content=content),
    image_context=vision.ImageContext(language_hints=["ko", "en"])
)

if response.error.message:
    raise Exception(response.error.message)

text = response.full_text_annotation.text
print(text)
```

#### 본 프로젝트 활용

```
알고리즘 ⓐ (영양제 OCR 파싱) — 1차 텍스트 추출
- Phase 2부터 핵심
- 응답 시간 800~1500ms
- 정확도 92~98% (영양제 라벨)
```

#### 인증 절차 (Phase 0 체크리스트)

```
☐ Google Cloud 계정 생성
☐ 새 프로젝트 생성 ("lemon-healthcare-poc")
☐ Cloud Vision API 활성화
☐ Service Account 생성 → JSON 키 다운로드
☐ JSON 키를 .env에 등록 (절대 commit 금지)
☐ 첫 호출 테스트 → 1,000건 무료 티어 확인
```

#### 사용 제약

- ⚠️ Service Account JSON은 절대 git에 커밋 금지
- ⚠️ 1회 호출 시 이미지 크기 ≤ 20MB
- ⚠️ 무료 티어 1,000건/월 → 초과 시 자동 과금
- ⚠️ Rate Limiting: 분당 1,800건 (충분)

---

### 5.2 Naver CLOVA OCR (백업)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영사** | Naver Cloud |
| **URL** | https://www.ncloud.com/product/aiService/ocr |
| **라이선스** | 상용 (사용량 과금) |
| **한국어 강점** | ⭐ 한국어 인식 SOTA 수준 |
| **비용** | 일정 무료 + 종량제 (약 ₩30~50/건) |

#### 본 프로젝트 활용

```
폴백(Fallback) 전략:
- Cloud Vision 정확도 < 임계치일 때 자동 호출
- 한글 영양제 라벨에서 우위
- Adapter 패턴으로 호출 (06번 참조)
```

---

### 5.3 Anthropic Claude API (LLM — 주력)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영사** | Anthropic |
| **URL** | https://docs.claude.com |
| **모델** | claude-sonnet-4-6 (균형) / claude-haiku-4-5 (빠름) / claude-opus-4-7 (최고 성능) |
| **라이선스** | 상용 API |
| **인증** | Anthropic Console → API 키 |
| **결제** | 선불 크레딧 |

#### 모델·가격 비교 (참고용)

| 모델 | 입력 가격 | 출력 가격 | 추천 사용처 |
|------|---------|---------|----------|
| claude-haiku-4-5 | 저렴 | 저렴 | 단순 파싱·캐싱 가능한 작업 |
| **claude-sonnet-4-6** | 중간 | 중간 | ⭐ **본 프로젝트 주력** |
| claude-opus-4-7 | 비쌈 | 비쌈 | 의료자문위 검토 시연용 |

> 정확한 가격은 Anthropic 공식 문서 확인 권장

#### 호출 예시 (Tool Use)

```python
from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=2048,
    tools=[{
        "name": "extract_supplement_facts",
        "description": "영양제 라벨에서 성분을 추출",
        "input_schema": {
            "type": "object",
            "properties": {
                "ingredients": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name_ko": {"type": "string"},
                            "amount": {"type": "number"},
                            "unit": {"type": "string"}
                        }
                    }
                }
            }
        }
    }],
    tool_choice={"type": "tool", "name": "extract_supplement_facts"},
    messages=[{
        "role": "user",
        "content": "OCR 결과: Vitamin C 1000mg, Vitamin D3 25mcg ..."
    }]
)
```

#### 본 프로젝트 활용

```
알고리즘 ⓐ (영양제 OCR 파싱) — 텍스트 → JSON 구조화
알고리즘 ⓑ (식단 텍스트 파싱) — "김치찌개 1그릇" → 구조화
알고리즘 ⓓ (목적별 분석) — (선택) 자연어 권고 메시지 생성
Phase 3 식단 이미지 인식 — Vision 모드 활용 가능
```

#### 인증 절차

```
☐ https://console.anthropic.com 가입
☐ API 키 발급 (.env에 저장)
☐ 결제 정보 등록 (또는 무료 크레딧 확인)
☐ 첫 호출 테스트
☐ 사용량 알림 임계치 설정 ($X 도달 시 이메일)
```

#### 사용 제약

- ⚠️ API 키는 절대 git/모바일 앱에 커밋 금지 (백엔드만)
- ⚠️ 한 번 호출당 최대 200K 토큰 입력 (영양제 라벨엔 충분)
- ⚠️ Rate Limit는 등급별로 다름

---

### 5.4 OpenAI GPT API (백업 LLM)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영사** | OpenAI |
| **URL** | https://platform.openai.com |
| **모델** | gpt-4o, gpt-4-turbo 등 |
| **라이선스** | 상용 API |

#### 본 프로젝트 활용

```
폴백 전략:
- Claude API 다운 시 자동 전환
- Adapter 패턴으로 인터페이스 동일
- 동일 프롬프트 재사용 가능
```

---

## 6. 모바일 헬스 데이터 SDK

### 6.1 Apple HealthKit (iOS)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영사** | Apple |
| **공식 문서** | https://developer.apple.com/documentation/healthkit |
| **라이선스** | Apple Developer 프로그램 가입 (연 $99) |
| **Flutter 통합** | `health` 패키지 |

#### 사용 가능 데이터

| 카테고리 | 본 프로젝트 사용 |
|---------|--------------|
| 걸음수 | ✅ 핵심 (v1~v4) |
| 심박수 | ✅ v2 가중 |
| 활동에너지 | ✅ TDEE 보조 |
| 운동 시간 | ✅ 심박 유지시간 |
| 체중 | ✅ 7-step 입력 |
| 키 | ✅ BMI 입력 |
| 수면 | △ 향후 |

#### 권한 요청

```dart
import 'package:health/health.dart';

final health = Health();

// 권한 요청
final types = [
    HealthDataType.STEPS,
    HealthDataType.HEART_RATE,
    HealthDataType.ACTIVE_ENERGY_BURNED,
    HealthDataType.WEIGHT,
];

bool granted = await health.requestAuthorization(types);

// 데이터 읽기
final now = DateTime.now();
final data = await health.getHealthDataFromTypes(
    startTime: now.subtract(Duration(days: 7)),
    endTime: now,
    types: types,
);
```

#### Info.plist 설정 (필수)

```xml
<key>NSHealthShareUsageDescription</key>
<string>건강 데이터를 분석하여 맞춤 권고를 제공합니다</string>
<key>NSHealthUpdateUsageDescription</key>
<string>건강 데이터를 기록합니다</string>
```

#### 사용 제약

- ⚠️ 임의 데이터 추가 후 측정 중단 사례 보고 (디버깅 시 주의)
- ⚠️ 백그라운드 실행은 별도 설정 (HKObserverQuery)
- ⚠️ App Store 심사 시 **건강 데이터 사용 목적** 까다롭게 검토

---

### 6.2 Google Health Connect (Android)

#### 핵심 정보

| 항목 | 내용 |
|------|------|
| **운영사** | Google (Android) |
| **공식 문서** | https://developer.android.com/health-connect |
| **라이선스** | Android 개발 표준 |
| **요구사항** | Android 13+ 권장 (이전 버전은 Health Connect 앱 별도 설치) |

#### 데이터 흐름

```
Galaxy Watch ────► Samsung Health ────► Health Connect ────► 본 앱
Mi Band     ────► Mi Fitness     ────► Health Connect ────► 본 앱
스마트폰만   ──────────────────────► Health Connect ────► 본 앱
```

#### AndroidManifest.xml 설정

```xml
<queries>
    <package android:name="com.google.android.apps.healthdata" />
    <intent>
        <action android:name="androidx.health.ACTION_SHOW_PERMISSIONS_RATIONALE" />
    </intent>
</queries>

<uses-permission android:name="android.permission.health.READ_STEPS" />
<uses-permission android:name="android.permission.health.READ_HEART_RATE" />
<uses-permission android:name="android.permission.health.READ_WEIGHT" />
<uses-permission android:name="android.permission.ACTIVITY_RECOGNITION" />
```

#### 사용 제약

- ⚠️ Google Fit API는 2024.05 deprecated → **Health Connect만 사용**
- ⚠️ 50+ 데이터 타입 지원하지만 일부는 OS 버전 제한
- ⚠️ Play Store 심사 시 **건강 데이터 사용 목적** 검토 (3~5일 소요)

---

## 7. 향후 통합 가능성

### 7.1 LDB-E 마이데이터 (레몬헬스케어)

| 항목 | 내용 |
|------|------|
| **운영사** | 레몬헬스케어 |
| **현재 상태** | 본사 R&D, 본 프로젝트는 인터페이스만 설계 |
| **활용 가능 시점** | Year 2~3 |
| **연결 가능 데이터** | 진료 기록, 처방, 검사 결과, 검진 이력 |

#### 본 프로젝트 활용 (Phase 4 이후)

```
약-영양제 상호작용 검토 (페르소나 B의 핵심 가치)
검진 기록 자동 통합 (필라이즈 대비 차별화)
의료진과 데이터 공유
```

> 🔍 **법규 측면**: HL7 FHIR KR Core 표준, 가명정보 처리, 환자 동의 — 상세는 [10번 문서](./10-compliance-checklist.md)

---

### 7.2 보건복지부 건강정보 고속도로

| 항목 | 내용 |
|------|------|
| **운영 기관** | 보건복지부 |
| **공식 자료** | https://kiri.or.kr/PDF/weeklytrend/20231016/trend20231016_11.pdf |
| **활용 가능 시점** | 정책 시행 시 (2025+) |

본 프로젝트는 마이데이터 표준에 맞게 설계되어 있으므로, 정책 시행 시 즉시 연동 가능.

---

## 8. 데이터 거버넌스

### 8.1 개인정보 분류

본 프로젝트가 다루는 데이터를 민감도별로 분류.

| 분류 | 데이터 | 보관 위치 | 암호화 |
|------|--------|---------|-------|
| **🔴 민감정보** (의료) | 만성질환, 복약, 검진 기록 | DB 컬럼 단위 암호화 | AES-256 |
| **🟡 일반 개인정보** | 이름, 나이, 성별, 키, 몸무게 | DB | TLS 1.3 (전송) |
| **🟢 측정 데이터** | 걸음수, 심박수, 활동에너지 | TimescaleDB | TLS 1.3 |
| **🔵 익명 통계** | 그룹 백분위 계산용 (v3) | 캐시 | — |

### 8.2 가명정보 처리

만성질환 같은 민감정보는 **가명 처리** 후 분석 활용:
- 직접 식별자 (이름, 전화번호, 주민번호) 제거
- 간접 식별자 결합 위험 평가
- 가명정보 처리 가이드라인 (개인정보보호위원회 2022) 준수

### 8.3 데이터 보관·삭제 정책

| 데이터 | 보관 기간 | 사용자 요청 시 |
|--------|---------|--------------|
| 영양제·식단 사진 | 30일 (캐시) | 즉시 삭제 |
| 사용자 프로필 | 회원 유지 동안 | 회원 탈퇴 시 즉시 삭제 |
| 측정 데이터 (걸음수 등) | 5년 (트렌드 분석) | 회원 탈퇴 시 즉시 삭제 |
| OCR/LLM 호출 로그 | 90일 (디버깅) | 익명화 후 보관 |
| 의료 정보 (만성질환) | 회원 유지 동안 | 즉시 삭제 + 백업도 삭제 |

### 8.4 데이터 무결성·갱신 정책

| 데이터 | 갱신 빈도 | 책임 |
|--------|---------|-----|
| KDRIs | 개정 발표 시 즉시 | DD |
| 식약처 식품영양성분 API | 분기 자동 동기화 | BE |
| 식약처 건강기능식품 원료 DB | 변경 알림 시 수동 | DD |
| 의료법·약사법 표현 가이드 | 변경 시 즉시 | DD, 법무 |

> 🔍 **법규·표준 상세**: [10. 컴플라이언스 체크리스트](./10-compliance-checklist.md)

---

## 9. 비용 추정 통합

### 9.1 PoC 단계 (Phase 1~2, 첫 6주)

| 항목 | 사용량 | 단가 | 합계 |
|------|--------|------|------|
| Cloud Vision API | 500건 (대부분 무료 티어) | $1.5/1k | **$0** |
| Claude API | 2,000회 호출 | sonnet | **약 $10~15** |
| KDRIs / 식약처 / AI Hub | — | 무료 | **$0** |
| Apple Developer | 연 $99 (학생 면제 가능) | — | **$0~99** |
| Google Play Developer | 1회 $25 | — | **$25** |
| 인프라 (NCP/AWS) | 학생 크레딧 | — | **$0** |
| **합계 (6주)** | | | **약 $35~140** |

### 9.2 MVP 단계 (Phase 3~4, 베타 50명)

| 항목 | 월 사용량 | 월 비용 |
|------|---------|--------|
| Cloud Vision API | 1,500건 | ~$0.75 |
| Claude API | 5,000회 | ~$15~25 |
| 인프라 | 1 vCPU 인스턴스 | $0 (크레딧) |
| **합계** | | **약 $17~27/월** |

### 9.3 정식 출시 (1만 MAU, 참고)

월 비용은 약 **$550~1,450** (06번 문서 5.2 절 참조).

---

## 📝 변경 이력

| 버전 | 날짜 | 변경 사항 | 작성자 |
|-----|------|---------|-------|
| v1.0 | 2026-05-03 | 초안 작성. 12종 데이터·API + 거버넌스 + 비용 통합 | TBD |

## 🔗 관련 문서

- [01. 프로젝트 개요](./01-project-overview.md)
- [06. 기술 스택](./06-tech-stack.md)
- [07. 핵심 알고리즘](./07-core-algorithm.md)
- [08. 구현 계획](./08-implementation-plan.md)
- [10. 컴플라이언스 체크리스트](./10-compliance-checklist.md)
