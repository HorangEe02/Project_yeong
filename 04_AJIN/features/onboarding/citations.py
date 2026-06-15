"""Citation helpers for Feature C onboarding answers.

The runtime keeps the LLM prompt advisory, but this module enforces the final
answer contract on the server side so source posture does not depend only on
model behavior.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal, Mapping

CitationStatus = Literal["verified", "corrected", "model_only", "failed"]

_CITATION_RE = re.compile(r"\[출처:([A-Za-z0-9_.:/\-]+)\]")
_MODEL_ONLY_NOTICE = (
    "사내 자료에서 확인된 출처 없음. 최신성 보장이 필요한 내용은 담당 부서 확인이 필요합니다."
)


@dataclass(frozen=True)
class SourceRef:
    """Normalized source reference shared by onboarding content surfaces.

    Args:
        citation_id: Stable identifier required in answer text as ``[출처:<id>]``.
        source_path: Repository path, API route, or object identifier.
        source_type: Source family such as ``kb_markdown``, ``sop``, or ``uploaded_file``.
        reviewed_at: Business review date when available.
        title: Human-readable source title.

    Returns:
        Immutable source reference value object.
    """

    citation_id: str
    source_path: str
    source_type: str
    reviewed_at: str = ""
    title: str = ""

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-serializable representation.

        Returns:
            A dictionary with the common citation fields.
        """

        return asdict(self)


@dataclass(frozen=True)
class CitationEnforcementResult:
    """Server-side citation enforcement result.

    Args:
        text: Full corrected answer text.
        footer: Text that should be appended to a streamed answer, if any.
        citation_status: Final citation status.
        sources: Normalized source dictionaries.

    Returns:
        Immutable enforcement result value object.
    """

    text: str
    footer: str
    citation_status: CitationStatus
    sources: list[dict[str, str]]


def source_ref_from_kb_context(ctx: Mapping[str, str]) -> SourceRef:
    """Convert a KB lookup result into a common ``SourceRef``.

    Args:
        ctx: KB lookup mapping with ``citation_id`` and ``source_path``.

    Returns:
        SourceRef: A normalized KB markdown source reference.

    Raises:
        ValueError: If the lookup result does not include a citation id.
    """

    citation_id = str(ctx.get("citation_id") or "").strip()
    if not citation_id:
        raise ValueError("KB context is missing citation_id")
    return SourceRef(
        citation_id=citation_id,
        source_path=str(ctx.get("source_path") or ""),
        source_type="kb_markdown",
        reviewed_at=str(ctx.get("reviewed_at") or ""),
        title=str(ctx.get("title") or citation_id),
    )


def enforce_citations(answer: str, sources: list[SourceRef]) -> CitationEnforcementResult:
    """Validate and, when safe, correct citation markers in an answer.

    Args:
        answer: Full LLM answer text accumulated from the stream.
        sources: Verified source references used to build the prompt.

    Returns:
        CitationEnforcementResult: Corrected answer, appended footer, final
        status, and serialized sources.
    """

    serialized = [source.to_dict() for source in sources]
    text = answer or ""
    if not sources:
        if _MODEL_ONLY_NOTICE in text:
            return CitationEnforcementResult(text, "", "model_only", serialized)
        footer = f"\n\n{_MODEL_ONLY_NOTICE}"
        return CitationEnforcementResult(f"{text}{footer}", footer, "model_only", serialized)

    present_ids = set(_CITATION_RE.findall(text))
    missing = [source for source in sources if source.citation_id not in present_ids]
    if not missing:
        return CitationEnforcementResult(text, "", "verified", serialized)

    footer_lines = ["", "", "출처 보정:"]
    for source in missing:
        label = source.title or source.source_path or source.source_type
        footer_lines.append(f"- {label} [출처:{source.citation_id}]")
    footer = "\n".join(footer_lines)
    return CitationEnforcementResult(f"{text}{footer}", footer, "corrected", serialized)


def analyzer_source_ref(task: str, route_family: str) -> SourceRef:
    """Build operational source metadata for a file analyzer result.

    Args:
        task: Analyzer task id.
        route_family: Either ``vision`` or ``document``.

    Returns:
        SourceRef: A normalized uploaded-file analyzer source marker.
    """

    return SourceRef(
        citation_id=f"analyzer:{route_family}:{task}",
        source_path=f"/api/onboarding/{route_family}/{task}",
        source_type="uploaded_file",
        title=f"{route_family}/{task}",
    )
