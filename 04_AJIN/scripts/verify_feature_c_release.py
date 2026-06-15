#!/usr/bin/env python3
"""Verify Feature C AI work assistant release posture.

The verifier is secret-safe. It checks endpoint coverage, paid LLM routing
posture, LLM fallback/circuit behavior, feature-flag rollout wiring, and
curated onboarding content integrity without printing API keys or credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tempfile
from collections.abc import AsyncIterator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DOC_REFERENCES = (
    "https://docs.ollama.com/api/chat",
    "https://ai.google.dev/api",
    "https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events",
    "https://fastapi.tiangolo.com/tutorial/testing/",
)

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head"}
EXPECTED_ENDPOINT_COUNTS = {
    "onboarding": 31,
    "scenarios": 5,
    "feature_flags": 3,
}
REQUIRED_ENDPOINTS: Mapping[str, set[str]] = {
    "/api/onboarding/chat": {"post"},
    "/api/onboarding/health": {"get"},
    "/api/onboarding/quick-questions": {"get"},
    "/api/onboarding/chat/vision": {"post"},
    "/api/onboarding/upload": {"post"},
    "/api/onboarding/sop/list": {"get"},
    "/api/onboarding/sop/{sop_id}": {"get"},
    "/api/onboarding/sop/{sop_id}/quiz": {"get"},
    "/api/onboarding/scenarios/match": {"post"},
    "/api/onboarding/actions/match": {"post"},
    "/api/onboarding/badges/me": {"get"},
    "/api/onboarding/leaderboard/{dept}": {"get"},
    "/api/onboarding/sop/progress": {"post"},
    "/api/onboarding/quiz/result": {"post"},
    "/api/scenarios": {"get"},
    "/api/scenarios/favorites": {"get"},
    "/api/scenarios/{scenario_id}/favorite": {"post", "put", "delete"},
    "/api/feature-flags/c": {"get"},
}
REQUIRED_VISION_TASKS = {
    "business-card",
    "rfq",
    "defect",
    "msds-label",
    "receipt",
    "po",
    "incident",
    "cad-verify",
    "5s",
    "error-log",
    "inventory-receive",
    "certificate",
}
REQUIRED_DOCUMENT_TASKS = {"contract", "resume", "financial-statement", "esg"}
EXPECTED_FEATURE_C_FLAGS = {
    "multi_llm",
    "compare_mode",
    "dept_lock",
    "division_boundary",
    "work_fullscreen",
    "quick_questions_v2",
    "inline_actions",
    "cad_upload",
    "analyzers_enabled",
}
QUESTION_REQUIRED_FIELDS = {"id", "label", "promptText", "category", "min_level", "max_level"}
QUESTION_CATEGORIES = {"scenario", "action", "sop", "general"}
SOP_REQUIRED_FIELDS = {
    "sop_id",
    "title",
    "department",
    "category",
    "steps",
    "citation_id",
    "owner_department",
    "reviewed_at",
    "effective_date",
    "version",
    "status",
}
SOP_STEP_REQUIRED_FIELDS = {"step_number", "title", "description", "checklist"}
COLLAB_REQUIRED_FIELDS = {
    "id",
    "trigger_keywords",
    "situation",
    "requesting_dept",
    "my_actions",
    "hand_off_to",
    "hand_off_items",
    "deadline_info",
    "citation_id",
}
ENV_POSTURE_KEYS = ("GEMINI_API_KEY", "LLM_ROUTER_PRIMARY", "FEATURE_C_COMPARE_MODE")
FEATURE_C_DOCKER_REQUIRED_ASSETS = {
    "sops": "data/knowledge_base/sops",
    "quick_questions": "data/knowledge_base/quick_questions",
    "collaboration": "data/knowledge_base/collaboration",
    "department_guides": "data/knowledge_base/department_guides",
    "glossary": "data/knowledge_base/glossary",
}


@dataclass(frozen=True)
class CheckResult:
    """Single Feature C release check result.

    Args:
        name: Stable machine-readable check name.
        status: One of pass, warn, fail, or skip.
        summary: Human-readable secret-safe summary.
        details: Optional secret-safe metadata.
    """

    name: str
    status: str
    summary: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable check.

        Returns:
            dict[str, Any]: Result fields for reports.
        """

        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class FeatureCConfig:
    """Runtime configuration for the Feature C verifier.

    Args:
        root: Repository root.
        openapi_path: OpenAPI JSON path.
        strict: Whether fail checks should return a non-zero exit code.
        content_signoff_path: Optional business-owner content review signoff file.
        allow_paid_llm: Whether paid/external LLM primary or compare mode is allowed.
    """

    root: Path = ROOT
    openapi_path: Path = ROOT / "docs" / "openapi.json"
    strict: bool = False
    content_signoff_path: Path | None = None
    allow_paid_llm: bool = False


