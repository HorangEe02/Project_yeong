# Supplement Brand/Product Review Bundle

Open `review-index.html` for a compact overview or `review.csv` in a
spreadsheet. Edit `decisions.todo.jsonl` after review.

Only approve rows when the manufacturer and product name were reviewed from a
safe label or catalog context. Do not use product folder names as confirmed
manufacturer without review. Do not copy raw OCR text, provider payloads, local
paths, URLs, free-text notes, or product directory literals into decisions.

After review, run `apply_supplement_brand_review_decisions.py` with the original
taxonomy staging JSONL and the edited decision JSONL to build an approved
product import manifest. The apply step still does not write to the database.
