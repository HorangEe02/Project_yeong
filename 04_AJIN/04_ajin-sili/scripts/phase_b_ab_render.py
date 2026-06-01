"""Phase B 도메인 A/B 검증 — markdown viewer 합성.

phase_b_ab_collect.py 가 생성한 /tmp/phase_b_ab_vertex.json + /tmp/phase_b_ab_ollama.json
2 파일을 합쳐 docs/PHASE_B_AB_VALIDATION.md 생성.

실행 (호스트):
  python3 scripts/phase_b_ab_render.py
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERTEX_JSON = Path("/tmp/phase_b_ab_vertex.json")
OLLAMA_JSON = Path("/tmp/phase_b_ab_ollama.json")
OUT_PATH = ROOT / "docs" / "PHASE_B_AB_VALIDATION.md"


def _cell(text: str, max_chars: int = 600) -> str:
    r"""Markdown 표 셀용 escape — newline → <br>, pipe → \|."""
    if not text:
        return "_(빈 응답)_"
    truncated = text[:max_chars]
    suffix = "..." if len(text) > max_chars else ""
    return (truncated + suffix).replace("\n", "<br>").replace("|", "\\|")


def main() -> None:
    if not VERTEX_JSON.exists():
        raise SystemExit(f"missing: {VERTEX_JSON} — run phase_b_ab_collect.py with LLM_PROVIDER=vertex first")
    if not OLLAMA_JSON.exists():
        raise SystemExit(f"missing: {OLLAMA_JSON} — run phase_b_ab_collect.py with LLM_PROVIDER=ollama first")

    v = json.loads(VERTEX_JSON.read_text(encoding="utf-8"))
    o = json.loads(OLLAMA_JSON.read_text(encoding="utf-8"))

    if len(v) != len(o):
        raise SystemExit(f"length mismatch: vertex={len(v)} ollama={len(o)}")

    lines: list[str] = [
        "# Phase B 도메인 A/B 검증 — Vertex (gemini-2.5-flash) vs Ollama (qwen3.5)",
        "",
        f"수집 일시: {datetime.datetime.now():%Y-%m-%d %H:%M}",
        "",
        "**평가 척도** (5점 만점, 도메인 전문가 작성):",
        "- 5 = 탁월 — 인용·근거 정확, 즉시 사용 가능",
        "- 4 = 좋음 — 실용 수준, 미세 보완만",
        "- 3 = 수용 가능 — 일부 보완 필요",
        "- 2 = 불충분 — 핵심 누락 또는 일부 오류",
        "- 1 = 명백한 오류 — 사실관계 틀림 / 답변 불가",
        "",
        "**평가 차원**: 정확도 (조문/시점/수치) · 완전성 (질문 모두 답함) · 명료성 (이해도)",
        "",
        "---",
        "",
    ]

    for vi, oi in zip(v, o):
        if vi["id"] != oi["id"] or vi["feature"] != oi["feature"]:
            raise SystemExit(f"query mismatch at id={vi['id']}: feature {vi['feature']} vs {oi['feature']}")
        lines.append(f"## Query {vi['id']} — `{vi['feature']}`")
        lines.append("")
        lines.append(f"**질문**: {vi['prompt']}")
        lines.append("")
        v_hdr = f"Vertex `{vi['model']}` ({vi['latency_s']}s)"
        o_hdr = f"Ollama `{oi['model']}` ({oi['latency_s']}s)"
        lines.append(f"| | {v_hdr} | {o_hdr} |")
        lines.append("|---|---|---|")
        lines.append(f"| 답변 | {_cell(vi['answer'])} | {_cell(oi['answer'])} |")
        lines.append("| 정확도 (1-5) | _ | _ |")
        lines.append("| 완전성 (1-5) | _ | _ |")
        lines.append("| 명료성 (1-5) | _ | _ |")
        lines.append("| 비고 |  |  |")
        lines.append("")

    lines.extend([
        "---",
        "",
        "## 결과 종합 (도메인 전문가 작성)",
        "",
        "| | Vertex 평균 | Ollama 평균 |",
        "|---|---|---|",
        "| 정확도 | _ | _ |",
        "| 완전성 | _ | _ |",
        "| 명료성 | _ | _ |",
        "| **종합** | _ | _ |",
        "",
        "**추천 결정** (해당 항목에 ✓):",
        "- [ ] Vertex 유지 (Vertex 평균 ≥ 3.5/5 + Ollama 동등 이하)",
        "- [ ] Pro swap (특정 feature 만 부족 — `LLM_MODEL_<F>_VERTEX=gemini-2.5-pro`)",
        "- [ ] Ollama 복귀 (전 feature 부족 — `.env.docker` 의 `LLM_PROVIDER=vertex` 주석화)",
        "",
        "**의견·메모**:",
        "",
        "_여기에 도메인 전문가 종합 의견 기재_",
        "",
    ])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"saved {OUT_PATH} — {len(v)} queries × 2 providers")


if __name__ == "__main__":
    main()