class _MockProvider:
    """Minimal in-memory LLM provider for verifier-only routing checks."""

    def __init__(
        self,
        name: str,
        *,
        fail: bool = False,
        tokens: Iterable[str] = ("ok",),
    ) -> None:
        self.name = name
        self.fail = fail
        self.tokens = list(tokens)
        self.call_count = 0

    async def health_check(self) -> bool:
        """Return provider health.

        Returns:
            bool: False when this mock is configured to fail.
        """

        return not self.fail

    async def stream(self, req: Mapping[str, Any], model: str) -> AsyncIterator[dict[str, Any]]:
        """Yield token events or raise a deterministic failure.

        Args:
            req: Stream request payload.
            model: Model id selected by the router.

        Yields:
            dict[str, Any]: Stream events.

        Raises:
            RuntimeError: When configured as failing.
        """

        self.call_count += 1
        if self.fail:
            raise RuntimeError(f"{self.name} simulated failure")
        for token in self.tokens:
            yield {"type": "token", "content": token, "metadata": None}

    async def embed(self, text: str, model: str) -> list[float]:
        """Return a small deterministic embedding.

        Args:
            text: Text to embed.
            model: Model id.

        Returns:
            list[float]: Deterministic embedding vector.
        """

        return [0.1, 0.2, 0.3]

    def supports_mode(self, mode: Any) -> bool:
        """Return whether the mode is supported.

        Args:
            mode: LLM mode.

        Returns:
            bool: Always true for verifier mocks.
        """

        return True


@contextmanager
def _temporary_env(updates: Mapping[str, str | None]) -> Iterator[None]:
    """Temporarily update environment variables.

    Args:
        updates: Environment variable updates. ``None`` unsets a variable.

    Yields:
        None: Control while the temporary environment is active.
    """

    old_values = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _snapshot_env(keys: Iterable[str]) -> dict[str, str | None]:
    """Capture selected environment values.

    Args:
        keys: Environment variable names.

    Returns:
        dict[str, str | None]: Current values, with ``None`` for missing keys.
    """

    return {key: os.environ.get(key) for key in keys}


def _restore_env(snapshot: Mapping[str, str | None]) -> None:
    """Restore selected environment values.

    Args:
        snapshot: Environment snapshot from ``_snapshot_env``.
    """

    for key, value in snapshot.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _load_release_dotenv(root: Path) -> bool:
    """Load local dotenv files exactly once for CLI release posture checks.

    Args:
        root: Repository root.

    Returns:
        bool: True when at least one dotenv file was loaded.
    """

    try:
        from dotenv import load_dotenv
    except Exception:
        return False

    loaded = False
    for name in (".env", ".env.local"):
        path = root / name
        if path.exists():
            loaded = bool(load_dotenv(path, override=False)) or loaded
    return loaded


def _display_path(root: Path, path: Path) -> str:
    """Return a repository-relative path when possible.

    Args:
        root: Repository root.
        path: Path to display.

    Returns:
        str: Secret-safe display path.
    """

    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _truthy(value: str | None) -> bool:
    """Return common environment truthiness.

    Args:
        value: Environment value.

    Returns:
        bool: True for 1/true/yes/on.
    """

    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _load_json(path: Path) -> Any:
    """Load JSON from disk.

    Args:
        path: JSON file path.

    Returns:
        Any: Parsed JSON payload.
    """

    return json.loads(path.read_text(encoding="utf-8"))


def _operation_counts(paths: Mapping[str, Any]) -> dict[str, int]:
    """Count Feature C operations by path group.

    Args:
        paths: OpenAPI paths mapping.

    Returns:
        dict[str, int]: Operation counts for Feature C path groups.
    """

    counts = {"onboarding": 0, "scenarios": 0, "feature_flags": 0}
    for path, methods in paths.items():
        if not isinstance(methods, Mapping):
            continue
        operation_count = sum(1 for method in methods if method.lower() in HTTP_METHODS)
        if path.startswith("/api/onboarding/"):
            counts["onboarding"] += operation_count
        elif path == "/api/scenarios" or path.startswith("/api/scenarios/"):
            counts["scenarios"] += operation_count
        elif path.startswith("/api/feature-flags/"):
            counts["feature_flags"] += operation_count
    return counts


