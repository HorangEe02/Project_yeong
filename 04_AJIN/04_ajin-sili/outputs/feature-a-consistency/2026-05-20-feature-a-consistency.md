# Feature A Consistency Check

- Status: `warn`
- Checked at: `2026-05-20T07:10:35.144645+00:00`
- Counts: `{"pass": 5, "warn": 1, "fail": 0, "skip": 0}`
- Employees DB: `data/employees.db`
- Vectorstore: `vectorstore`
- APP_DB_BACKEND: `postgres`

## Checks

| Status | Check | Summary | Details |
| --- | --- | --- | --- |
| `pass` | `sqlite_employee_source` | employees.db has required Feature A lineage columns | `{"total": 334, "missing_columns": []}` |
| `pass` | `real_active_employee_set` | 4 real active employees found | `{"real_active_count": 4, "sample_ids": ["ERP-0001", "ERP-0002", "ERP-0003", "ERP-0004"]}` |
| `pass` | `fts5_employee_coverage` | employees_fts covers all real active employees | `{"fts_total": 334, "real_active_count": 4}` |
| `warn` | `employee_chroma_coverage` | Chroma includes non-real-active employee profiles | `{"collection_count": 333, "real_active_count": 4, "extra_count": 329, "extra_sample": ["EMP-0001", "EMP-0002", "EMP-0003", "EMP-0004", "EMP-0005", "EMP-0006", "EMP-0007", "EMP-0008", "EMP-0009", "EMP-0010", "EMP-0011", "EMP-0012", "EMP-0013", "EMP-0014", "EMP-0015", "EMP-0016", "EMP-0017", "EMP-0018", "EMP-0019", "EMP-0020", "EMP-0021", "EMP-0022", "EMP-0023", "EMP-0024", "EMP-0025"]}` |
| `pass` | `postgres_employee_mirror` | Postgres employee mirror covers all real active employees | `{"postgres_active_count": 4, "real_active_count": 4}` |
| `pass` | `document_chroma_bm25_consistency` | document Chroma and BM25 chunk counts match | `{"bm25_chunks": 546, "chroma_count": 546}` |

## References

- https://docs.trychroma.com/reference/python/collection
- https://www.sqlite.org/fts5.html
- https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#insert-on-conflict-upsert
- https://supabase.com/docs/guides/api/securing-your-api
