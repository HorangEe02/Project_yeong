"""v3.3 Feature C — 베이스라인 메트릭 측정 스크립트 (Phase 0-5).

사용법:
    python scripts/measure_baseline.py --section llm --runs 10
    python scripts/measure_baseline.py --section upload --runs 10
    python scripts/measure_baseline.py --section all --runs 10

산출:
    update_log/v3.3_update/baseline_results.json — 측정 결과 (P50/P95)
    update_log/v3.3_update/BASELINE_METRICS.md — 사람이 읽는 표 갱신 (수동)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

# 프로젝트 루트를 path 에 추가
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

REPO_ROOT = ROOT.parent  # ajin-ai-assistant-react/ 의 상위 (02_AJIN/)
RESULTS_PATH = REPO_ROOT / "update_log" / "v3.3_update" / "baseline_results.json"

STANDARD_PROMPT_KO = "프레스 트라이 SOP를 단계별로 알려줘. 각 단계는 한 줄로."

OLLAMA_MODELS = [
    "qwen3.5:9b",
    "qwen3.5:4b",
    "gemma4:e4b",
    "gemma4:e2b",
    "exaone3.5:latest",
]


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    k = (len(s) - 1) * (p / 100.0)
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


async def measure_llm_ttft(
    model: str,
    provider: str = "ollama",
    runs: int = 10,
) -> dict:
    """Time To First Token + 총 지연 측정."""
    from core.llm_router import LLMRouter
    from core.llm_types import LLMMode

    router = LLMRouter()
    ttft_ms: list[float] = []
    total_ms: list[float] = []
    response_chars: list[int] = []

    # 1회 워밍 (콜드 스타트 제외)
    print(f"  [WARM] {provider}/{model}", flush=True)
    try:
        async for _ in router.stream(
            prompt=STANDARD_PROMPT_KO,
            mode=LLMMode.CHAT_KOREAN,
            force_provider=(provider, model),
        ):
            pass
    except Exception as e:
        print(f"  [WARM FAIL] {provider}/{model}: {e}", flush=True)
        return {"model": model, "provider": provider, "error": str(e)}

    for i in range(runs):
        start = time.monotonic()
        first_token_at: float | None = None
        chars = 0
        try:
            async for ev in router.stream(
                prompt=STANDARD_PROMPT_KO,
                mode=LLMMode.CHAT_KOREAN,
                force_provider=(provider, model),
            ):
                if ev.get("type") == "token":
                    if first_token_at is None:
                        first_token_at = time.monotonic()
                    chars += len(ev.get("content", ""))
        except Exception as e:
            print(f"  [RUN {i+1} FAIL] {e}", flush=True)
            continue

        end = time.monotonic()
        if first_token_at is not None:
            ttft_ms.append((first_token_at - start) * 1000.0)
        total_ms.append((end - start) * 1000.0)
        response_chars.append(chars)
        print(f"  [{i+1}/{runs}] TTFT={ttft_ms[-1]:.0f}ms total={total_ms[-1]:.0f}ms chars={chars}", flush=True)

    return {
        "model": model,
        "provider": provider,
        "runs": runs,
        "ttft_p50_ms": round(percentile(ttft_ms, 50), 1) if ttft_ms else None,
        "ttft_p95_ms": round(percentile(ttft_ms, 95), 1) if ttft_ms else None,
        "total_p50_ms": round(percentile(total_ms, 50), 1) if total_ms else None,
        "total_p95_ms": round(percentile(total_ms, 95), 1) if total_ms else None,
        "chars_avg": round(statistics.mean(response_chars), 1) if response_chars else None,
    }


def measure_upload_extract(fixtures_dir: Path, runs: int = 10) -> list[dict]:
    """파일 업로드 + 추출 시간 측정."""
    from core.llm_client import extract_text_from_file

    if not fixtures_dir.exists():
        print(f"[SKIP] fixtures dir not found: {fixtures_dir}", flush=True)
        return []

    results = []
    for f in sorted(fixtures_dir.iterdir()):
        if not f.is_file():
            continue
        data = f.read_bytes()
        durations: list[float] = []
        chars: list[int] = []
        for i in range(runs):
            start = time.monotonic()
            try:
                text = extract_text_from_file(data, f.name)
            except Exception as e:
                print(f"  [{f.name} RUN {i+1} FAIL] {e}", flush=True)
                continue
            durations.append((time.monotonic() - start) * 1000.0)
            chars.append(len(text or ""))
        results.append({
            "filename": f.name,
            "size_bytes": len(data),
            "extract_p50_ms": round(percentile(durations, 50), 1) if durations else None,
            "extract_p95_ms": round(percentile(durations, 95), 1) if durations else None,
            "extracted_chars_avg": round(statistics.mean(chars), 1) if chars else None,
        })
        print(f"  [{f.name}] size={len(data)} P50={results[-1]['extract_p50_ms']}ms", flush=True)
    return results


async def run_llm_section(provider: str, runs: int) -> list[dict]:
    results = []
    if provider in ("ollama", "all"):
        for m in OLLAMA_MODELS:
            print(f"\n[LLM] ollama/{m} × {runs}", flush=True)
            results.append(await measure_llm_ttft(m, "ollama", runs))
    if provider in ("gemini", "all"):
        import os
        if not os.environ.get("GEMINI_API_KEY"):
            print("[SKIP] GEMINI_API_KEY 미설정 — Gemini 측정 생략", flush=True)
        else:
            for m in ("gemini-2.5-pro", "gemini-2.5-flash"):
                print(f"\n[LLM] gemini/{m} × {runs}", flush=True)
                results.append(await measure_llm_ttft(m, "gemini", runs))
    return results


def save_results(payload: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\n[SAVED] {RESULTS_PATH}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", choices=["llm", "upload", "all"], default="all")
    parser.add_argument("--provider", choices=["ollama", "gemini", "all"], default="all")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--fixtures", default="tests/fixtures/baseline/")
    args = parser.parse_args()

    payload: dict = {
        "measured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "host": __import__("platform").node(),
        "python": __import__("sys").version.split()[0],
        "runs": args.runs,
    }

    if args.section in ("llm", "all"):
        payload["llm"] = asyncio.run(run_llm_section(args.provider, args.runs))

    if args.section in ("upload", "all"):
        fixtures = ROOT / args.fixtures
        payload["upload"] = measure_upload_extract(fixtures, args.runs)

    save_results(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