def verify_endpoint_surface(config: FeatureCConfig) -> CheckResult:
    """Verify the OpenAPI Feature C endpoint surface.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Endpoint surface posture.
    """

    try:
        openapi = _load_json(config.openapi_path)
    except Exception as exc:
        return CheckResult(
            "feature_c_endpoint_surface",
            "fail",
            "OpenAPI document could not be loaded",
            {"path": _display_path(config.root, config.openapi_path), "error": type(exc).__name__},
        )

    paths = openapi.get("paths", {})
    if not isinstance(paths, Mapping):
        return CheckResult(
            "feature_c_endpoint_surface",
            "fail",
            "OpenAPI document does not contain a paths mapping",
        )

    counts = _operation_counts(paths)
    missing_counts = {
        key: {"expected": expected, "actual": counts.get(key, 0)}
        for key, expected in EXPECTED_ENDPOINT_COUNTS.items()
        if counts.get(key, 0) != expected
    }
    missing_required: list[str] = []
    for path, expected_methods in REQUIRED_ENDPOINTS.items():
        methods = paths.get(path)
        if not isinstance(methods, Mapping):
            missing_required.append(f"{path}:missing_path")
            continue
        actual_methods = {method.lower() for method in methods if method.lower() in HTTP_METHODS}
        missing_methods = sorted(expected_methods - actual_methods)
        if missing_methods:
            missing_required.append(f"{path}:missing_methods={','.join(missing_methods)}")

    missing_vision = [
        task for task in sorted(REQUIRED_VISION_TASKS)
        if f"/api/onboarding/vision/{task}" not in paths
    ]
    missing_documents = [
        task for task in sorted(REQUIRED_DOCUMENT_TASKS)
        if f"/api/onboarding/document/{task}" not in paths
    ]

    if missing_counts or missing_required or missing_vision or missing_documents:
        return CheckResult(
            "feature_c_endpoint_surface",
            "fail",
            "Feature C OpenAPI endpoint surface is incomplete",
            {
                "counts": counts,
                "missing_counts": missing_counts,
                "missing_required": missing_required,
                "missing_vision": missing_vision,
                "missing_documents": missing_documents,
            },
        )

    return CheckResult(
        "feature_c_endpoint_surface",
        "pass",
        "Feature C OpenAPI surface has 31 onboarding, 5 scenarios, and 3 feature-flag operations",
        {"counts": counts},
    )


def verify_llm_cost_posture(config: FeatureCConfig, env: Mapping[str, str] | None = None) -> CheckResult:
    """Verify paid/external LLM posture for Feature C release.

    Args:
        config: Verifier config.
        env: Environment mapping for tests or runtime.

    Returns:
        CheckResult: Cost posture.
    """

    env = env or os.environ
    gemini_present = bool((env.get("GEMINI_API_KEY") or "").strip())
    primary = (env.get("LLM_ROUTER_PRIMARY") or "gemini").strip().lower()
    compare_mode_enabled = _truthy(env.get("FEATURE_C_COMPARE_MODE"))

    blockers: list[str] = []
    if gemini_present and primary != "ollama":
        blockers.append("gemini_key_present_with_non_ollama_primary")
    if compare_mode_enabled:
        blockers.append("feature_c_compare_mode_enabled")

    details = {
        "gemini_api_key_present": gemini_present,
        "llm_router_primary": primary or "gemini",
        "feature_c_compare_mode": compare_mode_enabled,
        "allow_paid_llm": config.allow_paid_llm,
    }
    if blockers and not config.allow_paid_llm:
        return CheckResult(
            "llm_cost_posture",
            "fail",
            "paid/external LLM primary or compare mode is enabled without explicit release override",
            {**details, "blockers": blockers},
        )
    if blockers:
        return CheckResult(
            "llm_cost_posture",
            "warn",
            "paid/external LLM posture is explicitly allowed for this run",
            {**details, "allowed_risks": blockers},
        )
    return CheckResult(
        "llm_cost_posture",
        "pass",
        "Feature C release posture avoids paid/external LLM primary and compare-mode doubling by default",
        details,
    )


async def _collect_stream_events(router: Any, prompt: str, mode: Any) -> list[dict[str, Any]]:
    """Collect router stream events.

    Args:
        router: LLMRouter instance.
        prompt: Prompt text.
        mode: LLM mode.

    Returns:
        list[dict[str, Any]]: Stream events.
    """

    return [event async for event in router.stream(prompt, mode=mode)]


