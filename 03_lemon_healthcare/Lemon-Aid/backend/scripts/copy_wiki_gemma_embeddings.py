"""Additively copy the second-model (EmbeddingGemma) wiki embeddings between DBs.

Backfills ``wiki_chunk_embeddings_gemma`` on a target DB from a source DB without
re-embedding. Matches by ``wiki_chunks.content_hash`` rather than ``chunk_id`` so it
works across databases that were ingested independently (their chunk UUIDs differ):
identical chunk content yields an identical embedding, so the source vector for a
content hash is valid for any target chunk with the same hash.

Non-destructive: only inserts embeddings for target chunks that currently lack a
Gemma embedding (``ON CONFLICT (chunk_id, embedding_model) DO NOTHING``). No
TRUNCATE/DELETE — safe for production targets.

Connections via ``--source-dsn`` / ``--target-dsn`` (asyncpg URLs; passwords may
come from ``SOURCE_PGPASSWORD`` / ``TARGET_PGPASSWORD``).

References:
    https://github.com/pgvector/pgvector
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import asyncpg

BATCH = 1000
GEMMA_TABLE = "wiki_chunk_embeddings_gemma"


async def _executemany_batched(conn: asyncpg.Connection, sql: str, rows: list[tuple]) -> None:
    """Run executemany in bounded batches to keep statements small."""
    for start in range(0, len(rows), BATCH):
        await conn.executemany(sql, rows[start : start + BATCH])


async def copy_gemma(*, source_dsn: str, target_dsn: str, model: str) -> dict:
    """Copy missing Gemma embeddings from source to target, matched by content hash.

    Args:
        source_dsn: asyncpg URL of the source DB (already has Gemma embeddings).
        target_dsn: asyncpg URL of the target DB to backfill.
        model: Embedding model label stored in ``embedding_model``.

    Returns:
        A count-only summary of the backfill.
    """
    src = await asyncpg.connect(dsn=source_dsn)
    tgt = await asyncpg.connect(dsn=target_dsn)
    try:
        source_rows = await src.fetch(
            f"""
            select c.content_hash as content_hash, e.embedding::text as embedding,
                   e.embedding_dimensions as embedding_dimensions
            from {GEMMA_TABLE} e
            join wiki_chunks c on c.id = e.chunk_id
            where e.embedding_model = $1
            """,
            model,
        )
        by_hash: dict[str, tuple[str, int]] = {}
        for row in source_rows:
            # Identical content -> identical embedding; first occurrence wins.
            by_hash.setdefault(row["content_hash"], (row["embedding"], row["embedding_dimensions"]))
        target_chunks = await tgt.fetch(
            f"""
            select c.id as id, c.content_hash as content_hash
            from wiki_chunks c
            where not exists (
                select 1 from {GEMMA_TABLE} g
                where g.chunk_id = c.id and g.embedding_model = $1
            )
            """,
            model,
        )
        to_insert: list[tuple] = []
        unmatched = 0
        for chunk in target_chunks:
            match = by_hash.get(chunk["content_hash"])
            if match is None:
                unmatched += 1
                continue
            embedding, dimensions = match
            to_insert.append((uuid4(), chunk["id"], embedding, model, dimensions))
        if to_insert:
            async with tgt.transaction():
                await _executemany_batched(
                    tgt,
                    f"insert into {GEMMA_TABLE} "
                    "(id, chunk_id, embedding, embedding_model, embedding_dimensions) "
                    "values ($1,$2,$3::extensions.vector,$4,$5) "
                    "on conflict (chunk_id, embedding_model) do nothing",
                    to_insert,
                )
        return {
            "model": model,
            "source_embeddings": len(source_rows),
            "source_distinct_hashes": len(by_hash),
            "target_chunks_missing_gemma": len(target_chunks),
            "matched_for_insert": len(to_insert),
            "unmatched_target_chunks": unmatched,
            "target_gemma_after": await tgt.fetchval(
                f"select count(*) from {GEMMA_TABLE} where embedding_model=$1", model
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
    parser.add_argument("--model", default="embeddinggemma")
    parser.add_argument("--summary", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source = _with_password(args.source_dsn, "SOURCE_PGPASSWORD")
    target = _with_password(args.target_dsn, "TARGET_PGPASSWORD")
    summary = asyncio.run(copy_gemma(source_dsn=source, target_dsn=target, model=args.model))
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
