"""D3 job — D1 FTS5 인덱스 일일 재구축 (정합성 보장)."""
from __future__ import annotations


def run() -> dict[str, int]:
    from backend.services.search import fts_index
    n = fts_index.rebuild()
    return {"indexed_rows": n}