def verify_llm_failure_posture(config: FeatureCConfig) -> CheckResult:
    """Verify LLM fallback, circuit breaker, metrics, and runtime guard posture.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: LLM failure posture.
    """

    env_snapshot = _snapshot_env(ENV_POSTURE_KEYS)
    try:
        try:
            from backend.main import OllamaHealthMiddleware
            from core.llm_health import HealthRegistry
            from core.llm_router import LLMRouter
            from core.llm_types import LLMMode

            with tempfile.TemporaryDirectory(prefix="feature-c-llm-") as tmp:
                with _temporary_env({
                    "LLM_METRICS_LOG_PATH": str(Path(tmp) / "llm_metrics.log"),
                    "LLM_ROUTER_FALLBACK_ENABLED": "true",
                    "LLM_ROUTER_PRIMARY": "gemini",
                }):
                    router = LLMRouter(
                        providers={
                            "gemini": _MockProvider("gemini", fail=True),
                            "ollama": _MockProvider("ollama", tokens=("fallback-ok",)),
                        }
                    )
                    router.health = HealthRegistry(threshold=1, recovery_sec=60)
                    events = asyncio.run(_collect_stream_events(router, "hello", LLMMode.CHAT_KOREAN))
                    metadata_providers = [
                        event.get("metadata", {}).get("provider")
                        for event in events
                        if event.get("type") == "metadata"
                    ]
                    done = [event for event in events if event.get("type") == "done"]
                    circuit = router.health.snapshot()
                    metrics = router.metrics.snapshot()

                with _temporary_env({"LLM_METRICS_LOG_PATH": str(Path(tmp) / "all_fail.log")}):
                    all_fail_router = LLMRouter(
                        providers={
                            "gemini": _MockProvider("gemini", fail=True),
                            "ollama": _MockProvider("ollama", fail=True),
                        }
                    )
                    error_events = asyncio.run(
                        _collect_stream_events(all_fail_router, "hello", LLMMode.CHAT_KOREAN)
                    )

            guard_expected = {
                "/api/onboarding/health": False,
                "/api/onboarding/quick-questions": False,
                "/api/onboarding/chat": True,
                "/api/onboarding/vision/po": True,
            }
            guard_actual = {
                path: OllamaHealthMiddleware._requires_ollama(path)
                for path in guard_expected
            }
        except Exception as exc:
            return CheckResult(
                "llm_failure_posture",
                "fail",
                "LLM failure posture smoke raised unexpectedly",
                {"error": type(exc).__name__},
            )

        failures: list[str] = []
        if metadata_providers[:2] != ["gemini", "ollama"]:
            failures.append("fallback_chain_not_observed")
        if not done or done[-1].get("metadata", {}).get("final_provider") != "ollama":
            failures.append("ollama_fallback_not_final")
        if circuit.get("gemini", {}).get("state") != "open":
            failures.append("gemini_circuit_not_open_after_threshold")
        if metrics.get("counters", {}).get("gemini:chat_korean", {}).get("failure", 0) < 1:
            failures.append("gemini_failure_metric_missing")
        if metrics.get("counters", {}).get("ollama:chat_korean", {}).get("success", 0) < 1:
            failures.append("ollama_success_metric_missing")
        if not any(event.get("type") == "error" for event in error_events):
            failures.append("all_provider_failure_error_event_missing")
        if guard_actual != guard_expected:
            failures.append("ollama_runtime_guard_mapping_changed")

        details = {
            "metadata_providers": metadata_providers,
            "final_provider": done[-1].get("metadata", {}).get("final_provider") if done else "",
            "circuit": circuit,
            "guard_actual": guard_actual,
            "metrics_counters": metrics.get("counters", {}),
        }
        if failures:
            return CheckResult(
                "llm_failure_posture",
                "fail",
                "LLM fallback/circuit/metrics or runtime guard posture is not release-safe",
                {**details, "failures": failures},
            )
        return CheckResult(
            "llm_failure_posture",
            "pass",
            "LLM fallback, circuit breaker, metrics, and runtime guard posture pass",
            details,
        )
    finally:
        _restore_env(env_snapshot)


def verify_feature_flag_rollout(config: FeatureCConfig) -> CheckResult:
    """Verify Feature C flag definitions and rollout wiring.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Feature flag posture.
    """

    try:
        from backend.routers.onboarding import _resolve_effective_department
        from core.feature_flags import feature_c_flags_dict
    except Exception as exc:
        return CheckResult(
            "feature_c_flag_rollout",
            "fail",
            "Feature C flag or RBAC modules could not be imported",
            {"error": type(exc).__name__},
        )

    with _temporary_env({f"FEATURE_C_{name.upper()}": None for name in EXPECTED_FEATURE_C_FLAGS}):
        flag_keys = set(feature_c_flags_dict())
    missing_flags = sorted(EXPECTED_FEATURE_C_FLAGS - flag_keys)
    extra_flags = sorted(flag_keys - EXPECTED_FEATURE_C_FLAGS)

    frontend_chat = config.root / "frontend" / "src" / "routes" / "chat.tsx"
    frontend_onboarding = config.root / "frontend" / "src" / "routes" / "onboarding.tsx"
    attachment_tray = config.root / "frontend" / "src" / "components" / "chat" / "AttachmentTray.tsx"
    chat_text = frontend_chat.read_text(encoding="utf-8") if frontend_chat.exists() else ""
    onboarding_text = frontend_onboarding.read_text(encoding="utf-8") if frontend_onboarding.exists() else ""
    tray_text = attachment_tray.read_text(encoding="utf-8") if attachment_tray.exists() else ""

    required_source_markers = {
        "multi_llm": "featureCFlags.multi_llm",
        "compare_mode": "featureCFlags.compare_mode",
        "work_fullscreen": "featureCFlags.work_fullscreen",
        "cad_upload": "flags.cad_upload",
        "analyzers_enabled": "featureCFlags.analyzers_enabled",
    }
    missing_markers = [
        name for name, marker in required_source_markers.items()
        if marker not in (chat_text + "\n" + tray_text + "\n" + onboarding_text)
    ]

    l2_user = SimpleNamespace(username="l2", role_level=2, department="품질보증팀")
    l3_user = SimpleNamespace(username="l3", role_level=3, department="품질보증팀")
    l4_user = SimpleNamespace(username="l4", role_level=4, department="품질보증팀")
    rbac_outcomes = {
        "l2_other_dept_forced": _resolve_effective_department("재무팀", l2_user),
        "l3_same_division_allowed": _resolve_effective_department("영업팀", l3_user),
        "l3_other_division_forced": _resolve_effective_department("재무팀", l3_user),
        "l4_other_division_allowed": _resolve_effective_department("재무팀", l4_user),
    }
    expected_rbac = {
        "l2_other_dept_forced": "품질보증팀",
        "l3_same_division_allowed": "영업팀",
        "l3_other_division_forced": "품질보증팀",
        "l4_other_division_allowed": "재무팀",
    }

    failures: list[str] = []
    if missing_flags:
        failures.append("missing_feature_c_flags")
    if extra_flags:
        failures.append("unexpected_feature_c_flags")
    if missing_markers:
        failures.append("frontend_flag_consumption_missing")
    if rbac_outcomes != expected_rbac:
        failures.append("dept_rbac_baseline_changed")

    details = {
        "flag_keys": sorted(flag_keys),
        "missing_flags": missing_flags,
        "extra_flags": extra_flags,
        "missing_frontend_markers": missing_markers,
        "rbac_outcomes": rbac_outcomes,
        "dept_lock_policy": "baseline_enforced",
        "division_boundary_policy": "baseline_enforced",
        "quick_questions_v2_policy": "ga_content_verified",
    }
    if failures:
        return CheckResult(
            "feature_c_flag_rollout",
            "fail",
            "Feature C flag rollout wiring or RBAC baseline is incomplete",
            {**details, "failures": failures},
        )
    return CheckResult(
        "feature_c_flag_rollout",
        "pass",
        "Feature C flags are defined, key frontend flags are consumed, and RBAC baseline is enforced",
        details,
    )


