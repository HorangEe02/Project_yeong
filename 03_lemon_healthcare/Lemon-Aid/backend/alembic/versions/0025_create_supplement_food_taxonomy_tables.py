"""Create supplement and food taxonomy catalog tables.

Revision ID: 0025_create_supplement_food_taxonomy_tables
Revises: 0024_add_user_supplement_precaution_snapshot
Create Date: 2026-06-01 00:00:00.000000

The taxonomy tables let the backend store direct user supplement/meal records
against curated categories without exposing raw images, OCR text, provider
payloads, request headers, or secrets. Supplement categories are initialized from
the repo-local crawling-image folder names. Food taxonomy follows the current
Cuisine -> Course -> Food item design requested for Korean, Chinese, Japanese,
Western, and Other/Fast categories.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_create_supplement_food_taxonomy_tables"
down_revision: str | Sequence[str] | None = "0024_add_user_supplement_precaution_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

APP_ROLE = "lemon_app"
CATALOG_POLICY = "lemon_app_catalog_read"
MANIFEST_VERSION = "crawling-image-folder-v1"

CATALOG_TABLES = (
    "supplement_categories",
    "supplement_product_categories",
    "food_cuisines",
    "food_courses",
    "food_catalog_items",
)

SUPPLEMENT_CATEGORY_SEEDS: tuple[tuple[str, str, str], ...] = (
    ("남성_쏘팔메토", "남성 쏘팔메토", "[남성_쏘팔메토]"),
    ("항산화", "항산화", "[항산화]"),
    ("관절_MSM_콘드로이친", "관절 MSM 콘드로이친", "[관절_MSM_콘드로이친]"),
    ("오메가3", "오메가3", "[오메가3]"),
    ("다이어트_체지방", "다이어트 체지방", "[다이어트_체지방]"),
    ("BCAA_EAA", "BCAA EAA", "[BCAA_EAA]"),
    ("스피루리나_클로렐라", "스피루리나 클로렐라", "[스피루리나_클로렐라]"),
    ("코엔자임Q10", "코엔자임Q10", "[코엔자임Q10]"),
    ("비타민B", "비타민B", "[비타민B]"),
    ("HMB_타우린", "HMB 타우린", "[HMB_타우린]"),
    ("비타민A", "비타민A", "[비타민A]"),
    ("프리워크아웃", "프리워크아웃", "[프리워크아웃]"),
    ("비타민K", "비타민K", "[비타민K]"),
    ("카페인_각성", "카페인 각성", "[카페인_각성]"),
    ("비타민E", "비타민E", "[비타민E]"),
    ("아연", "아연", "[아연]"),
    ("철분", "철분", "[철분]"),
    ("단백질_프로틴", "단백질 프로틴", "[단백질_프로틴]"),
    ("멀티비타민", "멀티비타민", "[멀티비타민]"),
    ("수면_멜라토닌", "수면 멜라토닌", "[수면_멜라토닌]"),
    ("크레아틴", "크레아틴", "[크레아틴]"),
    ("뇌_은행잎", "뇌 은행잎", "[뇌_은행잎]"),
    ("콜라겐", "콜라겐", "[콜라겐]"),
    ("기타", "기타", "[기타]"),
    ("식이섬유", "식이섬유", "[식이섬유]"),
    ("강황_커큐민", "강황 커큐민", "[강황_커큐민]"),
    ("종합영양제", "종합영양제", "[종합영양제]"),
    ("여성영양제", "여성영양제", "[여성영양제]"),
    ("혈관_낫토_폴리코사놀", "혈관 낫토 폴리코사놀", "[혈관_낫토_폴리코사놀]"),
    ("글루코사민", "글루코사민", "[글루코사민]"),
    ("프로폴리스_벌", "프로폴리스 벌", "[프로폴리스_벌]"),
    ("스트레스_아쉬와간다", "스트레스 아쉬와간다", "[스트레스_아쉬와간다]"),
    ("유산균_프로바이오틱", "유산균 프로바이오틱", "[유산균_프로바이오틱]"),
    ("비타민D", "비타민D", "[비타민D]"),
    ("칼슘", "칼슘", "[칼슘]"),
    ("어린이_키성장", "어린이 키성장", "[어린이_키성장]"),
    ("아르기닌_시트룰린", "아르기닌 시트룰린", "[아르기닌_시트룰린]"),
    ("비타민C", "비타민C", "[비타민C]"),
    ("밀크씨슬_간", "밀크씨슬 간", "[밀크씨슬_간]"),
    ("아사이_베리류", "아사이 베리류", "[아사이_베리류]"),
    ("마그네슘", "마그네슘", "[마그네슘]"),
    ("효소_소화", "효소 소화", "[효소_소화]"),
    ("루테인_눈", "루테인 눈", "[루테인_눈]"),
)

FOOD_CUISINE_SEEDS: tuple[tuple[str, str, str], ...] = (
    ("korean", "한식", "Korean"),
    ("chinese", "중식", "Chinese"),
    ("japanese", "일식", "Japanese"),
    ("western", "양식", "Western"),
    ("other", "기타", "Ethnic/Fast"),
)

FOOD_COURSE_SEEDS: tuple[tuple[str, str, str, str], ...] = (
    ("korean", "main", "메인", "Main"),
    ("korean", "side", "서브(반찬)", "Side dishes"),
    ("korean", "soup_stew", "국·탕·찌개", "Soup, tang, jjigae"),
    ("korean", "salad", "무침(샐러드)", "Muchim salad"),
    ("korean", "dessert_rice_cake", "디저트·떡", "Dessert and rice cake"),
    ("chinese", "main", "메인", "Main"),
    ("chinese", "side", "서브", "Side"),
    ("chinese", "dessert", "디저트", "Dessert"),
    ("japanese", "main", "메인", "Main"),
    ("japanese", "soup", "국", "Soup"),
    ("japanese", "side", "서브", "Side"),
    ("japanese", "dessert", "디저트", "Dessert"),
    ("western", "main", "메인", "Main"),
    ("western", "soup", "수프", "Soup"),
    ("western", "salad", "샐러드", "Salad"),
    ("western", "side", "사이드", "Side"),
    ("western", "dessert", "디저트", "Dessert"),
    ("other", "ethnic", "태국·인도·멕시칸·베트남·중동", "Ethnic"),
    ("other", "fast_food", "패스트푸드", "Fast food"),
)

FOOD_ITEM_SEEDS: tuple[tuple[str, str, str, str | None], ...] = (
    ("korean", "soup_stew", "된장찌개", "Doenjang jjigae"),
    ("korean", "soup_stew", "김치찌개", "Kimchi jjigae"),
)


def _stable_uuid(kind: str, *parts: str) -> str:
    """Return deterministic UUID strings for migration seed rows."""
    return str(uuid5(NAMESPACE_URL, "lemon-aid:" + kind + ":" + "|".join(parts)))


def _create_catalog_read_policy(table_name: str) -> None:
    """Expose catalog rows to the backend request role without user-data writes."""
    op.execute(f"ALTER TABLE public.{table_name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"""
        CREATE POLICY {CATALOG_POLICY} ON public.{table_name}
          FOR SELECT TO {APP_ROLE}
          USING (true)
        """)
    op.execute(f"ALTER TABLE public.{table_name} FORCE ROW LEVEL SECURITY")
    op.execute(f"GRANT SELECT ON public.{table_name} TO {APP_ROLE}")


def upgrade() -> None:
    """Create supplement and food taxonomy tables plus initial category seeds."""
    op.create_table(
        "supplement_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_key", sa.String(length=120), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("source_folder_name", sa.String(length=180), nullable=True),
        sa.Column("source_path", sa.String(length=512), nullable=True),
        sa.Column(
            "source_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source_manifest_version", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category_key <> ''",
            name=op.f("ck_supplement_categories_category_key_nonempty"),
        ),
        sa.CheckConstraint(
            "display_name <> ''",
            name=op.f("ck_supplement_categories_display_name_nonempty"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_supplement_categories_sort_order_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplement_categories")),
        sa.UniqueConstraint(
            "category_key",
            name=op.f("uq_supplement_categories_category_key"),
        ),
    )
    op.create_index(
        "ix_supplement_categories_display_name",
        "supplement_categories",
        ["display_name"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_categories_active_sort",
        "supplement_categories",
        ["is_active", "sort_order"],
        unique=False,
    )

    op.create_table(
        "supplement_product_categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "source_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source <> ''", name=op.f("ck_supplement_product_categories_source_nonempty")
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 1)",
            name=op.f("ck_supplement_product_categories_confidence_range"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_supplement_product_categories_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["supplement_categories.id"],
            name=op.f("fk_supplement_product_categories_category_id_supplement_categories"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["supplement_products.id"],
            name=op.f("fk_supplement_product_categories_product_id_supplement_products"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_supplement_product_categories")),
        sa.UniqueConstraint(
            "product_id",
            "category_id",
            name=op.f("uq_supplement_product_categories_product_category"),
        ),
    )
    op.create_index(
        "ix_supplement_product_categories_product_id",
        "supplement_product_categories",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_product_categories_category_id",
        "supplement_product_categories",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        "ix_supplement_product_categories_primary",
        "supplement_product_categories",
        ["product_id", "is_primary"],
        unique=False,
    )

    op.create_table(
        "food_cuisines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cuisine_code", sa.String(length=40), nullable=False),
        sa.Column("display_name_ko", sa.String(length=80), nullable=False),
        sa.Column("display_name_en", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "cuisine_code <> ''",
            name=op.f("ck_food_cuisines_cuisine_code_nonempty"),
        ),
        sa.CheckConstraint(
            "display_name_ko <> ''",
            name=op.f("ck_food_cuisines_display_name_ko_nonempty"),
        ),
        sa.CheckConstraint(
            "display_name_en <> ''",
            name=op.f("ck_food_cuisines_display_name_en_nonempty"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_food_cuisines_sort_order_nonnegative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_cuisines")),
        sa.UniqueConstraint("cuisine_code", name=op.f("uq_food_cuisines_cuisine_code")),
    )
    op.create_index(
        "ix_food_cuisines_active_sort",
        "food_cuisines",
        ["is_active", "sort_order"],
        unique=False,
    )

    op.create_table(
        "food_courses",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cuisine_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_code", sa.String(length=60), nullable=False),
        sa.Column("display_name_ko", sa.String(length=80), nullable=False),
        sa.Column("display_name_en", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("course_code <> ''", name=op.f("ck_food_courses_course_code_nonempty")),
        sa.CheckConstraint(
            "display_name_ko <> ''",
            name=op.f("ck_food_courses_display_name_ko_nonempty"),
        ),
        sa.CheckConstraint(
            "display_name_en <> ''",
            name=op.f("ck_food_courses_display_name_en_nonempty"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_food_courses_sort_order_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["cuisine_id"],
            ["food_cuisines.id"],
            name=op.f("fk_food_courses_cuisine_id_food_cuisines"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_courses")),
        sa.UniqueConstraint(
            "cuisine_id",
            "course_code",
            name=op.f("uq_food_courses_cuisine_course"),
        ),
    )
    op.create_index(
        "ix_food_courses_cuisine_sort",
        "food_courses",
        ["cuisine_id", "sort_order"],
        unique=False,
    )

    op.create_table(
        "food_catalog_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cuisine_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_name_ko", sa.String(length=120), nullable=False),
        sa.Column("canonical_name_en", sa.String(length=160), nullable=True),
        sa.Column(
            "aliases",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "nutrition_reference",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column(
            "source_payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "canonical_name_ko <> ''",
            name=op.f("ck_food_catalog_items_canonical_name_ko_nonempty"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(aliases) = 'array'",
            name=op.f("ck_food_catalog_items_aliases_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(nutrition_reference) = 'object'",
            name=op.f("ck_food_catalog_items_nutrition_reference_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(source_payload) = 'object'",
            name=op.f("ck_food_catalog_items_source_payload_object"),
        ),
        sa.CheckConstraint("source <> ''", name=op.f("ck_food_catalog_items_source_nonempty")),
        sa.ForeignKeyConstraint(
            ["course_id"],
            ["food_courses.id"],
            name=op.f("fk_food_catalog_items_course_id_food_courses"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["cuisine_id"],
            ["food_cuisines.id"],
            name=op.f("fk_food_catalog_items_cuisine_id_food_cuisines"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_catalog_items")),
        sa.UniqueConstraint(
            "cuisine_id",
            "course_id",
            "canonical_name_ko",
            name=op.f("uq_food_catalog_items_cuisine_course_name"),
        ),
    )
    op.create_index(
        "ix_food_catalog_items_cuisine_course",
        "food_catalog_items",
        ["cuisine_id", "course_id"],
        unique=False,
    )
    op.create_index(
        "ix_food_catalog_items_name_ko",
        "food_catalog_items",
        ["canonical_name_ko"],
        unique=False,
    )

    op.add_column(
        "meal_food_items",
        sa.Column("food_catalog_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        op.f("fk_meal_food_items_food_catalog_item_id_food_catalog_items"),
        "meal_food_items",
        "food_catalog_items",
        ["food_catalog_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_meal_food_items_food_catalog_item_id",
        "meal_food_items",
        ["food_catalog_item_id"],
        unique=False,
    )

    supplement_categories = sa.table(
        "supplement_categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("category_key", sa.String),
        sa.column("display_name", sa.String),
        sa.column("source_folder_name", sa.String),
        sa.column("source_path", sa.String),
        sa.column("source_manifest_version", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        supplement_categories,
        [
            {
                "id": _stable_uuid("supplement-category", category_key),
                "category_key": category_key,
                "display_name": display_name,
                "source_folder_name": folder_name,
                "source_path": f"data/nutrition_reference/crawling-image/{folder_name}",
                "source_manifest_version": MANIFEST_VERSION,
                "sort_order": sort_order,
                "is_active": True,
            }
            for sort_order, (category_key, display_name, folder_name) in enumerate(
                SUPPLEMENT_CATEGORY_SEEDS
            )
        ],
    )

    food_cuisines = sa.table(
        "food_cuisines",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("cuisine_code", sa.String),
        sa.column("display_name_ko", sa.String),
        sa.column("display_name_en", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    cuisine_ids = {
        cuisine_code: _stable_uuid("food-cuisine", cuisine_code)
        for cuisine_code, _, _ in FOOD_CUISINE_SEEDS
    }
    op.bulk_insert(
        food_cuisines,
        [
            {
                "id": cuisine_ids[cuisine_code],
                "cuisine_code": cuisine_code,
                "display_name_ko": display_name_ko,
                "display_name_en": display_name_en,
                "sort_order": sort_order,
                "is_active": True,
            }
            for sort_order, (cuisine_code, display_name_ko, display_name_en) in enumerate(
                FOOD_CUISINE_SEEDS
            )
        ],
    )

    food_courses = sa.table(
        "food_courses",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("cuisine_id", postgresql.UUID(as_uuid=True)),
        sa.column("course_code", sa.String),
        sa.column("display_name_ko", sa.String),
        sa.column("display_name_en", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    course_ids = {
        (cuisine_code, course_code): _stable_uuid("food-course", cuisine_code, course_code)
        for cuisine_code, course_code, _, _ in FOOD_COURSE_SEEDS
    }
    course_order_by_cuisine: dict[str, int] = {}
    course_rows = []
    for cuisine_code, course_code, display_name_ko, display_name_en in FOOD_COURSE_SEEDS:
        course_order = course_order_by_cuisine.get(cuisine_code, 0)
        course_order_by_cuisine[cuisine_code] = course_order + 1
        course_rows.append(
            {
                "id": course_ids[(cuisine_code, course_code)],
                "cuisine_id": cuisine_ids[cuisine_code],
                "course_code": course_code,
                "display_name_ko": display_name_ko,
                "display_name_en": display_name_en,
                "sort_order": course_order,
                "is_active": True,
            }
        )
    op.bulk_insert(food_courses, course_rows)

    food_catalog_items = sa.table(
        "food_catalog_items",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("cuisine_id", postgresql.UUID(as_uuid=True)),
        sa.column("course_id", postgresql.UUID(as_uuid=True)),
        sa.column("canonical_name_ko", sa.String),
        sa.column("canonical_name_en", sa.String),
        sa.column("source", sa.String),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        food_catalog_items,
        [
            {
                "id": _stable_uuid("food-item", cuisine_code, course_code, name_ko),
                "cuisine_id": cuisine_ids[cuisine_code],
                "course_id": course_ids[(cuisine_code, course_code)],
                "canonical_name_ko": name_ko,
                "canonical_name_en": name_en,
                "source": "manual_seed",
                "is_active": True,
            }
            for cuisine_code, course_code, name_ko, name_en in FOOD_ITEM_SEEDS
        ],
    )

    for table_name in CATALOG_TABLES:
        _create_catalog_read_policy(table_name)


def downgrade() -> None:
    """Drop supplement and food taxonomy tables."""
    op.drop_index("ix_meal_food_items_food_catalog_item_id", table_name="meal_food_items")
    op.drop_constraint(
        op.f("fk_meal_food_items_food_catalog_item_id_food_catalog_items"),
        "meal_food_items",
        type_="foreignkey",
    )
    op.drop_column("meal_food_items", "food_catalog_item_id")

    op.drop_index("ix_food_catalog_items_name_ko", table_name="food_catalog_items")
    op.drop_index("ix_food_catalog_items_cuisine_course", table_name="food_catalog_items")
    op.drop_table("food_catalog_items")
    op.drop_index("ix_food_courses_cuisine_sort", table_name="food_courses")
    op.drop_table("food_courses")
    op.drop_index("ix_food_cuisines_active_sort", table_name="food_cuisines")
    op.drop_table("food_cuisines")

    op.drop_index(
        "ix_supplement_product_categories_primary",
        table_name="supplement_product_categories",
    )
    op.drop_index(
        "ix_supplement_product_categories_category_id",
        table_name="supplement_product_categories",
    )
    op.drop_index(
        "ix_supplement_product_categories_product_id",
        table_name="supplement_product_categories",
    )
    op.drop_table("supplement_product_categories")
    op.drop_index("ix_supplement_categories_active_sort", table_name="supplement_categories")
    op.drop_index("ix_supplement_categories_display_name", table_name="supplement_categories")
    op.drop_table("supplement_categories")
