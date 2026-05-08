"""문서 버전 관리 DB

초안 작성/수정 이력을 SQLite에 영구 저장한다.
- 문서 단위: documents 테이블 (doc_type, title, author, department)
- 버전 단위: versions 테이블 (template_vars, rendered_text, 변경 요약)
- 이전 버전으로 롤백 지원
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

VERSION_DB_PATH = Path("data/draft_versions.db")


def init_version_db(db_path: Path = VERSION_DB_PATH) -> None:
    """문서 버전 DB 초기화"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_type TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            author TEXT DEFAULT '',
            department TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        );

        CREATE TABLE IF NOT EXISTS versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            version_num INTEGER NOT NULL DEFAULT 1,
            template_vars_json TEXT DEFAULT '{}',
            rendered_text TEXT DEFAULT '',
            change_summary TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            created_by TEXT DEFAULT '',
            FOREIGN KEY (document_id) REFERENCES documents(id)
        );

        CREATE INDEX IF NOT EXISTS idx_versions_doc
        ON versions(document_id, version_num);

        CREATE INDEX IF NOT EXISTS idx_documents_author
        ON documents(author, created_at DESC);
    """)
    conn.commit()
    conn.close()


def _get_conn(db_path: Path = VERSION_DB_PATH) -> sqlite3.Connection:
    init_version_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def save_version(
    doc_type: str,
    title: str,
    author: str,
    department: str,
    template_vars: dict,
    rendered_text: str,
    change_summary: str = "초기 작성",
    document_id: Optional[int] = None,
    db_path: Path = VERSION_DB_PATH,
) -> dict:
    """새 버전을 저장한다. document_id가 없으면 새 문서를 생성한다.

    Returns:
        {"document_id": int, "version_id": int, "version_num": int}
    """
    conn = _get_conn(db_path)
    try:
        if document_id is None:
            cur = conn.execute(
                "INSERT INTO documents (doc_type, title, author, department) VALUES (?, ?, ?, ?)",
                (doc_type, title, author, department),
            )
            document_id = cur.lastrowid
            version_num = 1
        else:
            row = conn.execute(
                "SELECT MAX(version_num) as max_ver FROM versions WHERE document_id = ?",
                (document_id,),
            ).fetchone()
            version_num = (row["max_ver"] or 0) + 1
            conn.execute(
                "UPDATE documents SET updated_at = datetime('now', 'localtime') WHERE id = ?",
                (document_id,),
            )

        vars_json = json.dumps(template_vars, ensure_ascii=False, default=str)
        cur = conn.execute(
            """INSERT INTO versions
               (document_id, version_num, template_vars_json, rendered_text, change_summary, created_by)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (document_id, version_num, vars_json, rendered_text, change_summary, author),
        )
        version_id = cur.lastrowid
        conn.commit()

        return {
            "document_id": document_id,
            "version_id": version_id,
            "version_num": version_num,
        }
    finally:
        conn.close()


def get_document_history(
    document_id: int,
    limit: int = 20,
    db_path: Path = VERSION_DB_PATH,
) -> list[dict]:
    """문서의 버전 이력을 조회한다."""
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            """SELECT id, document_id, version_num, change_summary,
                      created_at, created_by
               FROM versions
               WHERE document_id = ?
               ORDER BY version_num DESC
               LIMIT ?""",
            (document_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_version(version_id: int, db_path: Path = VERSION_DB_PATH) -> Optional[dict]:
    """특정 버전의 전체 내용을 조회한다."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            """SELECT v.*, d.doc_type, d.title, d.author, d.department
               FROM versions v
               JOIN documents d ON v.document_id = d.id
               WHERE v.id = ?""",
            (version_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["template_vars"] = json.loads(result.get("template_vars_json", "{}"))
        return result
    finally:
        conn.close()


def get_recent_documents(
    author: str = "",
    department: str = "",
    limit: int = 20,
    db_path: Path = VERSION_DB_PATH,
) -> list[dict]:
    """최근 문서 목록을 조회한다."""
    conn = _get_conn(db_path)
    try:
        query = """
            SELECT d.id, d.doc_type, d.title, d.author, d.department,
                   d.created_at, d.updated_at,
                   COUNT(v.id) as version_count,
                   MAX(v.version_num) as latest_version
            FROM documents d
            LEFT JOIN versions v ON d.id = v.document_id
        """
        conditions = []
        params = []
        if author:
            conditions.append("d.author = ?")
            params.append(author)
        if department:
            conditions.append("d.department = ?")
            params.append(department)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " GROUP BY d.id ORDER BY d.updated_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def rollback_to_version(
    version_id: int,
    author: str = "",
    db_path: Path = VERSION_DB_PATH,
) -> Optional[dict]:
    """이전 버전으로 롤백한다 (새 버전으로 복사).

    Returns:
        새로 생성된 버전 정보 또는 None
    """
    source = get_version(version_id, db_path)
    if not source:
        return None

    return save_version(
        doc_type=source["doc_type"],
        title=source["title"],
        author=author or source.get("created_by", ""),
        department=source["department"],
        template_vars=source["template_vars"],
        rendered_text=source["rendered_text"],
        change_summary=f"v{source['version_num']}에서 롤백",
        document_id=source["document_id"],
        db_path=db_path,
    )


def get_version_stats(db_path: Path = VERSION_DB_PATH) -> dict:
    """버전 DB 통계"""
    conn = _get_conn(db_path)
    try:
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        ver_count = conn.execute("SELECT COUNT(*) FROM versions").fetchone()[0]
        return {"documents": doc_count, "versions": ver_count}
    finally:
        conn.close()
