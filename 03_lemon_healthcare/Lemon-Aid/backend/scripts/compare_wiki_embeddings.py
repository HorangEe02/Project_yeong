"""A/B compare WIKI semantic retrieval across embedding models.

For a set of representative queries, embeds each query with every registered model
(``bge-m3`` 1024-dim and ``embeddinggemma`` 768-dim), runs cosine top-K against the
model's own embedding table, and reports the results side by side plus a small
quantitative summary focused on how well each model surfaces curated, entity-linked
hub pages (the pages mapped to DB entities via ``entity_wiki_links``).

Each model uses its documented query prompt (from
``src.services.wiki_embedding_targets``), matching how its documents were embedded
at ingestion, so the comparison reflects each model used as intended.

Read-only. Connection via ``--dsn`` (asyncpg URL; password may come from the
``PGPASSWORD`` env var). Defaults target the local Supabase stack.

References:
    https://github.com/pgvector/pgvector
    https://github.com/ollama/ollama/blob/main/docs/api.md#generate-embeddings
"""

from __future__ import annotations

import argparse
import asyncio
import json
import urllib.error
import urllib.request
from pathlib import Path

import asyncpg
from src.services.wiki_embedding_targets import WikiEmbeddingTarget, get_target, known_models

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_DSN = "postgresql://postgres@127.0.0.1:56322/postgres"
DEFAULT_TOP_K = 5
EMBED_TIMEOUT_SECONDS = 60

# Representative nutrition queries spanning supplements, RDA/UL limits, cuisine
# sodium, and nutrient interactions.
DEFAULT_QUERIES = (
    "오메가3 효능",
    "마그네슘 권장량과 UL",
    "한식 나트륨",
    "비타민D 칼슘 상호작용",
)


def _embed(query: str, *, ollama_url: str, target: WikiEmbeddingTarget) -> list[float]:
    """Embed a query with one model, applying its documented query prompt.

    Args:
        query: Raw query text.
        ollama_url: Ollama base URL.
        target: Embedding target (model, dimension, query prompt).

    Returns:
        The embedding vector.

    Raises:
        ValueError: If the embedding dimension does not match the target.
        RuntimeError: If the embeddings request fails.
    """
    payload = json.dumps({"model": target.model, "prompt": target.format_query(query)}).encode(
        "utf-8"
    )
    req = urllib.request.Request(
        f"{ollama_url}/api/embeddings",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=EMBED_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"ollama embeddings failed for {target.model}: {exc}") from exc
    vector = data.get("embedding") or []
    if len(vector) != target.dimensions:
        raise ValueError(
            f"embedding dim {len(vector)} != expected {target.dimensions} for {target.model}"
        )
    return [float(x) for x in vector]


def _vector_literal(vector: list[float]) -> str:
    """Return a pgvector text literal like ``[0.1,0.2,...]``."""
    return "[" + ",".join(repr(round(x, 6)) for x in vector) + "]"


async def _search(
    conn: asyncpg.Connection,
    *,
    target: WikiEmbeddingTarget,
    embedding_literal: str,
    top_k: int,
    entity_slugs: set[str],
) -> list[dict[str, object]]:
    """Run cosine top-K retrieval against one model's embedding table.

    Args:
        conn: Open asyncpg connection.
        target: Embedding target selecting the table and model.
        embedding_literal: pgvector text literal of the query embedding.
        top_k: Number of nearest chunks to return.
        entity_slugs: Slugs linked to DB entities, used to flag curated hits.

    Returns:
        Ranked hits with slug, title, heading, cosine score, and entity flag.
    """
    rows = await conn.fetch(
        f"""
        SELECT d.slug AS slug, d.title AS title, c.heading AS heading,
               (e.embedding OPERATOR(extensions.<=>) $1::extensions.vector) AS distance
        FROM {target.table} AS e
        JOIN wiki_chunks AS c ON c.id = e.chunk_id
        JOIN wiki_documents AS d ON d.id = c.document_id
        WHERE e.embedding_model = $2
        ORDER BY e.embedding OPERATOR(extensions.<=>) $1::extensions.vector ASC
        LIMIT $3
        """,
        embedding_literal,
        target.model,
        top_k,
    )
    return [
        {
            "rank": index + 1,
            "slug": row["slug"],
            "title": row["title"],
            "heading": row["heading"],
            "score": round(1.0 - float(row["distance"]), 4),
            "is_entity": row["slug"] in entity_slugs,
        }
        for index, row in enumerate(rows)
    ]


def _first_entity_rank(hits: list[dict[str, object]], top_k: int) -> int:
    """Return the 1-based rank of the first entity-linked hit, or ``top_k + 1``.

    Args:
        hits: Ranked retrieval hits (each carries an ``is_entity`` flag).
        top_k: Result-set size used as the "not found" sentinel.

    Returns:
        Rank of the first curated/entity-linked hit (lower is better), or
        ``top_k + 1`` when none of the top-K hits are entity-linked.
    """
    for hit in hits:
        if hit["is_entity"]:
            return int(hit["rank"])
    return top_k + 1


