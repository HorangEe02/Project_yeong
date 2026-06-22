"""Upsert food_nutrition 40-class nutrition data (reconstructed).

Reconstructed from food_nutrition_40class_upsert.sql after the original
migration file for revision 0045_upsert_food_nutrition_40class_v2 was lost
before being committed, leaving the DB stranded on a revision Alembic could
not locate. All statements are INSERT ... ON CONFLICT (class_en) DO UPDATE,
so this is idempotent and safe to re-run against a DB that already holds the
data.

Revision ID: 0045_upsert_food_nutrition_40class_v2
Revises: 0044_normalize_check_constraint_names
Create Date: 2026-06-13
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0045_upsert_food_nutrition_40class_v2"
down_revision: str | None = "0044_normalize_check_constraint_names"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_UPSERT_SQL = r"""
-- 최종 서비스 40클래스 영양 UPSERT (food_nutrition 테이블)
-- source=aihub_taxo59_csv(1차) + 웹서치 감사 보정(10건, manifest=food-nutrition-40class-v2).
-- 1인분 = per_100g * serving_g/100. [WEB-FIX] 코멘트 = 웹 감사로 보정된 행.

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('barbecue-ribs', '갈비', 7, 266, 188.96, 10.29, 3.54, 11.99, 10.81, 560.34, 43.6, 2.52, 0.03, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('black-bean-noodles', '짜장면', 3, 483, 111.72, 17.02, 5.92, 1.95, 6.14, 236.19, 8.68, 0.33, 0.03, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('braised-chicken', '찜닭', 3, 314, 126.63, 7.16, 0.78, 6.56, 9.68, 193.47, 30, 1.3, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('braised-pork-hock', '족발', 3, 310, 194.99, 11.34, 6.85, 8.55, 16.5, 497.51, 57.55, 2.35, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('bread', '빵', 45, 150, 274.41, 37.4, 9.14, 10.77, 7.34, 238.68, 57.54, 3.48, 0.37, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('bulgogi', '불고기', 3, 237, 144.91, 6.97, 2.27, 8.43, 10.12, 224.22, 27.08, 2.79, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('cake', '케이크', 8, 182, 321.6, 35.09, 13.84, 18.06, 4.64, 146.36, 69.69, 3.71, 0.12, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('cold-noodles', '냉면', 4, 328, 166.23, 28.53, 1.85, 2.13, 7.8, 472.95, 31.89, 0.53, 0.02, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('curry', '카레', 8, 308, 153.67, 12.16, 1.74, 9.24, 5.9, 529.23, 30.36, 3.07, 0.41, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('dim-sum', '딤섬(찐만두)', 2, 272, 364.27, 34.71, 4.29, 19.3, 10.55, 149.78, 17.38, 7.5, 0.07, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('doenjang-jjigae', '된장찌개', 2, 300, 103.87, 4.48, 0.57, 6.75, 6.35, 378.21, 20.1, 2.01, 0.11, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('fish-cake', '어묵', 2, 110, 191.01, 16.52, 1.51, 7.81, 12.91, 401.07, 53.03, 0.57, 1.69, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('fried-chicken', '후라이드치킨', 43, 217, 236.26, 21.37, 4.98, 11.69, 11.37, 355.92, 88, 3, 0.83, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('fried-food-platter', '튀김(모둠)', 3, 124, 231.65, 18.34, 0.6, 11.86, 12.18, 486.79, 45.49, 2, 1.15, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('grilled-fish', '생선구이', 7, 74, 191.08, 0.46, NULL, 10.66, 21.69, 400.21, 61.25, 9.47, 0.68, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('grilled-pork-belly', '삼겹살', 1, 205, 220.4, 3.14, NULL, 18.2, 10.81, 159.28, 32.15, 9.28, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('hamburger', '햄버거', 5, 227, 179.43, 16.68, 0.87, 7.15, 12.01, 293.58, 21.27, 4, 0.35, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('japanese-ramen', '일본라멘', 5, 496, 114.82, 13.52, 0.77, 4.51, 4.51, 400.73, 110.56, 1.61, 0.02, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('jjigae-red', '빨간찌개', 4, 371, 75.39, 4.1, 1.32, 3.92, 6.14, 452.91, 26.57, 0.44, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('kalguksu', '칼국수', 5, 512, 95.03, 17.27, 1.64, 0.55, 4.29, 319.28, 2.54, 0.07, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('korean-blood-sausage', '순대', 3, 206, 151.63, 13.05, 0.01, 6.47, 9.68, 476.18, 95.94, 2.04, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('korean-ramyeon-red', '라면', 3, 519, 144.39, 19.87, NULL, 4.69, 5.41, 382.55, 0, 1.09, 0.03, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('mixed-rice-bowl', '비빔밥', 5, 362, 171.98, 28.75, 1.32, 3.65, 5.82, 236.23, 28.16, 0.47, 0.11, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('pasta', '파스타', 18, 359, 245.87, 27.11, 0.98, 12.03, 7.24, 366.43, 28.99, 1.5, 0.02, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('pizza', '피자', 29, 193, 199.4, 26.51, 2.46, 6.27, 7.71, 550, 13.61, 1.58, 0.08, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('pork-cutlet-dry', '돈가스', 6, 194, 241.61, 24.75, 7.7, 9.64, 12.69, 204.08, 65.13, 4.5, 0.87, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('raw-fish', '회', 7, 236, 114.61, 10.22, 2.17, 2.52, 12.11, 258.22, 13.37, 0.3, 0.01, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)  -- [WEB-FIX] 웹 감사 보정 적용
  VALUES ('rice-noodle-soup', '쌀국수', 11, 594, 97.96, 15.58, 0.19, 2.25, 3.53, 278.83, 13, 0.44, 0.02, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('rice-porridge', '죽', 8, 205, 227.06, 28.74, 15.85, 10.53, 4.79, 278.4, 32.43, 3.77, 0.25, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('rice-soup', '국밥', 3, 517, 91.34, 17.51, NULL, 0.71, 3.55, 192.17, 3.45, 0.06, 0.01, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('salad', '샐러드', 11, 134, 129.18, 10.64, 1.78, 7.52, 5.57, 128.31, 21.84, 1.17, 0.03, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('sandwich', '샌드위치', 26, 195, 242.8, 22.36, 1.77, 13.77, 8.34, 445.3, 53.57, 4.47, 0.21, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('savory-pancake', '전/부침개', 3, 217, 171.05, 23.73, NULL, 4.55, 8.15, 318.42, 10.99, 0.27, 0.78, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('seaweed-rice-roll', '김밥', 10, 205, 232.96, 37.97, 1.75, 5.11, 7.51, 372.18, 46.19, 0.51, 0.3, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('spicy-mixed-noodles', '비빔국수', 2, 175, 230.02, 47.3, 3.88, 0.77, 6.54, 448.53, 0.54, 0.08, 0, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('sushi', '초밥', 9, 221, 248.86, 36.9, 3.29, 3.55, 15.17, 536.98, 111.78, 0.69, 0.02, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('takoyaki', '타코야키', 1, 206, 161.46, 15.56, 1.65, 8.26, 5.23, 120.11, 36.6, 0.49, 0.77, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('tteokbokki-red', '떡볶이', 6, 280, 199.53, 33.73, 3.77, 4.42, 6.17, 458.77, 7.84, 1.06, 0.05, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('udon', '우동', 4, 468, 92.39, 10.01, NULL, 4.27, 2.51, 233.21, 9.31, 0.34, 0.01, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();

INSERT INTO food_nutrition (class_en, class_ko, n_source_codes, serving_g, kcal_100g, carb_g, sugar_g, fat_g, protein_g, sodium_mg, chol_mg, sat_fat_g, trans_fat_g, source, source_manifest_version)
  VALUES ('western-cream-soup', '양식수프', 5, 274, 139.17, 16.24, 0.36, 5.84, 5.05, 527.14, 14.95, 1.38, 0.07, 'aihub_taxo59_csv', 'food-nutrition-40class-v2')
  ON CONFLICT (class_en) DO UPDATE SET
    class_ko=EXCLUDED.class_ko, serving_g=EXCLUDED.serving_g, kcal_100g=EXCLUDED.kcal_100g,
    carb_g=EXCLUDED.carb_g, sugar_g=EXCLUDED.sugar_g, fat_g=EXCLUDED.fat_g,
    protein_g=EXCLUDED.protein_g, sodium_mg=EXCLUDED.sodium_mg, chol_mg=EXCLUDED.chol_mg,
    sat_fat_g=EXCLUDED.sat_fat_g, trans_fat_g=EXCLUDED.trans_fat_g,
    source_manifest_version=EXCLUDED.source_manifest_version, updated_at=now();
"""


def upgrade() -> None:
    """Upsert the curated 40-class nutrition rows (idempotent)."""
    op.execute(_UPSERT_SQL)


def downgrade() -> None:
    """Remove rows seeded by this manifest version."""
    op.execute(
        "DELETE FROM food_nutrition " "WHERE source_manifest_version = 'food-nutrition-40class-v2';"
    )
