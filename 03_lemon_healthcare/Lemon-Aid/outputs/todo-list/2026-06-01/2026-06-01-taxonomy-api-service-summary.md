# 2026-06-01 Taxonomy API/Service 구현 요약

> 작성 기준: 2026-06-01
> 범위: backend 영양제/음식 taxonomy catalog, 사용자 영양제/식단 조회 필터, 관련 DB/API 계약

---

## 1. Summary

영양제와 음식 데이터를 사용자 기록 조회 흐름에서 분류 기준으로 사용할 수 있도록 backend taxonomy 계층을 추가했다.

이번 변경의 핵심은 다음과 같다.

- 영양제 카테고리는 `data/nutrition_reference/crawling-image` 폴더명을 기준으로 catalog seed를 구성했다.
- 음식 taxonomy는 `한식/중식/일식/양식/기타` 대분류와 cuisine별 course 구조로 분리했다.
- catalog 조회 API와 사용자 영양제/식단 조회 필터 API를 추가했다.
- 식단 조회 권한은 `meal:read` scope로 분리하고, 이미지 분석/확정은 기존 `meal:write`를 유지했다.
- 사용자 데이터 조회는 owner scope와 soft-delete 조건을 먼저 적용하고, stale taxonomy filter는 `422 taxonomy_filter_not_found`로 반환한다.

---

## 2. 주요 변경 파일

### DB / Migration

- `backend/alembic/versions/0024_add_user_supplement_precaution_snapshot.py`
  - 사용자가 확인한 주의사항 snapshot 저장 필드 추가
- `backend/alembic/versions/0025_create_supplement_food_taxonomy_tables.py`
  - `supplement_categories`
  - `supplement_product_categories`
  - `food_cuisines`
  - `food_courses`
  - `food_catalog_items`
  - `meal_food_items.food_catalog_item_id`
  - catalog read RLS policy 및 초기 seed 추가

### Backend Models / Schemas

- `backend/Nutrition-backend/src/models/db/supplement.py`
  - 영양제 category 및 product-category mapping 모델 추가
- `backend/Nutrition-backend/src/models/db/meal.py`
  - 음식 cuisine/course/catalog item 모델 및 meal food item catalog reference 추가
- `backend/Nutrition-backend/src/models/schemas/taxonomy.py`
  - public taxonomy catalog 응답 schema 추가
- `backend/Nutrition-backend/src/models/schemas/supplement.py`
  - 사용자 영양제 응답에 category summary 추가
- `backend/Nutrition-backend/src/models/schemas/meal.py`
  - 사용자 식단 조회 응답 및 food catalog item reference 추가

### Services / API

- `backend/Nutrition-backend/src/services/taxonomy_catalog.py`
  - active catalog 조회
  - taxonomy filter validation
  - user-data filter용 catalog reference resolution
- `backend/Nutrition-backend/src/api/v1/supplements.py`
  - `GET /api/v1/supplements/categories`
  - `GET /api/v1/supplements?category_key=...&category_id=...&q=...`
- `backend/Nutrition-backend/src/api/v1/meals.py`
  - `GET /api/v1/meals/cuisines`
  - `GET /api/v1/meals/foods`
  - `GET /api/v1/meals?cuisine_code=...&course_code=...`
- `backend/Nutrition-backend/src/security/scopes.py`
  - `meal:read` scope 추가
- `backend/Nutrition-backend/src/security/auth.py`
  - `require_meal_read` dependency 추가

---

## 3. API 계약

### Catalog 조회

- `GET /api/v1/supplements/categories`
  - query: `q`, `limit`, `offset`
  - active category만 반환
  - 응답: `results`, `limit`, `offset`

- `GET /api/v1/meals/cuisines`
  - active cuisine과 active course를 nested 형태로 반환
  - 응답: `results[].courses[]`

- `GET /api/v1/meals/foods`
  - query: `cuisine_code`, `course_code`, `q`, `limit`, `offset`
  - 응답: 음식 catalog item summary

### 사용자 데이터 조회

- `GET /api/v1/supplements`
  - query: `category_key`, `category_id`, `q`
  - current user 소유 영양제만 조회
  - category filter가 있으면 matched product category join으로 제한
  - category가 없는 기존 사용자 영양제는 unfiltered 조회에는 유지

- `GET /api/v1/meals`
  - query: `cuisine_code`, `course_code`, `food_catalog_item_id`, `from_eaten_at`, `to_eaten_at`, `limit`, `offset`
  - current user confirmed meal만 조회
  - 기본 정렬: `eaten_at DESC`, `created_at DESC`

---

## 4. 보안/데이터 기준

- catalog table은 RLS read policy로 읽기 전용 접근만 허용한다.
- 사용자 영양제/식단 조회는 항상 owner scope를 먼저 적용한다.
- soft-delete된 사용자 데이터는 조회에서 제외한다.
- raw OCR, provider payload, image path, local source path는 taxonomy 응답에 포함하지 않는다.
- stale taxonomy filter는 빈 결과로 조용히 넘기지 않고 `422 taxonomy_filter_not_found`로 반환한다.

---

## 5. 참고한 공식 문서

- FastAPI Query Parameter Validation: https://fastapi.tiangolo.com/tutorial/query-params-str-validations/
- SQLAlchemy ORM Select: https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
- Pydantic Models: https://docs.pydantic.dev/latest/concepts/models/