def _validate_question_file(root: Path, path: Path) -> tuple[list[str], list[str]]:
    """Validate a quick-questions JSON file.

    Args:
        root: Repository root.
        path: JSON file path.

    Returns:
        tuple[list[str], list[str]]: Failures and kb citation ids observed.
    """

    failures: list[str] = []
    citation_ids: list[str] = []
    data = _load_json(path)
    questions = data.get("questions", [])
    if not isinstance(questions, list) or not questions:
        failures.append(f"{path.name}:questions_empty")
        return failures, citation_ids
    if not path.name.startswith("_") and data.get("department") != path.stem:
        failures.append(f"{path.name}:department_mismatch")
    seen_ids: set[str] = set()
    kb_base = root / "data" / "knowledge_base"
    for idx, item in enumerate(questions):
        if not isinstance(item, Mapping):
            failures.append(f"{path.name}:{idx}:not_object")
            continue
        missing = sorted(QUESTION_REQUIRED_FIELDS - set(item))
        if missing:
            failures.append(f"{path.name}:{idx}:missing={','.join(missing)}")
            continue
        qid = str(item.get("id") or "")
        if qid in seen_ids:
            failures.append(f"{path.name}:{idx}:duplicate_id={qid}")
        seen_ids.add(qid)
        if item.get("category") not in QUESTION_CATEGORIES:
            failures.append(f"{path.name}:{qid}:bad_category={item.get('category')}")
        min_level = item.get("min_level")
        max_level = item.get("max_level")
        if not isinstance(min_level, int) or not isinstance(max_level, int) or not (1 <= min_level <= max_level <= 5):
            failures.append(f"{path.name}:{qid}:bad_level_range")
        kb_doc_path = item.get("kb_doc_path")
        if kb_doc_path:
            kb_path = kb_base / str(kb_doc_path)
            if not kb_path.exists():
                failures.append(f"{path.name}:{qid}:missing_kb_doc={kb_doc_path}")
            else:
                content = kb_path.read_text(encoding="utf-8")
                citation_ids.append(_citation_id_from_markdown(content, kb_path.stem.replace(".en", "")))
    return failures, citation_ids


def _citation_id_from_markdown(content: str, default: str) -> str:
    """Extract a markdown citation id with the same fallback policy as runtime.

    Args:
        content: Markdown content.
        default: Default citation id.

    Returns:
        str: Citation id.
    """

    for line in content.splitlines()[:20]:
        if line.strip().startswith("citation_id:"):
            value = line.split(":", 1)[1].strip()
            if value:
                return value
    return default


