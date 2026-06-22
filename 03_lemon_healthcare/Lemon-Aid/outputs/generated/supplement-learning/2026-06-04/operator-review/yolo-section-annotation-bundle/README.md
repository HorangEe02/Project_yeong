# Supplement YOLO Section Annotation Bundle

Open `annotation-index.html` locally to inspect materialized detail-page images.

Annotate section boxes for supplement label regions only:
`product_identity`, `supplement_facts`, `ingredient_amounts`, `intake_method`,
`precautions`, `other_ingredients`, `functional_claims`.

Use normalized `xywh` values in source-image coordinate space. Do not copy raw
OCR text, provider payloads, local paths, product folder names, or image bytes
into `annotation.todo.jsonl`.

After human review, accepted rows can be passed to
`promote_supplement_yolo_annotation_template.py`, then
`materialize_supplement_section_yolo_dataset.py`.
