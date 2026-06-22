"""Additively copy MISSING wiki RAG rows from a source DB to a target DB.

Fast, non-destructive backfill: reads already-computed embeddings from a source
(e.g. the compose DB) and inserts only the documents whose ``slug`` is not yet
present on the target (e.g. remote Supabase), with their chunks + embeddings.
No TRUNCATE/DELETE — existing target rows are left untouched (idempotent via
``ON CONFLICT DO NOTHING``). Avoids re-embedding (embeddings are deterministic).

Connections via ``--source-dsn`` / ``--target-dsn`` (asyncpg URLs; passwords may
come from ``SOURCE_PGPASSWORD`` / ``TARGET_PGPASSWORD``).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

import asyncpg

BATCH = 1000


async def _executemany_batched(conn: asyncpg.Connection, sql: str, rows: list[tuple]) -> None:
    """Run executemany in bounded batches to keep statements small."""
    for start in range(0, len(rows), BATCH):
        await conn.executemany(sql, rows[start : start + BATCH])


async def copy_missing(*, source_dsn: str, target_dsn: str) -> dict:
    """Copy documents missing on the target (by slug) with chunks + embeddings."""
    src = await asyncpg.connect(dsn=source_dsn)
    tgt = await asyncpg.connect(dsn=target_dsn)
    try:
        target_slugs = {r["slug"] for r in await tgt.fetch("select slug from wiki_documents")}
        src_docs = await src.fetch(
            "select id, slug, title, category, rel_path, tags::text AS tags, summary, "
            "content_hash, source_manifest_version from wiki_documents"
        )
        missing_docs = [d for d in src_docs if d["slug"] not in target_slugs]
        if not missing_docs:
            return {
                "missing_documents": 0,
                "copied_documents": 0,
                "copied_chunks": 0,
                "copied_embeddings": 0,
                "documents_in_target": len(target_slugs),
            }
        doc_ids = [d["id"] for d in missing_docs]
        chunks = await src.fetch(
            "select id, document_id, heading, chunk_index, content, content_hash, token_count "
            "from wiki_chunks where document_id = any($1::uuid[])",
            doc_ids,
        )
        chunk_ids = [c["id"] for c in chunks]
        embeddings = await src.fetch(
            "select id, chunk_id, embedding::text AS embedding, embedding_model, "
            "embedding_dimensions from wiki_chunk_embeddings where chunk_id = any($1::uuid[])",
            chunk_ids,
        )
        async with tgt.transaction():
            await _executemany_batched(
                tgt,
                "insert into wiki_documents (id, slug, title, category, rel_path, tags, summary, "
                "content_hash, source_manifest_version) "
                "values ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9) on conflict (slug) do nothing",
                [
                    (
                        d["id"],
                        d["slug"],
                        d["title"],
                        d["category"],
                        d["rel_path"],
                        d["tags"],
                        d["summary"],
                        d["content_hash"],
                        d["source_manifest_version"],
                    )
                    for d in missing_docs
                ],
            )
            await _executemany_batched(
                tgt,
                "insert into wiki_chunks (id, document_id, heading, chunk_index, content, "
                "content_hash, token_count) values ($1,$2,$3,$4,$5,$6,$7) "
                "on conflict (id) do nothing",
                [
                    (
                        c["id"],
                        c["document_id"],
                        c["heading"],
                        c["chunk_index"],
                        c["content"],
                        c["content_hash"],
                        c["token_count"],
                    )
                    for c in chunks
                ],
            )
            await _executemany_batched(
                tgt,
                "insert into wiki_chunk_embeddings (id, chunk_id, embedding, embedding_model, "
                "embedding_dimensions) values ($1,$2,$3::extensions.vector,$4,$5) "
                "on conflict (id) do nothing",
                [
                    (
                        e["id"],
                        e["chunk_id"],
                        e["embedding"],
                        e["embedding_model"],
                        e["embedding_dimensions"],
                    )
                    for e in embeddings
                ],
            )
        return {
            "missing_documents": len(missing_docs),
            "copied_documents": len(missing_docs),
            "copied_chunks": len(chunks),
            "copied_embeddings": len(embeddings),
            "documents_in_target": await tgt.fetchval("select count(*) from wiki_documents"),
            "embeddings_in_target": await tgt.fetchval(
                "select count(*) from wiki_chunk_embeddings"
            ),
        }
    finally:
        await src.close()
        await tgt.close()


def _with_password(dsn: str, env_key: str) -> str:
    """Inject a password from env into a DSN lacking one (asyncpg uses PGPASSWORD-style)."""
    pw = os.environ.get(env_key)
    if pw and "@" in dsn and ":" not in dsn.split("@", 1)[0].split("//", 1)[-1]:
        userhost = dsn.split("//", 1)[1]
        user, rest = userhost.split("@", 1)
        return f"{dsn.split('//', 1)[0]}//{user}:{pw}@{rest}"
    return dsn


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dsn", required=True)
    parser.add_argument("--target-dsn", required=True)
    parser.add_argument("--summary", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = _with_password(args.source_dsn, "SOURCE_PGPASSWORD")
    target = _with_password(args.target_dsn, "TARGET_PGPASSWORD")
    summary = asyncio.run(copy_missing(source_dsn=source, target_dsn=target))
    if args.summary:
        path = Path(args.summary)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
