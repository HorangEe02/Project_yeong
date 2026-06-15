"""Phase B 도메인 A/B 검증 — 답변 수집.

현재 provider (`config.LLM_PROVIDER`) 기준으로 8 골든 query 의 답변 수집 → JSON 저장.
Vertex/Ollama 양쪽 수집 후 phase_b_ab_render.py 가 markdown 합성.

실행:
  docker compose exec -T backend python3 /app/scripts/phase_b_ab_collect.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/app")

import config
from features.compliance.regulation_qa import _call_llm

QUERIES: list[dict] = [
    {
        "id": 1,
        "feature": "rag_answer",
        "prompt": "산업안전보건법 제38조 사업주 안전조치 의무를 한 문장으로 요약하시오.",
        "kw": {"num_predict": 400},
    },
    {
        "id": 2,
        "feature": "rag_answer",
        "prompt": "물질안전보건자료(MSDS) 작성 시 GHS 분류 항목은 16개 섹션 중 어느 섹션에 위치합니까? 근거와 함께 답하시오.",
        "kw": {"num_predict": 400},
    },
    {
        "id": 3,
        "feature": "rag_answer",
        "prompt": "자동차 부품 품질 도메인에서 PPAP(Production Part Approval Process) 5단계 흐름과 8D 보고서 흐름의 차이를 비교 설명하시오.",
        "kw": {"num_predict": 600},
    },
    {
        "id": 4,
        "feature": "rag_answer",
        "prompt": "EU CBAM(탄소국경조정메커니즘)이 한국 자동차 부품 수출에 미치는 영향을 시점·품목·세율 관점에서 설명하시오.",
        "kw": {"num_predict": 600},
    },
    {
        "id": 5,
        "feature": "rag_answer",
        "prompt": "30인 미만 사업장의 산업안전보건위원회 설치 의무 여부와 그 근거 조항을 답하시오.",
        "kw": {"num_predict": 400},
    },
    {
        "id": 6,
        "feature": "quiz_gen",
        "prompt": (
            "산업안전보건법상 사업주의 안전보건 교육 의무에 관한 5지선다 퀴즈 1개를 "
            "JSON 으로 출력하시오. 형식: "
            '{"question": "...", "options": ["A","B","C","D","E"], "answer_index": 0, "explanation": "..."}'
        ),
        "kw": {"num_predict": 500, "format": "json", "temperature": 0.2},
    },
    {
        "id": 7,
        "feature": "short_answer_grade",
        "prompt": (
            '학생 답안: "사업주는 근로자에게 안전모를 지급해야 하며 이를 위반하면 과태료가 부과된다"\n'
            "기준: 산업안전보건법 제38조 안전조치 의무.\n"
            "위 학생 답안을 5점 만점으로 채점하고 점수와 채점 근거를 답하시오."
        ),
        "kw": {"num_predict": 400},
    },
    {
        "id": 8,
        "feature": "whatif_nl_route",
        "prompt": (
            "다음 시나리오를 JSON 으로 분류하시오: "
            '"원자재 관세 25% 인상 + 환율 +5% 동시 발생 시 내년 영업이익 영향". '
            'JSON 형식: {"scenario_dim": [...], "variables": {...}, "expected_impact": "..."}'
        ),
        "kw": {"num_predict": 500, "format": "json", "temperature": 0.1},
    },
]


def main() -> None:
    provider = config.LLM_PROVIDER
    print(f"[collect] provider={provider}, queries={len(QUERIES)}")
    print(f"[routes] " + " ".join(
        f"{f}={config.resolve_llm_route(f)[2]}"
        for f in ("rag_answer", "quiz_gen", "short_answer_grade", "whatif_nl_route")
    ))

    results: list[dict] = []
    for q in QUERIES:
        feature = q["feature"]
        prompt = q["prompt"]
        kw = dict(q.get("kw") or {})
        kw.setdefault("timeout", 120.0)
        t0 = time.time()
        answer = _call_llm(prompt, feature=feature, **kw)
        dt = round(time.time() - t0, 2)
        route = config.resolve_llm_route(feature)
        text = (answer or "").strip()
        print(f"  [Q{q['id']}] {feature} {dt:>5.2f}s len={len(text)}")
        results.append({
            "id": q["id"],
            "feature": feature,
            "prompt": prompt,
            "provider": provider,
            "model": route[2],
            "latency_s": dt,
            "answer": text,
        })

    out_path = Path(f"/tmp/phase_b_ab_{provider}.json")
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for r in results if r["answer"])
    print(f"[saved] {out_path} — {ok}/{len(results)} non-empty answers")


if __name__ == "__main__":
    main()