def verify_content_assets(config: FeatureCConfig) -> CheckResult:
    """Verify curated Feature C content assets.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Content asset posture.
    """

    failures: list[str] = []
    warnings: list[str] = []

    try:
        from features.onboarding.department_router import DEPARTMENT_PROFILES
    except Exception:
        DEPARTMENT_PROFILES = {}

    kb_root = config.root / "data" / "knowledge_base"
    quick_dir = kb_root / "quick_questions"
    sops_dir = kb_root / "sops"
    collab_dir = kb_root / "collaboration"

    if not quick_dir.exists():
        failures.append("quick_questions_dir_missing")
        quick_dept_count = 0
        question_count = 0
    else:
        quick_failures: list[str] = []
        kb_citations: list[str] = []
        question_count = 0
        for path in sorted(quick_dir.glob("*.json")):
            q_failures, q_citations = _validate_question_file(config.root, path)
            quick_failures.extend(q_failures)
            kb_citations.extend(q_citations)
            try:
                question_count += len(_load_json(path).get("questions", []))
            except Exception:
                pass
        level_dir = quick_dir / "_by_level"
        for required in ("L1.json", "L2.json", "L3.json", "L4_5.json"):
            if not (level_dir / required).exists():
                quick_failures.append(f"_by_level/{required}:missing")
        dept_files = [
            path for path in quick_dir.glob("*.json")
            if not path.name.startswith("_")
        ]
        quick_dept_count = len(dept_files)
        if quick_dept_count < 30:
            quick_failures.append(f"department_question_files_lt_30:{quick_dept_count}")
        profile_names = set(DEPARTMENT_PROFILES)
        unknown_depts = sorted(path.stem for path in dept_files if profile_names and path.stem not in profile_names)
        if unknown_depts:
            quick_failures.append(f"quick_question_unknown_departments={','.join(unknown_depts[:10])}")
        missing_profile_questions = sorted(profile_names - {path.stem for path in dept_files})
        if missing_profile_questions:
            warnings.append(f"profile_without_quick_questions={','.join(missing_profile_questions[:10])}")
        if quick_failures:
            failures.extend(quick_failures[:50])

    sop_ids: set[str] = set()
    sop_citations: set[str] = set()
    if not sops_dir.exists():
        failures.append("sops_dir_missing")
    else:
        sop_files = sorted(sops_dir.glob("*.json"))
        if len(sop_files) != 8:
            failures.append(f"sop_json_count_expected_8_actual_{len(sop_files)}")
        for path in sop_files:
            try:
                data = _load_json(path)
            except Exception as exc:
                failures.append(f"{path.name}:json_error={type(exc).__name__}")
                continue
            missing = sorted(SOP_REQUIRED_FIELDS - set(data))
            if missing:
                failures.append(f"{path.name}:missing={','.join(missing)}")
                continue
            sop_id = str(data.get("sop_id") or "")
            if sop_id in sop_ids:
                failures.append(f"{path.name}:duplicate_sop_id={sop_id}")
            sop_ids.add(sop_id)
            citation_id = str(data.get("citation_id") or "")
            if not citation_id:
                failures.append(f"{path.name}:citation_id_empty")
            elif citation_id in sop_citations:
                failures.append(f"{path.name}:duplicate_citation_id={citation_id}")
            sop_citations.add(citation_id)
            steps = data.get("steps")
            if not isinstance(steps, list) or not steps:
                failures.append(f"{path.name}:steps_empty")
            else:
                for idx, step in enumerate(steps):
                    if not isinstance(step, Mapping):
                        failures.append(f"{path.name}:step_{idx}:not_object")
                        continue
                    missing_step = sorted(SOP_STEP_REQUIRED_FIELDS - set(step))
                    if missing_step:
                        failures.append(f"{path.name}:step_{idx}:missing={','.join(missing_step)}")
            for related in data.get("related_sops") or []:
                if related and related not in {p.stem for p in sop_files} and related not in sop_ids:
                    failures.append(f"{path.name}:related_sop_unknown={related}")

    collab_citations: set[str] = set()
    if not collab_dir.exists():
        failures.append("collaboration_dir_missing")
        collab_json_count = 0
    else:
        collab_files = sorted(collab_dir.glob("*.json"))
        collab_json_count = len(collab_files)
        if collab_json_count != 5:
            failures.append(f"collaboration_json_count_expected_5_actual_{collab_json_count}")
        for path in collab_files:
            try:
                data = _load_json(path)
            except Exception as exc:
                failures.append(f"{path.name}:json_error={type(exc).__name__}")
                continue
            missing = sorted(COLLAB_REQUIRED_FIELDS - set(data))
            if missing:
                failures.append(f"{path.name}:missing={','.join(missing)}")
                continue
            citation_id = str(data.get("citation_id") or "")
            if citation_id in collab_citations:
                failures.append(f"{path.name}:duplicate_citation_id={citation_id}")
            collab_citations.add(citation_id)
            for list_field in ("trigger_keywords", "my_actions", "hand_off_items"):
                if not isinstance(data.get(list_field), list) or not data.get(list_field):
                    failures.append(f"{path.name}:{list_field}_empty")
            related_sop = data.get("related_sop_id")
            if related_sop and related_sop not in sop_ids:
                failures.append(f"{path.name}:related_sop_unknown={related_sop}")

    details = {
        "quick_question_departments": quick_dept_count,
        "quick_question_count": question_count,
        "sop_count": len(sop_ids),
        "collaboration_count": collab_json_count,
        "sop_citation_count": len(sop_citations),
        "collaboration_citation_count": len(collab_citations),
        "warnings": warnings[:20],
    }
    try:
        from features.onboarding.content_cms import validate_content_store

        cms_result = validate_content_store(config.root)
        if not cms_result["ok"]:
            for issue in cms_result["issues"][:50]:
                failures.append(
                    f"{issue.get('path')}:{issue.get('item_id')}:{issue.get('detail')}"
                )
        details["cms_validation"] = cms_result
    except Exception as exc:
        failures.append(f"content_cms_validation_error:{type(exc).__name__}")
    if failures:
        return CheckResult(
            "feature_c_content_assets",
            "fail",
            "Feature C curated content has broken schema, links, or citation posture",
            {**details, "failures": failures[:80]},
        )
    if warnings:
        return CheckResult(
            "feature_c_content_assets",
            "warn",
            "Feature C curated content passes blocker checks with non-blocking coverage notes",
            details,
        )
    return CheckResult(
        "feature_c_content_assets",
        "pass",
        "Feature C quick questions, SOPs, and collaboration scenarios pass content integrity checks",
        details,
    )