async def compare(
    *, dsn: str, queries: tuple[str, ...], ollama_url: str, top_k: int
) -> dict[str, object]:
    """Compare retrieval across all registered models for the given queries.

    Args:
        dsn: asyncpg connection URL.
        queries: Representative query strings.
        ollama_url: Ollama base URL.
        top_k: Number of nearest chunks to compare per query.

    Returns:
        A report with per-query side-by-side hits and an aggregate summary.
    """
    models = known_models()
    targets = {model: get_target(model) for model in models}
    conn = await asyncpg.connect(dsn=dsn)
    try:
        entity_slugs = {
            row["wiki_slug"]
            for row in await conn.fetch("select distinct wiki_slug from entity_wiki_links")
        }
        coverage = {
            model: await conn.fetchval(
                f"select count(*) from {targets[model].table} where embedding_model=$1", model
            )
            for model in models
        }
        per_query: list[dict[str, object]] = []
        entity_rank_totals = dict.fromkeys(models, 0)
        entity_hit_totals = dict.fromkeys(models, 0)
        overlap_total = 0
        for query in queries:
            per_model_hits: dict[str, list[dict[str, object]]] = {}
            for model in models:
                embedding = _embed(query, ollama_url=ollama_url, target=targets[model])
                per_model_hits[model] = await _search(
                    conn,
                    target=targets[model],
                    embedding_literal=_vector_literal(embedding),
                    top_k=top_k,
                    entity_slugs=entity_slugs,
                )
            slug_sets = [{h["slug"] for h in hits} for hits in per_model_hits.values()]
            overlap = len(set.intersection(*slug_sets)) if len(slug_sets) > 1 else 0
            overlap_total += overlap
            ranks: dict[str, int] = {}
            for model in models:
                rank = _first_entity_rank(per_model_hits[model], top_k)
                ranks[model] = rank
                entity_rank_totals[model] += rank
                entity_hit_totals[model] += sum(1 for h in per_model_hits[model] if h["is_entity"])
            per_query.append(
                {
                    "query": query,
                    "hits": per_model_hits,
                    "overlap_at_k": overlap,
                    "first_entity_rank": ranks,
                }
            )
        query_count = len(queries) or 1
        summary = {
            "models": list(models),
            "top_k": top_k,
            "embeddings_in_db": coverage,
            "entity_linked_slug_count": len(entity_slugs),
            "mean_overlap_at_k": round(overlap_total / query_count, 3),
            "mean_first_entity_rank": {
                model: round(entity_rank_totals[model] / query_count, 3) for model in models
            },
            "entity_hits_in_topk": entity_hit_totals,
        }
    finally:
        await conn.close()
    return {"summary": summary, "queries": per_query}


def _print_report(report: dict[str, object]) -> None:
    """Print a human-readable side-by-side comparison and aggregate summary."""
    summary = report["summary"]
    models = summary["models"]
    print("=" * 78)
    print("WIKI embedding A/B comparison")
    print(f"  models             : {', '.join(models)}")
    print(f"  embeddings in db   : {summary['embeddings_in_db']}")
    print(f"  entity-linked slugs: {summary['entity_linked_slug_count']}")
    print("=" * 78)
    for entry in report["queries"]:
        print(f"\n■ query: {entry['query']}   (overlap@k={entry['overlap_at_k']})")
        for model in models:
            rank = entry["first_entity_rank"][model]
            print(f"  -- {model}  (first entity-linked rank: {rank})")
            hits = entry["hits"][model]
            if not hits:
                print("      (no embeddings for this model)")
                continue
            for hit in hits:
                marker = " [ENTITY]" if hit["is_entity"] else ""
                heading = f" > {hit['heading']}" if hit["heading"] else ""
                print(f"      {hit['rank']}. {hit['score']:>7}  {hit['slug']}{heading}{marker}")
    print("\n" + "-" * 78)
    print("SUMMARY (lower mean_first_entity_rank = surfaces curated/entity pages better)")
    print(f"  mean_overlap_at_k     : {summary['mean_overlap_at_k']}")
    print(f"  mean_first_entity_rank: {summary['mean_first_entity_rank']}")
    print(f"  entity_hits_in_topk   : {summary['entity_hits_in_topk']}")
    print("-" * 78)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default=DEFAULT_DSN)
    parser.add_argument("--ollama-url", default=DEFAULT_OLLAMA_URL)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--query",
        action="append",
        default=None,
        help="Override the representative query set (repeatable).",
    )
    parser.add_argument("--summary", type=Path, default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    queries = tuple(args.query) if args.query else DEFAULT_QUERIES
    report = asyncio.run(
        compare(dsn=args.dsn, queries=queries, ollama_url=args.ollama_url, top_k=args.top_k)
    )
    _print_report(report)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
