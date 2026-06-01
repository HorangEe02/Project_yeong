# Feature C Release Check

- Status: `warn`
- Checked at: `2026-05-20T12:19:08.448624+00:00`
- Counts: `{"pass": 5, "warn": 2, "fail": 0, "skip": 0}`
- LLM router primary: `ollama`
- Gemini API key present: `True`
- Feature C compare mode: `False`
- Allow paid LLM override: `False`
- Content signoff path: ``

## Checks

| Status | Check | Summary | Details |
| --- | --- | --- | --- |
| `pass` | `feature_c_endpoint_surface` | Feature C OpenAPI surface has 31 onboarding, 5 scenarios, and 3 feature-flag operations | `{"counts": {"onboarding": 31, "scenarios": 5, "feature_flags": 3}}` |
| `pass` | `llm_cost_posture` | Feature C release posture avoids paid/external LLM primary and compare-mode doubling by default | `{"gemini_api_key_present": true, "llm_router_primary": "ollama", "feature_c_compare_mode": false, "allow_paid_llm": false}` |
| `pass` | `llm_failure_posture` | LLM fallback, circuit breaker, metrics, and runtime guard posture pass | `{"metadata_providers": ["gemini", "ollama"], "final_provider": "ollama", "circuit": {"gemini": {"state": "open", "failure_count": 1, "last_error_kind": "unknown"}, "ollama": {"state": "closed", "failure_count": 0, "last_error_kind": null}}, "guard_actual": {"/api/onboarding/health": false, "/api/onboarding/quick-questions": false, "/api/onboarding/chat": true, "/api/onboarding/vision/po": true}, "metrics_counters": {"gemini:chat_korean": {"success": 0, "failure": 1}, "ollama:chat_korean": {"success": 1, "failure": 0}}}` |
| `pass` | `feature_c_flag_rollout` | Feature C flags are defined, key frontend flags are consumed, and RBAC baseline is enforced | `{"flag_keys": ["cad_upload", "compare_mode", "dept_lock", "division_boundary", "inline_actions", "multi_llm", "quick_questions_v2", "work_fullscreen"], "missing_flags": [], "extra_flags": [], "missing_frontend_markers": [], "rbac_outcomes": {"l2_other_dept_forced": "품질보증팀", "l3_same_division_allowed": "영업팀", "l3_other_division_forced": "품질보증팀", "l4_other_division_allowed": "재무팀"}, "dept_lock_policy": "baseline_enforced", "division_boundary_policy": "baseline_enforced", "quick_questions_v2_policy": "ga_content_verified"}` |
| `warn` | `feature_c_content_assets` | Feature C curated content passes blocker checks with non-blocking coverage notes | `{"quick_question_departments": 30, "quick_question_count": 184, "sop_count": 8, "collaboration_count": 5, "sop_citation_count": 8, "collaboration_citation_count": 5, "warnings": ["profile_without_quick_questions=기술연구소"]}` |
| `pass` | `feature_c_docker_slim_packaging` | Cloud Run slim image packages Feature C SOP, quick-question, collaboration, guide, and glossary assets | `{"path": "Dockerfile", "full_knowledge_base_copy": true, "required_assets": {"sops": "data/knowledge_base/sops", "quick_questions": "data/knowledge_base/quick_questions", "collaboration": "data/knowledge_base/collaboration", "department_guides": "data/knowledge_base/department_guides", "glossary": "data/knowledge_base/glossary"}}` |
| `warn` | `feature_c_content_signoff` | automated content checks can pass, but department business-owner signoff remains pending | `{"required_review_scope": ["department quick questions", "SOP steps and quiz source material", "collaboration scenarios and handoff wording", "vision/document task prompts"], "signoff_path": ""}` |

## Content Review Checklist

- Department quick questions: confirm labels, wording, level visibility, and owner department fit.
- SOPs and quizzes: confirm step order, safety warnings, customer/OEM wording, and quiz answers.
- Collaboration scenarios: confirm requesting department, handoff artifacts, deadlines, and related SOP links.
- Vision/document tasks: confirm extracted fields and downstream routing match department workflows.

## References

- https://docs.ollama.com/api/chat
- https://ai.google.dev/api
- https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events
- https://fastapi.tiangolo.com/tutorial/testing/