def verify_content_signoff(config: FeatureCConfig) -> CheckResult:
    """Check whether a business-owner content review signoff exists.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Content signoff posture.
    """

    if config.content_signoff_path and config.content_signoff_path.exists():
        return CheckResult(
            "feature_c_content_signoff",
            "pass",
            "business-owner department content signoff file exists",
            {"path": _display_path(config.root, config.content_signoff_path)},
        )
    return CheckResult(
        "feature_c_content_signoff",
        "fail",
        "department business-owner content signoff is required for release",
        {
            "required_review_scope": [
                "department quick questions",
                "SOP steps and quiz source material",
                "collaboration scenarios and handoff wording",
                "vision/document task prompts",
            ],
            "signoff_path": _display_path(config.root, config.content_signoff_path)
            if config.content_signoff_path
            else "",
        },
    )


def _docker_stage_block(dockerfile_text: str, stage_name: str) -> str:
    """Extract a Dockerfile stage body by stage name.

    Args:
        dockerfile_text: Full Dockerfile text.
        stage_name: Docker build stage alias, for example ``slim``.

    Returns:
        str: Stage body including the ``FROM`` line, or an empty string.
    """

    stage_re = re.compile(rf"^FROM\s+.+\s+AS\s+{re.escape(stage_name)}\s*$", re.MULTILINE)
    match = stage_re.search(dockerfile_text)
    if not match:
        return ""
    next_stage = re.search(r"^FROM\s+.+\s+AS\s+\S+\s*$", dockerfile_text[match.end():], re.MULTILINE)
    end = match.end() + next_stage.start() if next_stage else len(dockerfile_text)
    return dockerfile_text[match.start():end]


def verify_docker_slim_content_packaging(config: FeatureCConfig) -> CheckResult:
    """Verify Cloud Run slim images include Feature C content assets.

    Args:
        config: Verifier config.

    Returns:
        CheckResult: Docker slim packaging posture.
    """

    dockerfile = config.root / "Dockerfile"
    try:
        dockerfile_text = dockerfile.read_text(encoding="utf-8")
    except Exception as exc:
        return CheckResult(
            "feature_c_docker_slim_packaging",
            "fail",
            "Dockerfile could not be inspected for Feature C content packaging",
            {"path": _display_path(config.root, dockerfile), "error": type(exc).__name__},
        )

    slim = _docker_stage_block(dockerfile_text, "slim")
    if not slim:
        return CheckResult(
            "feature_c_docker_slim_packaging",
            "fail",
            "Dockerfile slim stage is missing",
            {"path": _display_path(config.root, dockerfile)},
        )

    normalized = re.sub(r"\s+", " ", slim)
    full_kb_copy = "COPY data/knowledge_base/ ./data/knowledge_base/" in slim
    missing_assets = [
        name for name, source_path in FEATURE_C_DOCKER_REQUIRED_ASSETS.items()
        if source_path not in normalized and not full_kb_copy
    ]

    if missing_assets:
        return CheckResult(
            "feature_c_docker_slim_packaging",
            "fail",
            "Cloud Run slim image does not package all Feature C training content assets",
            {
                "path": _display_path(config.root, dockerfile),
                "full_knowledge_base_copy": full_kb_copy,
                "missing_assets": missing_assets,
                "required_assets": FEATURE_C_DOCKER_REQUIRED_ASSETS,
            },
        )
    return CheckResult(
        "feature_c_docker_slim_packaging",
        "pass",
        "Cloud Run slim image packages Feature C SOP, quick-question, collaboration, guide, and glossary assets",
        {
            "path": _display_path(config.root, dockerfile),
            "full_knowledge_base_copy": full_kb_copy,
            "required_assets": FEATURE_C_DOCKER_REQUIRED_ASSETS,
        },
    )


def summarize(checks: Sequence[CheckResult]) -> dict[str, Any]:
    """Summarize check statuses.

    Args:
        checks: Check results.

    Returns:
        dict[str, Any]: Summary payload.
    """

    counts = {"pass": 0, "warn": 0, "fail": 0, "skip": 0}
    for check in checks:
        counts[check.status] = counts.get(check.status, 0) + 1
    status = "fail" if counts["fail"] else "warn" if counts["warn"] else "pass"
    return {"status": status, "counts": counts, "checked_at": datetime.now(timezone.utc).isoformat()}


