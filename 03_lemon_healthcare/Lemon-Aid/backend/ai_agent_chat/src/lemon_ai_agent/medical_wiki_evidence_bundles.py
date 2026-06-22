from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from lemon_ai_agent.answer_card import Answerability, AnswerCard, KnowledgeRetrievalResult
from lemon_ai_agent.knowledge import ChatIntentAnalysis, SourceFamily, analyze_chat_intent

WORKSPACE_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_EVIDENCE_BUNDLE_FIXTURES_PATH = (
    WORKSPACE_ROOT / "MEDICAL-WIKI" / "manifest" / "evidence_bundle_adapter_fixtures.jsonl"
)


@dataclass(frozen=True)
class MedicalWikiEvidenceBundleFixture:
    fixture_id: str
    query: str
    evidence_bundle_id: str
    bundle_mode: str
    expires_at: str
    expected_renderer_route: str
    expected_source_ids: tuple[str, ...]
    blocked_actions: tuple[str, ...]
    safety_anchor_claim_id: str
    safety_anchor: dict[str, Any]
    section_explanations: tuple[dict[str, Any], ...]
    sources: tuple[dict[str, str], ...]


class MedicalWikiEvidenceBundleRetriever:
    """MEDICAL-WIKI EvidenceBundle fixture adapter for backend contract evals."""

    def __init__(
        self,
        fixtures_path: Path | None = None,
        *,
        as_of: date | None = None,
    ) -> None:
        self._fixtures_path = fixtures_path or DEFAULT_EVIDENCE_BUNDLE_FIXTURES_PATH
        self._as_of = as_of or date.today()
        self._fixtures = tuple(self._load_fixtures())
        self._fixtures_by_query: dict[str, MedicalWikiEvidenceBundleFixture] = {}
        for fixture in self._fixtures:
            self._fixtures_by_query[fixture.query] = fixture
            self._fixtures_by_query[_normalize_query(fixture.query)] = fixture

    @property
    def fixtures(self) -> tuple[MedicalWikiEvidenceBundleFixture, ...]:
        return self._fixtures

    def route_counts(self) -> dict[str, int]:
        return dict(Counter(fixture.expected_renderer_route for fixture in self._fixtures))

    def fixture_for_query(self, query: str) -> MedicalWikiEvidenceBundleFixture | None:
        return self._fixtures_by_query.get(query) or self._fixtures_by_query.get(
            _normalize_query(query)
        )

    def retrieve(self, analysis: ChatIntentAnalysis) -> KnowledgeRetrievalResult:
        fixture = self.fixture_for_query(analysis.normalized_question)
        if fixture is None:
            return KnowledgeRetrievalResult(
                cards=(),
                knowledge_items=(),
                missing_topics=(analysis.primary_intent,),
                warnings=("no_reviewed_evidence_bundle",),
                retrieval_status="no_match",
            )
        cards = self.answer_cards_for_fixture(fixture, analysis)
        return KnowledgeRetrievalResult(
            cards=cards,
            knowledge_items=(),
            missing_topics=(),
            warnings=(),
            retrieval_status="found",
        )

    def retrieve_for_question(self, question: str) -> KnowledgeRetrievalResult:
        return self.retrieve(analyze_chat_intent(question))

    def answer_cards_for_fixture(
        self,
        fixture: MedicalWikiEvidenceBundleFixture,
        analysis: ChatIntentAnalysis,
    ) -> tuple[AnswerCard, ...]:
        answerability = _answerability_for_fixture(fixture)
        must_not_say = _must_not_say_for_fixture(fixture)
        source_family = _source_family_for_fixture(fixture)
        section_by_source_id = _section_by_source_id(fixture)
        return tuple(
            _answer_card_for_source(
                fixture,
                source,
                analysis,
                answerability=answerability,
                source_family=source_family,
                must_not_say=must_not_say,
                section=section_by_source_id.get(source["source_id"]),
            )
            for source in fixture.sources
        )

    def _load_fixtures(self) -> list[MedicalWikiEvidenceBundleFixture]:
        fixtures: list[MedicalWikiEvidenceBundleFixture] = []
        for row in _read_jsonl(self._fixtures_path):
            if not _is_eligible_fixture(row, self._as_of):
                continue
            fixtures.append(_fixture_from_row(row))
        return fixtures


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_no} is not a JSON object")
            rows.append(row)
    return rows


def _normalize_query(query: str) -> str:
    return " ".join(query.casefold().split())


