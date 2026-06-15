"""P1 D4 — RAG 답변 생성 (자연어 Q&A + 신입 풀이 모드).

검색 (regulation_indexer.search) → top-k 청크 → LLM (Ollama 또는 Gemini) 답변.

설계:
  1. 신입 모드 자동 활성 — user.hire_date 6개월 이내면 시스템 프롬프트 톤 변경.
  2. 인용 강제 — 답변 끝에 [regulation_id, item_title] 청크 출처 부착.
  3. RAG miss (top-k=0) — "확신할 수 없음" 안전 응답 (가짜 답변 절대 X).
  4. LLM 미연결 시 — 검색 결과 본문을 그대로 노출하는 폴백 응답.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# 신입 모드 판단
# ─────────────────────────────────────────────────────────────

NOVICE_MONTHS = 6


def is_novice(user: Any) -> bool:
    """user.hire_date 기반 신입 여부 (6개월 이내)."""
    if user is None:
        return False
    hire_date_str = getattr(user, "hire_date", None) or (
        user.get("hire_date") if isinstance(user, dict) else None
    )
    if not hire_date_str:
        return False
    try:
        hire = datetime.strptime(str(hire_date_str)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return False
    return (date.today() - hire) <= timedelta(days=NOVICE_MONTHS * 30)


# ─────────────────────────────────────────────────────────────
# 시스템 프롬프트
# ─────────────────────────────────────────────────────────────

_PROMPT_DEFAULT = """당신은 아진산업 사내 규제·법규 안내 AI입니다.
주어진 규제 본문 (검색 결과) 만 참고하여 한국어로 답변하세요.

원칙:
1. 본문에 없는 내용은 추측하지 말고 "확신할 수 없습니다"라고 답변.
2. 답변 끝에 인용 출처 (규제 ID, 항목명) 를 자동 첨부.
3. 5문장 이내, 핵심부터 답변.
4. AI 자문은 참고용이며 최종 판단은 담당자라고 명시."""

_PROMPT_NOVICE = """당신은 아진산업 신입사원에게 규제·법규를 평이하게 풀어주는 사내 AI 입니다.
주어진 규제 본문 (검색 결과) 만 참고하여 한국어로 답변하세요.