def run_verification(config: FeatureCConfig) -> dict[str, Any]:
    """Run all Feature C release checks.

    Args:
        config: Verifier config.

    Returns:
        dict[str, Any]: Secret-safe report payload.
    """

    checks = [
        verify_endpoint_surface(config),
        verify_llm_cost_posture(config),
        verify_llm_failure_posture(config),
        verify_feature_flag_rollout(config),
        verify_content_assets(config),
        verify_docker_slim_content_packaging(config),
        verify_content_signoff(config),
    ]
    return {
        "summary": summarize(checks),
        "config": {
            "strict": config.strict,
            "allow_paid_llm": config.allow_paid_llm,
            "openapi_path": _display_path(config.root, config.openapi_path),
            "content_signoff_path": _display_path(config.root, config.content_signoff_path)
            if config.content_signoff_path
            else "",
            "llm_router_primary": os.getenv("LLM_ROUTER_PRIMARY", "gemini").strip() or "gemini",
            "gemini_api_key_present": bool(os.getenv("GEMINI_API_KEY", "").strip()),
            "feature_c_compare_mode": _truthy(os.getenv("FEATURE_C_COMPARE_MODE")),
        },
        "references": list(DOC_REFERENCES),
        "checks": [check.to_dict() for check in checks],
    }


def write_markdown_report(report: Mapping[str, Any], path: Path) -> None:
    """Write a Markdown verification report.

    Args:
        report: Report payload.
        path: Destination path.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    summary = report["summary"]
    config = report["config"]
    lines = [
        "# Feature C Release Check",
        "",
        f"- Status: `{summary['status']}`",
        f"- Checked at: `{summary['checked_at']}`",
        f"- Counts: `{json.dumps(summary['counts'], ensure_ascii=False)}`",
        f"- LLM router primary: `{config['llm_router_primary']}`",
        f"- Gemini API key present: `{config['gemini_api_key_present']}`",
        f"- Feature C compare mode: `{config['feature_c_compare_mode']}`",
        f"- Allow paid LLM override: `{config['allow_paid_llm']}`",
        f"- Content signoff path: `{config['content_signoff_path']}`",
        "",
        "## Checks",
        "",
        "| Status | Check | Summary | Details |",
        "| --- | --- | --- | --- |",
    ]
    for check in report["checks"]:
        details = json.dumps(check.get("details", {}), ensure_ascii=False)
        lines.append(
            f"| `{check['status']}` | `{check['name']}` | {check['summary']} | `{details}` |"
        )
    lines.extend(
        [
            "",
            "## Content Review Checklist",
            "",
            "- Department quick questions: confirm labels, wording, level visibility, and owner department fit.",
            "- SOPs and quizzes: confirm step order, safety warnings, customer/OEM wording, and quiz answers.",
            "- Collaboration scenarios: confirm requesting department, handoff artifacts, deadlines, and related SOP links.",
            "- Vision/document tasks: confirm extracted fields and downstream routing match department workflows.",
            "",
            "## References",
            "",
        ]
    )
    for ref in report["references"]:
        lines.append(f"- {ref}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _print_text_report(report: Mapping[str, Any]) -> None:
    """Print a compact text report.

    Args:
        report: Report payload.
    """

    summary = report["summary"]
    print(
        "Feature C release: "
        f"{summary['status']} "
        f"(pass={summary['counts']['pass']}, warn={summary['counts']['warn']}, "
        f"fail={summary['counts']['fail']}, skip={summary['counts']['skip']})"
    )
    for check in report["checks"]:
        print(f"[{check['status'].upper()}] {check['name']}: {check['summary']}")
        if check.get("details"):
            print(f"  details={json.dumps(check['details'], ensure_ascii=False)}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments.

    Args:
        argv: Optional argument list.

    Returns:
        argparse.Namespace: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when fail checks remain.")
    parser.add_argument("--markdown", default="", help="Write a Markdown report to this path.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser.add_argument("--openapi", default="docs/openapi.json", help="OpenAPI JSON path.")
    parser.add_argument(
        "--content-signoff",
        "--business-signoff",
        dest="content_signoff",
        default="",
        help="Optional business-owner department content signoff file.",
    )
    parser.add_argument(
        "--allow-paid-llm",
        action="store_true",
        help="Allow paid/external LLM primary or compare mode for this run.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI.

    Args:
        argv: Optional argument list.

    Returns:
        int: Process exit code.
    """

    args = parse_args(argv)
    _load_release_dotenv(ROOT)
    openapi_path = Path(args.openapi)
    if not openapi_path.is_absolute():
        openapi_path = ROOT / openapi_path
    content_signoff_path = (ROOT / args.content_signoff).resolve() if args.content_signoff else None
    config = FeatureCConfig(
        root=ROOT,
        openapi_path=openapi_path,
        strict=bool(args.strict),
        content_signoff_path=content_signoff_path,
        allow_paid_llm=bool(args.allow_paid_llm),
    )
    report = run_verification(config)
    if args.markdown:
        markdown_path = Path(args.markdown)
        if not markdown_path.is_absolute():
            markdown_path = ROOT / markdown_path
        write_markdown_report(report, markdown_path)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text_report(report)
    if config.strict and report["summary"]["status"] == "fail":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