def _is_eligible_fixture(row: dict[str, Any], as_of: date) -> bool:
    adapter_input = row.get("adapter_input")
    contract = row.get("expected_adapter_contract")
    if not isinstance(adapter_input, dict) or not isinstance(contract, dict):
        return False
    normalizer_contract = adapter_input.get("normalizer_contract")
    if not isinstance(normalizer_contract, dict):
        return False
    return (
        _date_field_is_future(adapter_input, "bundle_expires_at", as_of)
        and contract.get("safety_anchor_required") is True
        and normalizer_contract.get("generation_performed") is False
        and normalizer_contract.get("langchain_attached") is False
        and normalizer_contract.get("runtime_adapter_attached") is False
        and normalizer_contract.get("retrieval_results_are_not_prompt") is True
        and bool(adapter_input.get("safety_anchor"))
        and bool(adapter_input.get("sources"))
        and bool(row.get("expected_renderer_route"))
    )


def _date_field_is_future(row: dict[str, Any], field_name: str, as_of: date) -> bool:
    try:
        return date.fromisoformat(str(row.get(field_name, ""))) > as_of
    except ValueError:
        return False


def _fixture_from_row(row: dict[str, Any]) -> MedicalWikiEvidenceBundleFixture:
    adapter_input = row["adapter_input"]
    expected_contract = row["expected_adapter_contract"]
    safety_anchor = adapter_input["safety_anchor"]
    return MedicalWikiEvidenceBundleFixture(
        fixture_id=str(row["fixture_id"]),
        query=str(adapter_input["query"]),
        evidence_bundle_id=str(adapter_input["evidence_bundle_id"]),
        bundle_mode=str(adapter_input["bundle_mode"]),
        expires_at=str(adapter_input["bundle_expires_at"]),
        expected_renderer_route=str(row["expected_renderer_route"]),
        expected_source_ids=tuple(
            str(source_id)
            for source_id in expected_contract.get("source_ids_must_be_preserved", [])
        ),
        blocked_actions=tuple(str(item) for item in adapter_input.get("blocked_actions", [])),
        safety_anchor_claim_id=str(safety_anchor.get("claim_id", "")),
        safety_anchor=safety_anchor,
        section_explanations=tuple(
            section
            for section in adapter_input.get("section_explanations", [])
            if isinstance(section, dict)
        ),
        sources=tuple(_source_from_row(source) for source in adapter_input.get("sources", [])),
    )


def _source_from_row(source: dict[str, Any]) -> dict[str, str]:
    return {
        "source_id": str(source.get("source_id", "")),
        "source_family": str(source.get("source_family", "")),
        "publisher": str(source.get("publisher", "")),
        "title": str(source.get("title", "")),
        "canonical_url": str(source.get("canonical_url", "")),
        "version_label": str(source.get("version_label", "")),
    }


def _answerability_for_fixture(fixture: MedicalWikiEvidenceBundleFixture) -> Answerability:
    if fixture.expected_renderer_route == "answer_renderer_with_boundary_anchor":
        return "answerable_with_caution"
    severity = str(fixture.safety_anchor.get("severity", ""))
    if "urgent" in severity:
        return "urgent_escalation"
    if severity == "safety_boundary":
        return "safety_boundary"
    return "medical_decision_boundary"


def _source_family_for_fixture(fixture: MedicalWikiEvidenceBundleFixture) -> SourceFamily:
    domain = str(fixture.safety_anchor.get("domain", ""))
    if domain == "mental_health":
        return "mental_health_escalation"
    if _answerability_for_fixture(fixture) == "urgent_escalation":
        return "emergency_escalation"
    if domain in {"medication_interaction", "supplement"}:
        return "drug_safety_boundary"
    if domain == "chronic_disease":
        return "chronic_condition"
    if domain == "food":
        return "food_safety_allergy"
    return "general_medical"


def _must_not_say_for_fixture(fixture: MedicalWikiEvidenceBundleFixture) -> tuple[str, ...]:
    phrases: list[str] = []
    phrases.extend(fixture.blocked_actions)
    phrases.extend(str(item) for item in fixture.safety_anchor.get("blocked_wording", []))
    phrases.extend(str(item) for item in fixture.safety_anchor.get("must_not_answer_as", []))
    for section in fixture.section_explanations:
        phrases.extend(str(item) for item in section.get("blocked_scope", []))
        phrases.extend(str(item) for item in section.get("must_not_do", []))
    return tuple(dict.fromkeys(item for item in phrases if item))


def _section_by_source_id(
    fixture: MedicalWikiEvidenceBundleFixture,
) -> dict[str, dict[str, Any]]:
    if fixture.expected_renderer_route == "boundary_renderer":
        return {}
    sections: dict[str, dict[str, Any]] = {}
    for section in fixture.section_explanations:
        for source_id in section.get("source_ids", []):
            sections[str(source_id)] = section
    return sections