원칙:
1. 전문용어는 평이한 한국어로 풀어서 설명.
2. 가능하면 우리 회사 (아진산업) 사례·공정·부서를 비유로 사용.
3. 본문에 없는 내용은 추측 금지 — "확신할 수 없습니다" 또는 "사수에게 문의" 라고 안내.
4. 답변 끝에 인용 출처 (규제 ID, 항목명) 를 자동 첨부.
5. 신입사원이 첫 6개월 이해하기 좋은 톤. 문장 짧게.
6. AI 자문은 참고용이며 최종 판단은 담당자라고 명시."""


def _build_prompt(query: str, hits: list[dict], novice: bool) -> str:
    """RAG 컨텍스트 포함 프롬프트 빌드."""
    sys = _PROMPT_NOVICE if novice else _PROMPT_DEFAULT
    if not hits:
        return (f"{sys}\n\n[검색 결과] 없음.\n\n[질문] {query}\n\n"
                "검색 결과가 없으므로 '확신할 수 없습니다. 부서장 또는 총무인사팀에 문의하세요' 라고 답변하세요.")

    context_lines = []
    for i, h in enumerate(hits, 1):
        meta = h.get("metadata", {}) or {}
        title = meta.get("item_title") or meta.get("item_id") or "(미상)"
        body = (h.get("document") or "")[:800]
        context_lines.append(f"[출처 {i}] {title}\n{body}")
    ctx = "\n\n".join(context_lines)

    return f"{sys}\n\n[검색 결과]\n{ctx}\n\n[질문] {query}\n\n[답변]"


# ─────────────────────────────────────────────────────────────
# LLM 호출
# ─────────────────────────────────────────────────────────────


def _call_ollama(
    prompt: str,
    timeout: float = 15.0,
    *,
    feature: str = "default",
    format: str | None = None,
    temperature: float = 0.2,
    num_predict: int = 600,
    think: bool = False,
) -> str | None:
    """Ollama generate 호출. feature 인자로 base URL + 모델 라우팅 (Phase 2).

    Phase 2 호환: feature 미지정 시 OLLAMA_BASE_URL + LLM_MODEL 로 폴백 → Phase 1 동작 유지.
    `think` 기본 False — qwen3 류 thinking 모델의 chain-of-thought 토큰 소모 차단.
    True 로 opt-in 시 thinking 활성 (긴 추론이 필요한 호출만).

    Phase B: provider 가 "vertex" 면 None 반환 (graceful skip). 호출자는 _call_llm dispatcher 권장.
    """
    try:
        from config import resolve_llm_route, ollama_headers
    except ImportError:
        return None
    provider, base_url, model = resolve_llm_route(feature)
    if provider != "ollama" or not base_url:
        return None

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": think,
        "options": {"temperature": temperature, "num_predict": num_predict},
    }
    if format:
        payload["format"] = format

    try:
        r = httpx.post(
            f"{base_url}/api/generate",
            headers={**ollama_headers(), "Content-Type": "application/json"},
            json=payload,
            timeout=timeout,
        )
        r.raise_for_status()
        # Phase 2 Stage 1 dry-run — 라우팅 적중 가시화. 종료 시 DEBUG 강등.
        logger.debug("ollama_call feature=%s model=%s base=%s", feature, model, base_url)
        return (r.json().get("response") or "").strip()
    except (httpx.HTTPError, json.JSONDecodeError) as e:
        logger.warning("Ollama 호출 실패 (feature=%s): %s", feature, e)
        return None


def _call_vertex(
    prompt: str,
    timeout: float = 60.0,
    *,
    feature: str = "default",
    format: str | None = None,
    temperature: float = 0.2,
    num_predict: int = 600,
    think: bool = False,  # Vertex 미적용 — 시그니처 호환만
) -> str | None:
    """Vertex AI Gemini 호출 (google-genai SDK, vertexai=True 모드).

    format='json' 시 response_mime_type 지정. 실패·미연결 시 None 반환.
    Gemini 2.5+ 는 thinking 모드가 default — `think=False` 시 thinking_budget=0 으로 비활성.
    """
    try:
        from config import resolve_llm_route, VERTEX_LOCATION
    except ImportError:
        return None
    provider, project_id, model = resolve_llm_route(feature)
    if provider != "vertex" or not project_id:
        return None

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("Vertex 호출 실패 (feature=%s): google-genai SDK 미설치", feature)
        return None

    try:
        client = genai.Client(vertexai=True, project=project_id, location=VERTEX_LOCATION)
        gen_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": num_predict,
        }
        if format == "json":
            gen_kwargs["response_mime_type"] = "application/json"
        if not think:
            # Gemini 2.5+ thinking 비활성 — output 0 토큰 회피 + 비용/지연 절감
            gen_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
        r = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**gen_kwargs),
        )
        logger.debug("vertex_call feature=%s model=%s project=%s", feature, model, project_id)
        return (getattr(r, "text", "") or "").strip()
    except Exception as e:
        logger.warning("Vertex 호출 실패 (feature=%s): %s", feature, e)
        return None


def _call_llm(
    prompt: str,
    timeout: float = 15.0,
    *,
    feature: str = "default",
    format: str | None = None,
    temperature: float = 0.2,
    num_predict: int = 600,
    think: bool = False,
) -> str | None:
    """통합 LLM dispatcher — Phase B 권장 진입점.

    config.resolve_llm_route 가 반환하는 provider 에 따라 _call_ollama 또는 _call_vertex 호출.
    Vertex 실패 시 자동 폴백 없음 (명시 폴백은 호출자 책임 — 룰 폴백 등).
    """
    try:
        from config import resolve_llm_route
    except ImportError:
        return None
    provider, _, _ = resolve_llm_route(feature)
    if provider == "vertex":
        return _call_vertex(prompt, timeout=timeout, feature=feature, format=format,
                            temperature=temperature, num_predict=num_predict, think=think)
    return _call_ollama(prompt, timeout=timeout, feature=feature, format=format,
                        temperature=temperature, num_predict=num_predict, think=think)


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────


def answer_question(query: str, user: Any = None, top_k: int = 5,
                    legal_class: str | None = None) -> dict[str, Any]:
    """자연어 질문 → RAG 답변 + 인용 출처.

    Returns:
        {
            "answer": "본문 답변 + 인용",
            "citations": [{regulation_type, item_id, item_title, change_id}, ...],
            "novice_mode": bool,
            "rag_hit": bool,  # 검색 결과 ≥1 건이면 True
        }
    """
    from features.compliance.infra.regulation_indexer import search

    novice = is_novice(user)
    hits = search(query, top_k=top_k, legal_class=legal_class)

    citations: list[dict[str, Any]] = []
    for h in hits:
        m = h.get("metadata", {}) or {}
        citations.append({
            "change_id": int(m.get("change_id") or 0),
            "regulation_type": str(m.get("regulation_type") or ""),
            "item_id": str(m.get("item_id") or ""),
            "item_title": str(m.get("item_title") or ""),
            "grade": str(m.get("grade") or "MEDIUM"),
            "distance": float(h.get("distance") or 0.0),
        })

    # RAG miss — 안전 응답 (가짜 답변 X)
    if not hits:
        safe = (
            "검색 결과가 없습니다. 확신할 수 없으므로 부서장 또는 총무인사팀에 문의하시거나, "
            "변경 피드 페이지에서 직접 검색해 주세요.\n\n"
            "※ AI 자문은 참고용 — 최종 판단은 담당자."
        )
        return {
            "answer": safe,
            "citations": [],
            "novice_mode": novice,
            "rag_hit": False,
        }

    # LLM 호출 (Phase B: dispatcher — Vertex 활성 시 자동 라우팅)
    prompt = _build_prompt(query, hits, novice)
    llm_answer = _call_llm(prompt, feature="rag_answer")

    if llm_answer:
        # 인용 자동 첨부
        cite_lines = "\n".join(
            f"- [{c['item_title']}] {c['regulation_type']} / {c['item_id']}"
            for c in citations
        )
        full = f"{llm_answer}\n\n출처:\n{cite_lines}\n\n※ AI 자문은 참고용 — 최종 판단은 담당자."
        return {
            "answer": full,
            "citations": citations,
            "novice_mode": novice,
            "rag_hit": True,
        }

    # LLM 미연결 폴백 — 검색 결과 본문을 그대로 노출 (가짜 답변 X, 사용자가 직접 본문 확인)
    body_lines = []
    for i, h in enumerate(hits, 1):
        m = h.get("metadata", {}) or {}
        body_lines.append(f"[{i}] {m.get('item_title', '(미상)')}")
        body_lines.append((h.get("document") or "")[:400])
        body_lines.append("")
    fallback = "LLM 답변 생성 미가용 — 검색 결과를 직접 확인하세요.\n\n" + "\n".join(body_lines)
    fallback += "\n※ AI 자문은 참고용 — 최종 판단은 담당자."
    return {
        "answer": fallback,
        "citations": citations,
        "novice_mode": novice,
        "rag_hit": True,
    }
