# AJIN Supabase pgvector Prerequisite Report

- Generated: `2026-05-20T17:12:36.088205+00:00`
- Overall status: `pass`

## Checks

### local_pgvector_migration — pass

Supabase pgvector migration defines backend-only vector store schema

```json
{
  "embedding_dim": 1024,
  "path": "supabase/migrations/20260520161230_add_pgvector_search_store.sql",
  "private_functions": [
    "match_document_chunks",
    "hybrid_search_document_chunks",
    "match_employee_profiles",
    "match_rag_chunks"
  ],
  "tables": [
    "document_chunks",
    "document_embeddings",
    "employee_embeddings",
    "rag_collections",
    "rag_chunks",
    "rag_chunk_embeddings"
  ]
}
```

### local_chroma_inventory — pass

Local Chroma/BM25 inventory captured for pgvector migration

```json
{
  "bm25_chunk_count": 546,
  "bm25_status": "pass",
  "chroma_counts": {
    "document_chroma": null,
    "employee_chroma": 333
  },
  "chroma_errors": {
    "document_chroma": "NotFoundError"
  },
  "vectorstore_exists": true
}
```

### remote_pgvector_posture — skip

Remote pgvector check skipped by option

### embedding_dimension_smoke — skip

Embedding smoke skipped; pass --embedding-smoke to call Ollama

```json
{
  "expected_dim": 1024,
  "model": "bge-m3"
}
```

## References

- https://supabase.com/docs/guides/ai
- https://supabase.com/docs/guides/ai/semantic-search
- https://supabase.com/docs/guides/ai/vector-columns
- https://supabase.com/docs/guides/ai/vector-indexes
- https://supabase.com/docs/guides/api/securing-your-api
- https://supabase.com/changelog?tags=database
