"""Tests for Korean localization of supplement-label display sections (KR market)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

import pytest
from src.services.supplement_label_localizer import (
    build_translation_payload,
    is_english_dominant,
    localize_snapshot_to_korean,
    parse_translations,
)


def _chat_returning(translations: list[str]):
    """Fake chat callable returning the given translations as JSON."""

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"message": {"content": json.dumps({"translations": translations})}}

    return _chat


def test_is_english_dominant() -> None:
    assert is_english_dominant("Consult your physician before using")
    assert not is_english_dominant("1일 1정 섭취하십시오")
    assert not is_english_dominant("mg")  # too few letters to bother translating


def test_build_payload_is_json_mode_and_carries_texts() -> None:
    payload = build_translation_payload(["Store in a cool dry place"], "gemma4:e4b")
    assert payload["format"] == "json"
    assert payload["options"]["temperature"] == 0
    assert "Store in a cool dry place" in payload["messages"][0]["content"]


def test_parse_translations_guards() -> None:
    assert parse_translations(json.dumps({"translations": ["가", "나"]}), 2) == ["가", "나"]
    assert parse_translations(json.dumps({"translations": ["가"]}), 2) is None  # count mismatch
    assert parse_translations("not json", 1) is None
    assert parse_translations(json.dumps({"translations": [""]}), 1) is None  # blank entry


@pytest.mark.asyncio
async def test_localizes_only_english_sections_without_mutating_input() -> None:
    snapshot = {
        "intake_method": {"text": "Take one tablet daily."},
        "precautions": [{"text": "Consult your physician before using."}],
        "functional_claims": [{"text": "장 건강에 도움을 줄 수 있음"}],  # Korean → skipped
    }
    # _collect_targets order: intake_method first, then list sections.
    out = await localize_snapshot_to_korean(
        snapshot,
        chat=_chat_returning(["1일 1정 섭취", "사용 전 의사와 상담하십시오"]),
        model="m",
    )
    assert out["intake_method"]["text"] == "1일 1정 섭취"
    assert out["precautions"][0]["text"] == "사용 전 의사와 상담하십시오"
    assert out["functional_claims"][0]["text"] == "장 건강에 도움을 줄 수 있음"  # unchanged
    # original snapshot is not mutated (a copy is returned)
    assert snapshot["precautions"][0]["text"] == "Consult your physician before using."


@pytest.mark.asyncio
async def test_korean_snapshot_makes_no_model_call() -> None:
    snapshot = {"precautions": [{"text": "임신 중에는 섭취 전 전문가와 상담하십시오."}]}
    called = False

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal called
        called = True
        return {"message": {"content": "{}"}}

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert out is snapshot
    assert called is False


@pytest.mark.asyncio
async def test_best_effort_keeps_original_on_chat_failure() -> None:
    snapshot = {"precautions": [{"text": "Store in a cool dry place."}]}

    async def _boom(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise RuntimeError("ollama unreachable")

    out = await localize_snapshot_to_korean(snapshot, chat=_boom, model="m")
    assert out["precautions"][0]["text"] == "Store in a cool dry place."


@pytest.mark.asyncio
async def test_batch_count_mismatch_falls_back_to_per_item_translation() -> None:
    # When the batched call returns the wrong count, each section is retried on its
    # own (one text per call is reliable) instead of leaving everything in English.
    snapshot = {
        "precautions": [
            {"text": "Consult your physician."},
            {"text": "Keep out of reach of children."},
        ],
    }

    async def _chat(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        content = payload["messages"][0]["content"]
        if "\n2. " in content:  # multi-text batch → return a wrong (short) count
            return {"message": {"content": json.dumps({"translations": ["하나만"]})}}
        return {"message": {"content": json.dumps({"translations": ["번역됨"]})}}

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert len(out["precautions"]) == 2
    assert out["precautions"][0]["text"] == "번역됨"
    assert out["precautions"][1]["text"] == "번역됨"


@pytest.mark.asyncio
async def test_per_item_fallback_keeps_original_when_an_item_still_fails() -> None:
    # If even the per-item retry yields nothing usable, that item keeps its original.
    snapshot = {
        "precautions": [
            {"text": "Consult your physician."},
            {"text": "Keep out of reach of children."},
        ],
    }

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"message": {"content": "not json"}}  # always unusable

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert out["precautions"][0]["text"] == "Consult your physician."
    assert out["precautions"][1]["text"] == "Keep out of reach of children."


@pytest.mark.asyncio
async def test_coalesces_word_fragmented_precautions_before_translating() -> None:
    # Word-level OCR boxes split one precaution into single-word items; they are
    # merged into a single item and translated as one coherent Korean sentence.
    snapshot = {
        "precautions": [
            {"text": "Consult", "category": "medication", "severity": "caution"},
            {"text": "pregnant"},
            {"text": "nursing,"},
            {"text": "medication,"},
            {"text": "children."},
        ],
    }
    captured: dict[str, Any] = {}

    async def _chat(payload: Mapping[str, Any]) -> Mapping[str, Any]:
        captured["content"] = payload["messages"][0]["content"]
        return {
            "message": {
                "content": json.dumps(
                    {
                        "translations": [
                            "임신, 수유 중이거나 약물 복용 중이거나 어린이는 전문가와 상담하세요."
                        ]
                    }
                )
            }
        }

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert len(out["precautions"]) == 1
    assert out["precautions"][0]["text"].startswith("임신")
    assert out["precautions"][0]["category"] == "medication"  # first fragment's metadata kept
    # The model received ONE joined text, not five numbered fragments.
    assert "\n2. " not in captured["content"]
    assert "Consult pregnant nursing, medication, children." in captured["content"]


@pytest.mark.asyncio
async def test_distinct_sentence_precautions_are_not_coalesced() -> None:
    # Two complete (multi-word) precautions are translated separately, not merged.
    snapshot = {
        "precautions": [
            {"text": "Consult your physician."},
            {"text": "Keep out of reach of children."},
        ],
    }

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        return {
            "message": {
                "content": json.dumps(
                    {
                        "translations": [
                            "의사와 상담하세요.",
                            "어린이 손이 닿지 않는 곳에 보관하세요.",
                        ]
                    }
                )
            }
        }

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert len(out["precautions"]) == 2
    assert out["precautions"][0]["text"] == "의사와 상담하세요."
    assert out["precautions"][1]["text"] == "어린이 손이 닿지 않는 곳에 보관하세요."


@pytest.mark.asyncio
async def test_coalesces_korean_word_fragmented_precautions() -> None:
    # CLOVA word-boxes split a Korean caution into single-token items; they merge into
    # one coherent line. Korean is not English-dominant, so NO translation call is made.
    snapshot = {
        "precautions": [
            {"text": "어린이,", "category": "children", "severity": "caution"},
            {"text": "임산부,"},
            {"text": "주의하십시오"},
        ],
    }
    calls = 0

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        nonlocal calls
        calls += 1
        return {"message": {"content": json.dumps({"translations": []})}}

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert len(out["precautions"]) == 1
    assert out["precautions"][0]["text"] == "어린이, 임산부, 주의하십시오"
    assert out["precautions"][0]["category"] == "children"  # first fragment metadata kept
    assert calls == 0  # already Korean → no model round-trip
    assert len(snapshot["precautions"]) == 3  # input snapshot untouched


@pytest.mark.asyncio
async def test_korean_complete_precautions_are_not_coalesced() -> None:
    # Multi-word Korean cautions are complete sentences; left as separate items.
    snapshot = {
        "precautions": [
            {"text": "어린이 손이 닿지 않는 곳에 보관하십시오."},
            {"text": "직사광선을 피해 보관하십시오."},
        ],
    }

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise AssertionError("Korean text must not trigger a translation call")

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert len(out["precautions"]) == 2


@pytest.mark.asyncio
async def test_distinct_short_korean_cautions_are_not_merged() -> None:
    # Space-free but COMPLETE short cautions are sentence-final, so each is its own run
    # and they must NOT collapse into one garbled item (adversarial review HIGH finding).
    snapshot = {
        "precautions": [
            {"text": "냉장보관하십시오."},
            {"text": "직사광선을피하십시오."},
        ],
    }

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise AssertionError("Korean text must not trigger a translation call")

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert [p["text"] for p in out["precautions"]] == [
        "냉장보관하십시오.",
        "직사광선을피하십시오.",
    ]


@pytest.mark.asyncio
async def test_complete_caution_after_fragment_run_is_not_swept_in() -> None:
    # The leading fragment run merges; a trailing standalone complete caution stays
    # separate instead of being absorbed (adversarial review MEDIUM finding).
    snapshot = {
        "precautions": [
            {"text": "어린이,"},
            {"text": "임산부,"},
            {"text": "주의하십시오"},
            {"text": "냉장보관하십시오."},
        ],
    }

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise AssertionError("Korean text must not trigger a translation call")

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert [p["text"] for p in out["precautions"]] == [
        "어린이, 임산부, 주의하십시오",
        "냉장보관하십시오.",
    ]


@pytest.mark.asyncio
async def test_merged_fragment_run_escalates_to_strongest_severity() -> None:
    # A merged run inherits the strongest severity, not just the first fragment's.
    snapshot = {
        "precautions": [
            {"text": "어린이,", "severity": "caution"},
            {"text": "위험하니,", "severity": "warning"},
            {"text": "주의하십시오"},
        ],
    }

    async def _chat(_payload: Mapping[str, Any]) -> Mapping[str, Any]:
        raise AssertionError("Korean text must not trigger a translation call")

    out = await localize_snapshot_to_korean(snapshot, chat=_chat, model="m")
    assert len(out["precautions"]) == 1
    assert out["precautions"][0]["severity"] == "warning"