def _answer_card_for_source(
    fixture: MedicalWikiEvidenceBundleFixture,
    source: dict[str, str],
    analysis: ChatIntentAnalysis,
    *,
    answerability: Answerability,
    source_family: SourceFamily,
    must_not_say: tuple[str, ...],
    section: dict[str, Any] | None,
) -> AnswerCard:
    anchor = fixture.safety_anchor
    grounding_ids = [f"medical-wiki-claim:{fixture.safety_anchor_claim_id}"]
    if section is not None:
        grounding_ids.append(f"reviewed_section:{section.get('section_id', '')}")
    return AnswerCard(
        card_id=f"medical-wiki-bundle:{fixture.fixture_id}:{source['source_id']}",
        answerability=answerability,
        topic=fixture.evidence_bundle_id,
        intent=analysis.primary_intent,
        condition=analysis.related_conditions[0] if analysis.related_conditions else None,
        allowed_guidance=_allowed_guidance(fixture, section),
        specific_examples=_specific_examples(fixture, section),
        checklist=_checklist(fixture, section),
        caution_conditions=_caution_conditions(fixture, section),
        must_not_say=must_not_say,
        source_id=source["source_id"],
        source_url=source["canonical_url"],
        source_family=source_family,
        source_version_id=source["source_id"],
        version_label=source.get("version_label", ""),
        review_status="reviewed",
        reviewed_at="2026-06-09",
        expires_at=fixture.expires_at,
        grounding_snippet_ids=tuple(item for item in grounding_ids if item),
        source_name=_source_name(source),
        concrete_guidance=_concrete_guidance(fixture, section),
        severity=str(anchor.get("severity", "")),
        primary_action=str(anchor.get("primary_action", "")),
        blocked_wording=must_not_say,
        linked_claim_id=fixture.safety_anchor_claim_id,
    )


def _allowed_guidance(
    fixture: MedicalWikiEvidenceBundleFixture,
    section: dict[str, Any] | None,
) -> tuple[str, ...]:
    if section is not None:
        return (str(section.get("content_summary", "")),)
    anchor_title = str(fixture.safety_anchor.get("title", "reviewed safety boundary"))
    primary_action = str(fixture.safety_anchor.get("primary_action", "consult clinician"))
    return (f"{anchor_title}: {primary_action}",)


def _specific_examples(
    fixture: MedicalWikiEvidenceBundleFixture,
    section: dict[str, Any] | None,
) -> tuple[str, ...]:
    if section is not None:
        return tuple(str(item) for item in section.get("must_include", []) if item)
    return (
        str(fixture.safety_anchor.get("title", "")),
        str(fixture.safety_anchor.get("domain", "")),
        str(fixture.safety_anchor.get("primary_action", "")),
    )


def _checklist(
    fixture: MedicalWikiEvidenceBundleFixture,
    section: dict[str, Any] | None,
) -> tuple[str, ...]:
    if section is not None:
        return tuple(str(item) for item in section.get("must_include", []) if item)
    domain = str(fixture.safety_anchor.get("domain", ""))
    if domain in {"medication_interaction", "supplement"}:
        return ("정확한 약 이름", "성분명", "제품 라벨", "복용 중인 약 목록", "이상 증상")
    if domain == "chronic_disease":
        return ("현재 증상", "측정 수치", "복용 중인 약", "기존 관리 계획", "증상 악화 여부")
    if domain == "food":
        return ("증상 시작 시점", "먹은 음식", "호흡/목 조임 여부", "고위험군 여부")
    return ("현재 증상", "복용 중인 약", "제품 라벨", "진료 필요 신호")


def _caution_conditions(
    fixture: MedicalWikiEvidenceBundleFixture,
    section: dict[str, Any] | None,
) -> tuple[str, ...]:
    values: list[str] = [
        str(fixture.safety_anchor.get("severity", "")),
        str(fixture.safety_anchor.get("primary_action", "")),
    ]
    if section is not None:
        values.extend(str(item) for item in section.get("blocked_scope", []))
    values.extend(str(item) for item in fixture.safety_anchor.get("must_not_answer_as", []))
    return tuple(dict.fromkeys(value for value in values if value))


def _concrete_guidance(
    fixture: MedicalWikiEvidenceBundleFixture,
    section: dict[str, Any] | None,
) -> str:
    if section is not None:
        return str(section.get("content_summary", ""))
    return str(fixture.safety_anchor.get("title", ""))


def _source_name(source: dict[str, str]) -> str:
    publisher = source.get("publisher", "").strip()
    title = source.get("title", "").strip()
    if publisher and title:
        return f"{publisher} {title}"
    return publisher or title or source["source_id"]
