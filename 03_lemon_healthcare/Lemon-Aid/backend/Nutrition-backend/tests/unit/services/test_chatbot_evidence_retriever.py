"""Chatbot DB evidence retriever tests."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from lemon_ai_agent.answer_card import (
    EvidenceRecordMedicalKnowledgeRetriever,
    MedicalKnowledgeRetriever,
)
from lemon_ai_agent.knowledge import analyze_chat_intent
from src.config import Settings
from src.services.chatbot_evidence_retriever import (
    ChatbotEvidenceRepository,
    build_chatbot_medical_knowledge_retriever,
)


class _FakeResult:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self._rows = rows

    def all(self) -> list[SimpleNamespace]:
        return self._rows


class _FakeSession:
    def __init__(self, rows: list[SimpleNamespace]) -> None:
        self.rows = rows
        self.statement: object | None = None

    async def execute(self, statement: object) -> _FakeResult:
        self.statement = statement
        return _FakeResult(self.rows)


def _row() -> SimpleNamespace:
    return SimpleNamespace(
        evidence_id="evidence-magnesium-bp",
        source_id="nih-ods-magnesium",
        source_title="NIH ODS Magnesium Fact Sheet",
        source_url="https://ods.od.nih.gov/factsheets/Magnesium-Consumer/",
        source_family="supplement_guidance",
        source_version_id="source-version-1",
        version_label="2026-05 DB reviewed source",
        source_review_status="reviewed",
        reviewed_at=date(2026, 5, 29),
        expires_at=date(2026, 11, 29),
        topic="magnesium_supplement_caution",
        audience="adult",
        claim_summary="Magnesium supplement use needs label and medication review.",
        allowed_user_wording="제품 라벨, 마그네슘 함량, 혈압약 종류, 신장 기능을 확인한다.",
        blocked_wording="먹어도 됩니다.",
        applicability_note="혈압약 복용 중인 성인",
        caution_level="professional_review",
        evidence_review_status="reviewed",
        specific_examples=["제품 라벨", "마그네슘 함량", "혈압약 종류"],
        checklist=["제품 라벨", "함량", "신장 기능", "이상 증상"],
        caution_conditions=["새 보충제 시작", "이상 증상"],
        must_not_say=["먹어도 됩니다", "안전합니다", "먹으면 안 됩니다"],
    )


def _row_with(**overrides: object) -> SimpleNamespace:
    values = vars(_row())
    values.update(overrides)
    return SimpleNamespace(**values)


async def test_chatbot_evidence_repository_maps_db_rows_to_answer_card_records() -> None:
    """Verify DB rows become package-level evidence records."""
    session = _FakeSession([_row()])

    records = await ChatbotEvidenceRepository(session).list_answer_card_records()

    assert session.statement is not None
    assert len(records) == 1
    record = records[0]
    assert record.evidence_id == "evidence-magnesium-bp"
    assert record.source_family == "supplement_reference"
    assert record.specific_examples == ("제품 라벨", "마그네슘 함량", "혈압약 종류")
    assert record.checklist == ("제품 라벨", "함량", "신장 기능", "이상 증상")
    assert record.must_not_say == ("먹어도 됩니다", "안전합니다", "먹으면 안 됩니다")


async def test_chatbot_evidence_repository_filters_unreviewed_and_expired_rows() -> None:
    """Verify retrieval eval gate excludes draft and expired source/evidence rows."""
    session = _FakeSession(
        [
            _row(),
            _row_with(evidence_id="draft-evidence", evidence_review_status="draft"),
            _row_with(evidence_id="draft-source", source_review_status="draft"),
            _row_with(evidence_id="expired-source", expires_at=date(2025, 1, 1)),
        ]
    )

    records = await ChatbotEvidenceRepository(session).list_answer_card_records()

    assert [record.evidence_id for record in records] == ["evidence-magnesium-bp"]


async def test_build_chatbot_retriever_uses_db_records_when_present() -> None:
    """Verify DB records select the evidence-backed retriever."""
    retriever = await build_chatbot_medical_knowledge_retriever(
        _FakeSession([_row()]),
        Settings(_env_file=None),
    )

    assert isinstance(retriever, EvidenceRecordMedicalKnowledgeRetriever)


async def test_build_chatbot_retriever_fails_closed_for_production_empty_db() -> None:
    """Verify production-like DB retrieval does not fall back to seed registry."""
    retriever = await build_chatbot_medical_knowledge_retriever(
        _FakeSession([]),
        SimpleNamespace(environment="production"),
    )

    result = retriever.retrieve(
        analyze_chat_intent("혈압약을 먹는데 마그네슘 영양제를 같이 먹어도 돼?")
    )

    assert isinstance(retriever, EvidenceRecordMedicalKnowledgeRetriever)
    assert result.retrieval_status == "no_match"
    assert result.cards == ()
    assert "no_reviewed_answer_card" in result.warnings


async def test_build_chatbot_retriever_keeps_dev_registry_fallback_for_empty_db() -> None:
    """Verify local/dev can still use seed registry while DB coverage is bootstrapped."""
    retriever = await build_chatbot_medical_knowledge_retriever(
        _FakeSession([]),
        Settings(_env_file=None),
    )

    result = retriever.retrieve(
        analyze_chat_intent("혈압약을 먹는데 마그네슘 영양제를 같이 먹어도 돼?")
    )

    assert isinstance(retriever, MedicalKnowledgeRetriever)
    assert result.retrieval_status == "found"
    assert any(card.card_id.startswith("seed:") for card in result.cards)


async def test_build_chatbot_retriever_keeps_dev_registry_fallback_for_fake_session() -> None:
    """Verify route tests and local bootstrap can fall back outside production."""
    retriever = await build_chatbot_medical_knowledge_retriever(
        object(),  # type: ignore[arg-type]
        Settings(_env_file=None),
    )

    assert isinstance(retriever, MedicalKnowledgeRetriever)
