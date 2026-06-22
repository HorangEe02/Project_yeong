# Supplement PII Screening Review Bundle

Open `review-index.html` locally and inspect each materialized review image.

Edit `decisions.todo.jsonl` only after review. A row can be cleared only when
no face, name, contact detail, address, order detail, or other personal data is
visible. Do not copy raw label text or review text into the decision file.

After completing decisions, run `apply_supplement_review_pii_screening_decisions.py`
against the original candidate manifest and the edited decision JSONL.
