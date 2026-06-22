# Supplement OCR Gate Report

- Gate mode: `report_only`
- Gate status: `warning`
- Release blocked: `False`
- Fixtures: `3`
- Provisional expected fixtures: `3`
- Interpretation: Metrics are redacted fixture observations. Provisional Google Vision auto-seeded expected snapshots are agreement baselines, not official OCR accuracy claims; the seed provider is excluded from self-exact field metrics.
- Expected sources: `{'pending_google_vision_auto_seed': 3}`

## Provider Metrics

| Provider | Completed | Not run | Errors | Text non-empty | Parser success | Ingredient exact | Amount exact | Unit exact | Layout | Evidence grounded | Self-seed excluded | Avg latency ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| paddleocr_local | 3 | 0 | 0 | 1.0 | 1.0 | None | None | None | 1.0 | 1.0 | 0 | 8103.0 |

## Reasons

- `baseline_fixture_count_below_minimum`
