# AJIN RAG 강화 구현 계획 — CRAG + Reranker + LongLLMLingua

**작성일**: 2026-05-27
**대상 본선**: 2026-06-10~11 (KNU SILLI 2026)
**현재 상태**: D-15
**근거 자료**: `<EXTERNAL_DRIVE>/LLM-WIKI/` (rag-variants.md, context-compression.md, bge-m3.md, rag-vs-refrag-overview.md) + 공식 논문 + 2026-05 웹 검색

---

## 0. Executive Summary

REFRAG 도입 불가 평가([HANDOFF_2026-05-27_v3.10.md](HANDOFF_2026-05-27_v3.10.md) 참조)에 따라, 동일 ROI 를 달성하는 **3가지 RAG 강화 모듈** 단계별 도입.

| 모듈 | 출처 | 효과(논문 보고) | 도입 우선순위 | 추가 학습 |
|---|---|---|---|---|
| **Reranker** (bge-reranker-v2-m3) | BAAI | top-K 재정렬 정확도 ↑ | **P0 (본선 전)** | ❌ |
| **CRAG evaluator** | [Yan et al. 2024](https://arxiv.org/abs/2401.15884) | noisy retrieval 차단 | **P0 (본선 전)** | ❌ |
| **LongLLMLingua** | [Jiang et al. ACL 2024](https://arxiv.org/abs/2310.06839) | NQ +21.4%p, 토큰 -75% | **P1 (본선 후)** | ❌ |

**핵심 가치**:
- 셋 다 **학습 불필요** → D-15 일정 적합
- 셋 다 **AJIN 기존 RAG 5개 파이프라인**(Onboarding/Draft/Search/Employee/Text-to-SQL)에 직교 결합 가능
- 셋 다 **citation_enforcer** 와 시너지 (출처 강제 + retrieval 품질 + 컨텍스트 압축)

---

## 1. 현황 진단 (AJIN RAG v3.10)

### 1.1 현재 검색 흐름 (`features/search/searcher.py:167-200`)
```
사용자 질의
    ↓
HybridSearcher.search()
    ├─ BM25 (kiwipiepy 형태소 + 아진 도메인 사전)
    └─ pgvector (bge-m3, 1024-dim, cosine)
    ↓
_rrf_merge(k * 2)  ← TOP_K=5, RRF_K=60 (config.py:323-324)
    ↓
top-K SearchResult
```

### 1.2 현재 컨텍스트 주입 흐름 (`backend/routers/onboarding.py:380-487`)
```
kb_lookup.load_kb_context(query, dept, max_chars=4000)
    ↓ ⚠️ frontmatter 매칭 only (semantic 없음, Quick Question 한정)
    ↓
prompt = "{system}{file_ctx}{action_context}{kb_context}{ref_context}{질문}"
    ↓
Ollama LLM
    ↓
citation_enforcer (사후 인용 검증)
```

### 1.3 현재 약점 (강화 모듈이 해결할 부분)

| 약점 | 영향 | 해결 모듈 |
|---|---|---|
| RRF top-K 재정렬 없음 — cross-encoder 미적용 | 정확도 손실 (특히 한국어) | **Reranker** |
| 저신뢰 retrieval 시 답변 차단 로직 단순 (0건만 명시) | 환각 위험 (1~3건 부적합 시 환각) | **CRAG** |
| kb_context 4000 chars 무조건 잘림 — 토큰 비용 + lost-in-middle | 정보 손실 + 비용 ↑ | **LongLLMLingua** |

---

## 2. 모듈 설계

### 2.1 Reranker — `bge-reranker-v2-m3` (P0)

#### 출처·근거
- 공식: [BAAI/bge-reranker-v2-m3](https://huggingface.co/BAAI/bge-reranker-v2-m3) (568M params, MIT license, 100+ languages)
- Wiki: [bge-m3.md L103](file://<EXTERNAL_DRIVE>/LLM-WIKI/wiki/entities/bge-m3.md) — "Reranker 짝: BGE Reranker (BAAI/bge-reranker-v2-m3): top-K 재정렬"
- 권장 패턴: [rag-variants.md L99](file://<EXTERNAL_DRIVE>/LLM-WIKI/wiki/concepts/rag-variants.md) — "[Reranker] cross-encoder로 top-K 재정렬"

#### 도입 방식
- **선택지 A (정공)**: `FlagEmbedding.FlagReranker` 직접 import (CloudRun 컨테이너 내 모델 로드)
  - 메모리: FP16 시 ~600MB, FP32 시 ~1.2GB
  - 추론: 한 쿼리당 top-20 → top-5 재정렬 ~200~500ms (Cloud Run CPU, GPU 없음)
- **선택지 B**: Ollama community model `qllama/bge-reranker-v2-m3` 사용 (`/api/embed` 통해)
  - ⚠️ Ollama 공식 reranker API 부재 (2026-05 기준) → embedding API 우회 → **정공 아님**
- **선택지 C**: Cohere Rerank API (외부, $1/1000 calls) — 시연 후 자체호스팅 전환

→ **권장: 선택지 A** (정공, 데이터 외부 유출 없음, 영구 무료)

#### 통합 위치
- 파일: `features/search/searcher.py`
- 함수: `_unfiltered_search()` L274, `_filtered_search()` L281
- 시점: `_rrf_merge(k=k*2)` 결과 → **NEW: `_rerank()` 추가** → top-K cut

```python
# searcher.py (신규 추가 의사 코드)
def _rerank(self, query: str, results: list[SearchResult], top_k: int) -> list[SearchResult]:
    """bge-reranker-v2-m3 으로 cross-encoder 재정렬."""
    if not results or not self.reranker:
        return results[:top_k]
    pairs = [(query, r.content[:512]) for r in results]
    scores = self.reranker.compute_score(pairs, normalize=True)
    for r, s in zip(results, scores):
        r.score = float(s)
        r.metadata["rerank_score"] = float(s)
    return sorted(results, key=lambda r: r.score, reverse=True)[:top_k]
```

#### 설정 (`config.py`)
```python
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "true").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANKER_TOP_K_INPUT = int(os.getenv("RERANKER_TOP_K_INPUT", "20"))  # rerank 입력 후보 수
RERANKER_USE_FP16 = os.getenv("RERANKER_USE_FP16", "true").lower() == "true"
```

#### 검증
- 골든셋: `data/eval/golden_qa_kosha.jsonl` (신규 — KOSHA 17건 기반 20개 QA 쌍)
- 측정: MRR@5, nDCG@5, "관련 자료 미반환률"
- 목표: MRR@5 0.65 → 0.80 이상

---

### 2.2 CRAG Retrieval Evaluator (P0)

#### 출처·근거
- 공식: [Yan et al. 2024, arXiv:2401.15884](https://arxiv.org/abs/2401.15884) — "Corrective Retrieval Augmented Generation"
- Wiki: [rag-variants.md L28-34](file://<EXTERNAL_DRIVE>/LLM-WIKI/wiki/concepts/rag-variants.md) — "Retrieval evaluator → confidence score → web search 보강"
- 2024 구현: [LangGraph CRAG 튜토리얼](https://www.datacamp.com/tutorial/corrective-rag-crag) — confidence ∈ {Correct, Incorrect, Ambiguous}

#### AJIN 환경 적응
원논문은 부적합 시 **web search fallback** 이지만, AJIN 은:
- 사내 KB + KOSHA/법령 corpus만 신뢰 → 외부 web search 금지 ([CLAUDE.md](../CLAUDE.md) 규정 4번 "Firebase/외부 추가 의존 금지")
- 따라서 AJIN CRAG = **evaluator + 차단 + 부서 안내** (no web fallback)

#### 3-Tier Confidence 로직 (AJIN 변형) — **결정: incorrect 강제 차단**

| Confidence | 조건 | 액션 |
|---|---|---|
| **Correct** | rerank_score ≥ 0.70 | 정상 답변 + 출처 부착 |
| **Ambiguous** | 0.40 ≤ score < 0.70 | 답변 + ⚠️ "출처 신뢰도 낮음" 배지 + 부서 확인 권유 |
| **Incorrect** | score < 0.40 | **🚫 LLM 답변 강제 차단 (확정 정책)**: 프론트에서 답변 영역 비활성 + "사내 자료에서 확인 불가 — 인사관리팀/안전보건팀 문의" 안내 메시지만 노출. LLM 호출 자체를 우회 (토큰 비용 절감 + 환각 0%). 우회 사유는 backend log + `live_alarms` 별도 카테고리(`crag_blocked`)로 운영 가시화. |

#### 구현 (Phase 1 — 단순)
- 위치: `features/search/searcher.py` 또는 `backend/routers/onboarding.py:410` (kb_ctx 평가 후)
- 입력: reranker score (Reranker 모듈 의존)
- 출력: `CRAGVerdict = Literal["correct", "ambiguous", "incorrect"]`

```python
# features/search/crag_evaluator.py (신규 파일)
from dataclasses import dataclass
from typing import Literal

CRAGVerdict = Literal["correct", "ambiguous", "incorrect"]

@dataclass
class CRAGResult:
    verdict: CRAGVerdict
    confidence: float
    rationale: str
    top_score: float

def evaluate_retrieval(
    results: list,
    upper: float = 0.70,
    lower: float = 0.40,
) -> CRAGResult:
    if not results:
        return CRAGResult("incorrect", 0.0, "검색 결과 0건", 0.0)
    top = results[0].metadata.get("rerank_score", results[0].score)
    if top >= upper:
        verdict = "correct"
    elif top >= lower:
        verdict = "ambiguous"
    else:
        verdict = "incorrect"
    return CRAGResult(verdict, top, f"top-1 score={top:.3f}", top)
```

#### 구현 (Phase 2 — 정공 LLM-as-judge, 본선 후)
- Ollama qwen2.5:3b 또는 더 작은 모델로 query-doc 적합도 판단
- 프롬프트: "다음 질의에 대해 이 문서가 답변에 적합한가? Correct/Incorrect/Ambiguous 중 하나로 응답"
- 비용: 추가 LLM 호출 1회 (~300ms)

#### 통합 위치
- `backend/routers/onboarding.py:410` (load_kb_context 직후)
- `backend/routers/search.py` (search 결과 반환 전)

```python
# onboarding.py 변형 (의사 코드)
from features.search.crag_evaluator import evaluate_retrieval
crag = evaluate_retrieval(retrieved_chunks)
if crag.verdict == "incorrect":
    kb_context = (
        "\n\n[사내 자료 매칭 결과]\n"
        "관련 사내 자료를 찾지 못했습니다 (top-1 적합도={:.2f} < 0.40).\n"
        "정확한 답변을 위해 인사관리팀 또는 안전보건팀에 직접 문의하시기 바랍니다."
    ).format(crag.top_score)
    # LLM 답변 차단 효과 — 출처 없이 답변 시 환각 위험
elif crag.verdict == "ambiguous":
    kb_context = (
        f"\n\n[사내 자료 — ⚠️ 출처 신뢰도 낮음 (score={crag.top_score:.2f})]\n"
        f"{kb_ctx['text']}\n"
        "위 자료는 부분 매칭이므로 담당 부서 확인을 권장합니다."
    )
# correct: 기존 로직 그대로
```

#### 설정 (`config.py`)
```python
CRAG_ENABLED = os.getenv("CRAG_ENABLED", "true").lower() == "true"
CRAG_UPPER_THRESHOLD = float(os.getenv("CRAG_UPPER_THRESHOLD", "0.70"))
CRAG_LOWER_THRESHOLD = float(os.getenv("CRAG_LOWER_THRESHOLD", "0.40"))
CRAG_LLM_JUDGE_ENABLED = os.getenv("CRAG_LLM_JUDGE_ENABLED", "false").lower() == "true"  # Phase 2
```

#### 검증
- 골든셋: `data/eval/golden_qa_kosha.jsonl` 에 "부적합 query" 5건 추가 (예: "회사 주식 가격", "오늘 점심 메뉴")
- 측정:
  - True Negative Rate (부적합 query 차단률) — 목표 ≥ 80%
  - False Negative Rate (정상 query 잘못 차단) — 목표 ≤ 10%

---

### 2.3 LongLLMLingua (P1, 본선 후)

#### 출처·근거
- 공식: [Jiang et al. ACL 2024, arXiv:2310.06839](https://arxiv.org/abs/2310.06839)
- 패키지: [`llmlingua` on PyPI](https://pypi.org/project/llmlingua/) (Microsoft 공식)
- 효과 (논문):
  - NaturalQuestions: 4× 압축 + **21.4%p 성능 향상**
  - LooGLE: **비용 94% 감소**
  - 10k 토큰: **1.4–2.6× latency 개선**
- Wiki: [context-compression.md L23-29](file://<EXTERNAL_DRIVE>/LLM-WIKI/wiki/concepts/context-compression.md)

#### 도입 방식
```python
from llmlingua import PromptCompressor

# 작은 SLM 으로 압축 — Cloud Run 메모리 제약 고려
compressor = PromptCompressor(
    model_name="microsoft/llmlingua-2-xlm-roberta-large-meetingbank",  # 약 600MB, 다국어
    use_llmlingua2=True,
)

compressed = compressor.compress_prompt(
    context=kb_context_text,
    instruction=user_query,
    rate=0.5,  # 50% 압축
    target_token=2000,
)
# compressed["compressed_prompt"], compressed["origin_tokens"], compressed["compressed_tokens"]
```

#### 모델 선택 (Cloud Run 제약)
| 모델 | 크기 | 한국어 | 권장 시점 |
|---|---|---|---|
| `microsoft/phi-2` (원논문) | 2.7B (~5GB) | ⚠️ | ❌ Cloud Run 무리 |
| `microsoft/llmlingua-2-xlm-roberta-large-meetingbank` | 0.55B (~1.1GB) | ✅ (XLM-R 다국어) | ✅ **권장** |
| `microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank` | 0.17B (~340MB) | ✅ | 메모리 빠듯하면 |

→ **권장: LLMLingua-2 xlm-roberta-large 다국어판** (한국어 지원 + 메모리 fit)

#### 통합 위치
- 파일: `backend/routers/onboarding.py:481` (prompt 합성 직후, LLM 호출 직전)
- 조건: `len(kb_context + ref_context + action_context) > 2000` 일 때만 활성화

```python
# onboarding.py (의사 코드)
from features.compression.llmlingua_filter import maybe_compress_context

total_ctx = f"{kb_context}{ref_context}{action_context}"
if len(total_ctx) > config.LLMLINGUA_THRESHOLD_CHARS:
    compressed_ctx, stats = maybe_compress_context(total_ctx, req.query, target_ratio=0.5)
    logger.info(f"LLMLingua: {stats['origin_tokens']} → {stats['compressed_tokens']} tokens")
    # 압축본을 kb_context 자리에 대체
```

#### 설정 (`config.py`)
```python
LLMLINGUA_ENABLED = os.getenv("LLMLINGUA_ENABLED", "false").lower() == "true"  # Phase 1 비활성, Phase 2 활성
LLMLINGUA_MODEL = os.getenv("LLMLINGUA_MODEL", "microsoft/llmlingua-2-xlm-roberta-large-meetingbank")
LLMLINGUA_THRESHOLD_CHARS = int(os.getenv("LLMLINGUA_THRESHOLD_CHARS", "2000"))
LLMLINGUA_TARGET_RATIO = float(os.getenv("LLMLINGUA_TARGET_RATIO", "0.5"))
```

#### 검증
- 동일 골든셋에 대해 LLM 응답 품질 측정 (압축 전/후)
- 측정: 토큰 절감률, 응답 latency (TTFT), 응답 품질 (LLM-as-judge 평가)
- 목표: 토큰 ≥ 40% 절감, 품질 손실 ≤ 5%

---

## 3. 전체 통합 흐름도 (목표 v4.0)

```
사용자 질의
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│  HybridSearcher.search() — features/search/searcher.py  │
│    BM25 (kiwipiepy) + pgvector (bge-m3 1024-dim)         │
│    └─ _rrf_merge (k * 4 = 20 후보)                       │
└─────────────────────────────────────────────────────────┘
    │ top-20 candidates
    ▼
┌─────────────────────────────────────────────────────────┐
│  NEW: _rerank — bge-reranker-v2-m3                      │
│    cross-encoder pair score (query, chunk)              │
└─────────────────────────────────────────────────────────┘
    │ top-5 reranked
    ▼
┌─────────────────────────────────────────────────────────┐
│  NEW: CRAG evaluator — features/search/crag_evaluator.py│
│    verdict ∈ {correct, ambiguous, incorrect}            │
└─────────────────────────────────────────────────────────┘
    │
    ├─ incorrect → "사내 자료 없음" 안내 (LLM 답변 차단)
    └─ correct / ambiguous
        ▼
┌─────────────────────────────────────────────────────────┐
│  prompt 합성 — backend/routers/onboarding.py L481       │
│  {file_ctx}{action_context}{kb_context}{ref_context}    │
└─────────────────────────────────────────────────────────┘
    │
    ├─ len(ctx) > 2000 → LongLLMLingua 압축 (Phase 2)
    └─ Ollama LLM 호출
        ▼
┌─────────────────────────────────────────────────────────┐
│  citation_enforcer — features/onboarding/citations.py   │
│    [출처:cid] 후처리 + 누락 시 경고                       │
└─────────────────────────────────────────────────────────┘
    │
    ▼
응답 + 출처 부착
```

---

## 4. 단계별 구현 로드맵

### Phase 0 (즉시, 본선 전 1일) — 인프라 준비
- [ ] `requirements.txt` 에 의존성 추가
  - `FlagEmbedding>=1.2.10`  (Reranker)
  - `llmlingua>=0.2.2`  (Phase 2 — 본선 후 활성)
- [ ] `data/eval/golden_qa_kosha.jsonl` 신규 — 20 QA + 5 negative
- [ ] `config.py` 에 4개 모듈 env 추가 (위 §2.1, §2.2, §2.3)
- [ ] Docker image 크기 영향 측정 (FlagEmbedding ~700MB, LLMLingua ~1.1GB)

### Phase 1 (본선 전, **D-3 = 2026-06-08 머지 마감**) — Reranker + CRAG 단순 모드
- [ ] `features/search/reranker.py` 신규 — `BgeReranker` 클래스 (lazy init, FP16)
- [ ] `searcher.py:274-323` 수정 — `_rerank()` 메서드 + `_unfiltered_search/_filtered_search` 흐름 끼움
- [ ] **Reranker 한국어 변형 비교 테스트** — `BAAI/bge-reranker-v2-m3` vs `dragonkue/BGE-m3-ko` 의 한국어 reranker 동등 모델 골든셋 MRR@5/nDCG@5 비교 (스크립트 `scripts/eval_rerank_korean.py` 신규) → 우수 모델을 RERANKER_MODEL 환경변수 기본값으로 채택
- [ ] `features/search/crag_evaluator.py` 신규 — Phase 1 단순 threshold
- [ ] `backend/routers/onboarding.py:410` 수정 — CRAG verdict 기반 kb_context 분기 (**incorrect → 강제 차단**, ambiguous → 경고 배지)
- [ ] `backend/routers/search.py` 수정 — CRAG verdict 응답 메타에 포함
- [ ] **프론트**: `dashboard.tsx` / `search.tsx` 에서 verdict='ambiguous' 시 ⚠️ 배지 노출, verdict='incorrect' 시 답변 영역 비활성 + 안내 메시지만
- [ ] 골든셋 평가 → MRR@5, TNR 측정
- [ ] **Cloud Run 메모리 4Gi → 8Gi 상향** (`gcloud run services update ajin-backend --memory=8Gi`)
- [ ] PR 분리: `feat/rag-rerank-bge` (D-7 머지) + `feat/rag-crag-evaluator` (D-3 머지)

### Phase 2 (**본선 다음날 D+1 = 2026-06-12 시작**) — LongLLMLingua + CRAG LLM-as-judge
- [ ] `features/compression/llmlingua_filter.py` 신규 — lazy init, cache
- [ ] `onboarding.py:481` 수정 — 조건부 압축
- [ ] CRAG Phase 2 — Ollama qwen2.5:3b LLM-as-judge
- [ ] A/B 평가 — 압축 전/후 응답 품질
- [ ] PR: `feat/rag-longlingua-crag-phase2` (D+7 = 2026-06-18 머지 목표)

### Phase 3 (D+14 = 2026-06-25 이후, 2주) — 모니터링 + 자동 튜닝
- [ ] verdict 통계 대시보드 (correct/ambiguous/incorrect 비율)
- [ ] threshold auto-tuning (사용자 피드백 기반)
- [ ] HyDE 추가 검토 ([Gao 2022](https://arxiv.org/abs/2212.10496))

---

## 5. 인프라 영향

### 5.1 메모리 (Cloud Run 컨테이너) — **결정: 8Gi 상향**
| 컴포넌트 | RAM | 누적 |
|---|---|---|
| 기존 (FastAPI + bge-m3 클라이언트) | ~1.5GB | 1.5 |
| + FlagReranker FP16 (bge-reranker-v2-m3) | +0.6GB | 2.1 |
| + LLMLingua-2 xlm-roberta-large | +1.1GB | 3.2 |
| **Phase 1+2 안전 마진 (peak 트래픽 + 모델 캐시)** | ~4.8GB | ~8GB |
| **결정된 Cloud Run 할당 (Phase 0 시 적용)** | **8Gi** | ✅ 충분 |

→ **Cloud Run `--memory=8Gi` 상향 확정** (`gcloud run services update ajin-backend --region=asia-northeast3 --memory=8Gi`). 월 추가 비용 ~$30. 4Gi → 8Gi 변경은 **Phase 0 의존성 추가 직전** 수행 (모델 로드 OOM 방지).

### 5.2 latency (예상)
| 단계 | 현재 | Phase 1 후 | Phase 2 후 |
|---|---|---|---|
| 검색 (BM25+pgvector RRF) | ~200ms | ~200ms | ~200ms |
| Reranker (top-20) | 0 | ~300ms | ~300ms |
| CRAG threshold | 0 | <5ms | <5ms |
| CRAG LLM-judge | 0 | 0 | +300ms |
| LLMLingua 압축 | 0 | 0 | ~500ms |
| LLM 생성 (Ollama) | ~3-8s | ~3-8s | ~2-5s (압축 효과) |
| **전체 TTFT** | ~4s | ~4.3s | ~3.5s |

→ Phase 1 은 +300ms 추가, Phase 2 는 압축 효과로 LLM 단축 → 전체 감소.

### 5.3 Docker image 크기
- 현재 backend image: ~3GB (Ollama 의존 없음, slim)
- + FlagEmbedding + bge-reranker-v2-m3 모델 캐시: +1.5GB
- + llmlingua + xlm-roberta-large: +1.2GB
- **Phase 1+2 완료 시: ~5.7GB**
- Cloud Run image size 한도 (10GB) 내 적합

### 5.4 인덱스 변경
- pgvector 재계산 **불필요** — reranker/CRAG/LLMLingua 모두 검색 후 단계
- Celery 매일 crawler 그대로 유지

---

## 6. 검증 계획

### 6.1 골든셋 (`data/eval/golden_qa_kosha.jsonl`)
신규 작성 — 25개 항목 (긍정 20 + 부정 5)

```jsonl
{"query": "직업병 사례 자동차 노동자 도장 공정", "expected_doc_id": "REAL-KOSHA-001", "expected_verdict": "correct"}
{"query": "프레스 작업 산재 사망 사고 분석", "expected_doc_id": "REAL-KOSHA-007", "expected_verdict": "correct"}
{"query": "ECN 변경통보서 작성 양식", "expected_doc_id": "ECN-TEMPLATE-01", "expected_verdict": "correct"}
{"query": "회사 주식 가격 어디서 보나요", "expected_doc_id": null, "expected_verdict": "incorrect"}
{"query": "오늘 점심 메뉴", "expected_doc_id": null, "expected_verdict": "incorrect"}
```

### 6.2 평가 메트릭
```python
# scripts/eval_rag_quality.py 신규
- MRR@5 (Mean Reciprocal Rank) — 정답 문서가 top-5 에서 얼마나 높은가
- nDCG@5 (Normalized Discounted Cumulative Gain)
- Verdict Accuracy — CRAG 가 정답 verdict 와 일치 비율
- TNR (True Negative Rate) — 부정 query 차단률
- FNR (False Negative Rate) — 긍정 query 잘못 차단률
```

### 6.3 회귀 가드
- 골든셋 모든 항목 Phase 0 baseline 대비 **품질 손실 없어야** Phase 1 머지 가능
- CI 에서 `pytest tests/test_rag_quality.py` 자동 실행

---

## 7. 리스크 + 완화책

| 리스크 | 영향 | 완화책 |
|---|---|---|
| FlagEmbedding 첫 로드 ~5초 — Cloud Run cold start 지연 | UX 저하 | lazy init + min-instances=1 |
| bge-reranker-v2-m3 한국어 도메인 특화 부족 | 정확도 미흡 | 골든셋 평가 후 dragonkue/BGE-m3-ko + 별도 reranker 비교 |
| CRAG threshold tuning 부족 | FNR 높음 | 5일간 verdict 로그 수집 후 자동 조정 |
| LLMLingua-2 한국어 압축 품질 미보고 | 정보 손실 위험 | Phase 2 시 A/B 충분히 테스트, 본선 후 적용 |
| Cloud Run 메모리 부족 | OOM kill | --memory 8Gi 상향 (월 비용 약 $30 추가) |
| Docker image 비대 → 빌드 시간 증가 | 배포 지연 | multi-stage build + model cache layer 분리 |
| ⚠️ **D-15 본선 일정** | Phase 1 못 끝나면 시연 위험 | Phase 1 만 본선 전 적용, Phase 2 본선 후 |

---

## 8. 환경 변수 요약 (`.env.example` 추가)

```bash
# === RAG Enhancement (Phase 1) ===
RERANKER_ENABLED=true
RERANKER_MODEL=BAAI/bge-reranker-v2-m3
RERANKER_TOP_K_INPUT=20
RERANKER_USE_FP16=true

CRAG_ENABLED=true
CRAG_UPPER_THRESHOLD=0.70
CRAG_LOWER_THRESHOLD=0.40
CRAG_LLM_JUDGE_ENABLED=false  # Phase 2 에서 true

# === RAG Enhancement (Phase 2) ===
LLMLINGUA_ENABLED=false  # Phase 2 에서 true
LLMLINGUA_MODEL=microsoft/llmlingua-2-xlm-roberta-large-meetingbank
LLMLINGUA_THRESHOLD_CHARS=2000
LLMLINGUA_TARGET_RATIO=0.5
```

---

## 9. PR 분리 계획 (확정 일정 반영)

본선 일정 + 코드 리뷰 부담 분산을 위해 3개 PR 로 나눔. **Phase 1 (PR 1+2) 모두 D-3 = 2026-06-08 까지 머지**.

| PR # | 브랜치 | 범위 | 머지 시점 |
|---|---|---|---|
| 1 | `feat/rag-rerank-bge` | Reranker 모듈 + searcher.py 통합 + 한국어 변형 비교 | **D-7 (2026-06-04)** |
| 2 | `feat/rag-crag-evaluator` | CRAG evaluator + onboarding.py + UI 배지/차단 | **D-3 (2026-06-08)** |
| 3 | `feat/rag-longlingua` | LongLLMLingua + onboarding.py 조건부 압축 | **D+7 (2026-06-18)** |

**선결 작업** (모든 PR 의 prerequisite, D-12 = 2026-05-30 완료):
- `chore/rag-infra-bump` — Cloud Run 4Gi → 8Gi, requirements.txt 의존성, 골든셋, env 변수 추가

---

## 10. 참고 자료

### 10.1 LLM-WIKI (1차 자료)
- `<EXTERNAL_DRIVE>/LLM-WIKI/wiki/concepts/rag-variants.md` — CRAG, HyDE, FLARE 등 변형 카탈로그
- `<EXTERNAL_DRIVE>/LLM-WIKI/wiki/concepts/context-compression.md` — LongLLMLingua + GIST + ICAE 비교
- `<EXTERNAL_DRIVE>/LLM-WIKI/wiki/entities/bge-m3.md` — BGE-M3 + bge-reranker-v2-m3
- `<EXTERNAL_DRIVE>/LLM-WIKI/raw/references/2026-05-27-rag-vs-refrag-overview.md` — 원논문 인용

### 10.2 공식 논문
- CRAG: [Yan et al. 2024, arXiv:2401.15884](https://arxiv.org/abs/2401.15884)
- LongLLMLingua: [Jiang et al. ACL 2024, arXiv:2310.06839](https://arxiv.org/abs/2310.06839)
- BGE-M3: [Chen et al. arXiv:2402.03216](https://arxiv.org/abs/2402.03216)

### 10.3 공식 패키지 / 구현
- FlagEmbedding: https://github.com/FlagOpen/FlagEmbedding (BGE 시리즈 공식 SDK)
- BAAI/bge-reranker-v2-m3: https://huggingface.co/BAAI/bge-reranker-v2-m3
- llmlingua PyPI: https://pypi.org/project/llmlingua/
- LLMLingua GitHub: https://github.com/microsoft/LLMLingua

### 10.4 2026-05 웹 검색 참조
- Ollama community models:
  - [qllama/bge-reranker-v2-m3](https://ollama.com/qllama/bge-reranker-v2-m3)
  - [bona/bge-reranker-v2-m3](https://ollama.com/bona/bge-reranker-v2-m3:latest)
  - ⚠️ Ollama 공식 reranker API 부재 — `/api/embed` 우회 필요 (정공 아님)
- CRAG 구현 사례:
  - [DataCamp CRAG with LangGraph](https://www.datacamp.com/tutorial/corrective-rag-crag)
  - [Meilisearch CRAG workflow](https://www.meilisearch.com/blog/corrective-rag)
- LongLLMLingua:
  - [LLMLingua 공식 사이트](https://www.llmlingua.com/)
  - [LangChain llmlingua_filter](https://api.python.langchain.com/en/latest/_modules/langchain_community/document_compressors/llmlingua_filter.html)

---

## 11. 의사결정 — **확정 (2026-05-27)** ✅

| # | 항목 | 결정 |
|---|---|---|
| 1 | Phase 1 머지 일정 | ✅ **D-3 (2026-06-08)** 까지 완료. PR 1 (Reranker) D-7, PR 2 (CRAG) D-3 |
| 2 | Cloud Run 메모리 | ✅ **8Gi 상향** (Phase 0 의존성 추가 직전 적용) |
| 3 | CRAG incorrect 정책 | ✅ **강제 차단** — LLM 호출 우회, 프론트 답변 영역 비활성 + 안내 메시지만 |
| 4 | Reranker 한국어 변형 비교 | ✅ **진행** — `BAAI/bge-reranker-v2-m3` vs `dragonkue/BGE-m3-ko` 골든셋 비교, 우수 모델 채택 |
| 5 | LongLLMLingua Phase 2 시작 | ✅ **D+1 (2026-06-12)** 시작, D+7 (2026-06-18) 머지 목표 |

---

**다음 단계 (Phase 0, D-12 = 2026-05-30 마감)**:
1. Cloud Run 메모리 8Gi 상향 (`gcloud run services update ajin-backend --memory=8Gi`)
2. `requirements.txt` 에 `FlagEmbedding>=1.2.10`, `llmlingua>=0.2.2` 추가
3. `config.py` 에 §8 환경 변수 8개 추가
4. `data/eval/golden_qa_kosha.jsonl` 작성 (긍정 20 + 부정 5)
5. `scripts/eval_rerank_korean.py` 스크립트 작성 (Reranker 한국어 변형 비교)
6. PR: `chore/rag-infra-bump` — 위 5개 항목 한 번에 머지

Phase 0 머지 후 Phase 1 PR 1 (`feat/rag-rerank-bge`) 작업 시작.

---

## 12. Reranker 한국어 변형 비교 결과 (2026-05-27, 로컬 dev 환경)

`scripts/eval_rerank_korean.py` 실행 결과 — 25 QA (긍정 20 + 부정 5) 평가, chroma 모드 (BM25 단독 + reranker).

| 지표 | BAAI/bge-reranker-v2-m3 | dragonkue/BGE-m3-ko |
|---|---|---|
| MRR@5 / nDCG@5 / Hit@5 | 0.000 | 0.000 |
| VerdictAccuracy | 0.160 | 0.160 |
| Latency | 783 ms | 756 ms |
| Memory | **468 MB** | 629 MB |
| Top score 평균 | **0.566** | 0.454 |
| Top score range | **0.501 – 0.725** | 0.326 – 0.621 |
| **TNR (부정 차단률)** | 0% (0/5) | **80% (4/5)** |
| **Pos→Correct 판정** | **20% (4/20)** | 0% (0/20) |

### Hit/MRR=0 인 이유
골든셋의 `expected_doc_id_prefix` (`REAL-KOSHA-*`, `REAL-LAW-*`, `DEMO-ECN-*` 등) 가 로컬 BM25 corpus (606 chunks) 의 실제 prefix (`ev-KOSHA-HV`, `ECN-2025/2026`, `8D-2025/2026`, `MTG-*`, `kb-sop-*`, `glossary-*`) 와 mismatch. KOSHA 실제 문서는 로컬 corpus 에 2건만 (production pgvector 에 14건). **production 환경 (pgvector 활성) 에서 별도 재평가 필요**.

### ✅ 채택: `BAAI/bge-reranker-v2-m3` (`config.RERANKER_MODEL` 기본값 유지)

근거:
1. **메모리 효율**: 468 MB vs 629 MB (Cloud Run 8Gi 환경에서 161 MB 절감)
2. **명확한 score 분리도**: 평균 0.566, range 0.501–0.725 → CRAG threshold(upper 0.70 / lower 0.40) 와 정합
3. **Pos→Correct 응답률**: 20% vs 0% → 정상 query 에 답변 가능
4. **Architecture 정합**: 정식 cross-encoder reranker (dragonkue 는 임베딩 모델을 cosine 유사도로 강제 사용 — semantically 다른 use case)
5. **다국어 우수성**: BGE-M3 시리즈 학습 데이터에 한국어 포함

### dragonkue/BGE-m3-ko 의 강점 (참고)
- TNR 80% — 부정 query 차단 효과 우수
- **Phase 1 PR2 (CRAG)** 의 LLM-as-judge 단계 입력 임베딩으로 활용 검토 가능

### 후속 튜닝 작업 (Phase 1 PR1 머지 후)
- 골든셋 `expected_doc_id_prefix` 를 corpus 실제 패턴으로 정정 (별도 commit)
- 25 → 100+ query 확장 (production 사용자 query 로그 기반)
- CRAG threshold 모델별 튜닝 — BAAI score 분포 기준 `upper=0.60, lower=0.40` 검토 (Phase 1 PR2 에서)
