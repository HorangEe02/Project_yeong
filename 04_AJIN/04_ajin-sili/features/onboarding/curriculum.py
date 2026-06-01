"""온보딩 커리큘럼 — 부서별 학습 경로 생성 + 진행 추적

GlossaryEntry의 difficulty(basic/intermediate/advanced)와
departments_involved를 기반으로 3단계 학습 경로를 자동 구성한다.

저장: SQLite data/onboarding_curriculum.db
"""

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

CURRICULUM_DB_PATH = Path("data/onboarding_curriculum.db")

DIFFICULTY_ORDER = {"basic": 0, "intermediate": 1, "advanced": 2}
DIFFICULTY_LABELS = {"basic": "기초", "intermediate": "핵심", "advanced": "심화"}


@dataclass
class CurriculumItem:
    """커리큘럼 항목"""
    term: str
    category: str
    difficulty: str
    korean_name: str = ""
    definition: str = ""
    is_completed: bool = False
    completed_at: Optional[str] = None


@dataclass
class CurriculumPath:
    """부서별 학습 경로"""
    department: str
    items: list[CurriculumItem] = field(default_factory=list)
    total: int = 0
    completed: int = 0
    progress_pct: float = 0.0


# ── DB 초기화 ──

def init_curriculum_db(db_path: Path = CURRICULUM_DB_PATH) -> None:
    """커리큘럼 진행 DB 초기화"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS curriculum_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            department TEXT NOT NULL,
            term TEXT NOT NULL,
            completed_at TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(session_id, term)
        );

        CREATE INDEX IF NOT EXISTS idx_curriculum_session
        ON curriculum_progress(session_id, department);
    """)
    conn.commit()
    conn.close()


def _get_conn(db_path: Path = CURRICULUM_DB_PATH) -> sqlite3.Connection:
    init_curriculum_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ── 커리큘럼 생성 ──

def _load_glossary_entries() -> list:
    """GlossaryMatcher에서 용어 사전을 로드한다."""
    try:
        from features.onboarding.glossary_matcher import GlossaryMatcher
        matcher = GlossaryMatcher()
        return list(matcher.entries.values())
    except Exception:
        return []


def _get_department_keywords(department: str) -> list[str]:
    """부서 프로필에서 핵심 키워드를 추출한다."""
    keywords = []
    try:
        from features.onboarding.department_router import DEPARTMENT_PROFILES
        profile = DEPARTMENT_PROFILES.get(department)
        if profile:
            keywords.extend(profile.core_responsibilities)
            keywords.extend(profile.key_systems)
    except Exception:
        pass

    try:
        from core.department_config import get_dept_config
        config = get_dept_config(department)
        keywords.extend(config.get("glossary_focus", []))
        keywords.extend(config.get("onboarding_essentials", []))
    except Exception:
        pass

    return keywords


def build_curriculum(department: str) -> CurriculumPath:
    """부서별 학습 경로를 생성한다.

    1. 용어 사전에서 부서 관련 용어 필터링
    2. difficulty 기준으로 기초→핵심→심화 정렬
    3. CurriculumPath로 반환
    """
    entries = _load_glossary_entries()
    dept_keywords = _get_department_keywords(department)
    dept_kw_lower = [kw.lower() for kw in dept_keywords]

    items = []
    for entry in entries:
        relevance = 0

        # 부서 직접 관련
        if hasattr(entry, 'departments_involved') and department in entry.departments_involved:
            relevance += 3

        # 키워드 매칭
        entry_text = f"{entry.term} {entry.full_name} {entry.category}".lower()
        for kw in dept_kw_lower:
            if kw.lower() in entry_text:
                relevance += 1

        if relevance > 0:
            items.append(CurriculumItem(
                term=entry.term,
                category=entry.category,
                difficulty=getattr(entry, 'difficulty', 'basic'),
                korean_name=getattr(entry, 'korean_name', ''),
                definition=getattr(entry, 'definition', '')[:100],
            ))

    # 난이도 순 정렬 → 같은 난이도 내에서 카테고리 순
    items.sort(key=lambda x: (
        DIFFICULTY_ORDER.get(x.difficulty, 0),
        x.category,
        x.term,
    ))

    # 중복 제거 (term 기준)
    seen = set()
    unique_items = []
    for item in items:
        if item.term not in seen:
            seen.add(item.term)
            unique_items.append(item)

    return CurriculumPath(
        department=department,
        items=unique_items,
        total=len(unique_items),
    )


# ── 진행 추적 ──

def mark_completed(
    session_id: str,
    department: str,
    term: str,
    db_path: Path = CURRICULUM_DB_PATH,
) -> None:
    """학습 항목을 완료 처리한다."""
    conn = _get_conn(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO curriculum_progress (session_id, department, term) VALUES (?, ?, ?)",
            (session_id, department, term),
        )
        conn.commit()
    finally:
        conn.close()


def get_completed_terms(
    session_id: str,
    db_path: Path = CURRICULUM_DB_PATH,
) -> list[str]:
    """완료된 용어 목록을 조회한다."""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT term FROM curriculum_progress WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        return [r["term"] for r in rows]
    finally:
        conn.close()


def get_progress(
    session_id: str,
    department: str,
    db_path: Path = CURRICULUM_DB_PATH,
) -> CurriculumPath:
    """진행 상태가 반영된 커리큘럼을 반환한다."""
    path = build_curriculum(department)
    completed = set(get_completed_terms(session_id, db_path))

    for item in path.items:
        if item.term in completed:
            item.is_completed = True

    path.completed = sum(1 for i in path.items if i.is_completed)
    path.progress_pct = round(
        path.completed / path.total * 100, 1
    ) if path.total > 0 else 0.0

    return path


def get_next_items(
    session_id: str,
    department: str,
    count: int = 3,
    db_path: Path = CURRICULUM_DB_PATH,
) -> list[CurriculumItem]:
    """다음 학습할 항목을 반환한다."""
    path = get_progress(session_id, department, db_path)
    remaining = [i for i in path.items if not i.is_completed]
    return remaining[:count]


def get_curriculum_stats(
    session_id: str,
    department: str,
    db_path: Path = CURRICULUM_DB_PATH,
) -> dict:
    """커리큘럼 통계"""
    path = get_progress(session_id, department, db_path)

    by_difficulty = {}
    for diff in DIFFICULTY_ORDER:
        items = [i for i in path.items if i.difficulty == diff]
        completed = sum(1 for i in items if i.is_completed)
        by_difficulty[DIFFICULTY_LABELS[diff]] = {
            "total": len(items),
            "completed": completed,
        }

    return {
        "department": department,
        "total": path.total,
        "completed": path.completed,
        "progress_pct": path.progress_pct,
        "by_difficulty": by_difficulty,
    }
