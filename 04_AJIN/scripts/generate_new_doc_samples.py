"""신규 문서 양식 생성 + corpus 적재 (Gemini 3.5 Flash)

생성 양식 (7종, AJIN 자동차 부품 제조 컨텍스트):
  1. FMEA — EMP 워터펌프 Process FMEA (품질관리팀)
  2. FMEA — B-Pillar 용접 Process FMEA (생산기술팀)
  3. Control Plan — EMP 워터펌프 (품질관리팀)
  4. Control Plan — CCH 냉각플레이트 (품질관리팀)
  5. Audit Report — IATF 16949 내부 감사 (품질관리팀)
  6. Inspection Report — 수입검사 (수입검사팀)
  7. Training Material — SPC 교육 (생산기술팀)

각 문서:
  - Gemini 3.5 Flash 호출 → markdown 생성
  - data/documents/<doc_type 폴더>/<doc_id>.md 저장
  - "---" 기준 chunk 분할 → metadata 부여
  - vectorstore/bm25_corpus.json 에 append (기존 546 chunks 보존)

사용:
  export GEMINI_API_KEY=<key>
  python3 scripts/generate_new_doc_samples.py

근거:
  - Gemini 3.5 Flash GA 2026-05-19 — thinking 모드 + 1M context.
  - chunk format = 기존 corpus 와 동일 (doc_id, content, metadata{doc_type, part_name, ...}).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "documents"
CORPUS_PATH = ROOT / "vectorstore" / "bm25_corpus.json"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY 환경 변수 미설정. .env 에서 load 후 재실행.", file=sys.stderr)
    sys.exit(1)

try:
    import google.generativeai as genai  # type: ignore
except ImportError:
    print("ERROR: google-generativeai 미설치. `pip install google-generativeai`.", file=sys.stderr)
    sys.exit(1)

genai.configure(api_key=GEMINI_API_KEY)
MODEL = genai.GenerativeModel("gemini-3.5-flash")


# ──────────────────────────────────────────────────────────────────────────
# 신규 양식 7종 정의 — AJIN 자동차 부품 제조 컨텍스트
# ──────────────────────────────────────────────────────────────────────────

COMMON_CONTEXT = """
회사: 아진산업 (자동차 부품 1차 협력사, 본사 경상북도, 직원 649명)
주요 고객: 현대자동차, 기아자동차
주력 제품: EMP 워터펌프(AJ-EMP-W100), CCH 냉각플레이트(AJ-CCH-P100), B-Pillar(SPFC980),
          OBC 케이스(AJ-OBC-C100), 시트 레일(AJ-SIT-R100)
인증: IATF 16949, ISO 14001, ISO 45001, AEO AAA
공정: 프레스 / 다이캐스팅 / CNC 가공 / 용접 / 조립 / 검사
"""

SAMPLES: list[dict] = [
    {
        "doc_id": "FMEA-2026-001",
        "doc_type": "FMEA",
        "part_name": "EMP 워터펌프",
        "title": "EMP 워터펌프 Process FMEA",
        "department": "품질관리팀",
        "customer": "현대차/기아",
        "created_date": "2026-05-25",
        "tags": "FMEA, 공정FMEA, EWP, 워터펌프, RPN, 위험우선순위, IATF, AIAG-VDA",
        "output_dir": "fmea",
        "prompt_kicker": (
            "Process FMEA (공정 고장모드 영향 분석) 보고서를 작성합니다. "
            "대상은 EMP 워터펌프 다이캐스팅 + CNC + 조립 공정. "
            "표준은 IATF 16949 / AIAG-VDA FMEA 매뉴얼."
        ),
    },
    {
        "doc_id": "FMEA-2026-002",
        "doc_type": "FMEA",
        "part_name": "B-Pillar",
        "title": "B-Pillar 용접 Process FMEA",
        "department": "생산기술팀",
        "customer": "현대차",
        "created_date": "2026-05-25",
        "tags": "FMEA, 공정FMEA, B-Pillar, 용접, MAG, RPN, SPFC980",
        "output_dir": "fmea",
        "prompt_kicker": (
            "Process FMEA 보고서를 작성합니다. 대상은 B-Pillar (SPFC980 핫스탬핑 보강재) "
            "MAG 용접 + 점용접 공정. 차체 안전 부품으로 측면 충돌 시 객실 보호 기능."
        ),
    },
    {
        "doc_id": "CP-2026-001",
        "doc_type": "Control Plan",
        "part_name": "EMP 워터펌프",
        "title": "EMP 워터펌프 Control Plan (양산)",
        "department": "품질관리팀",
        "customer": "현대차/기아",
        "created_date": "2026-05-25",
        "tags": "Control Plan, 관리계획서, EWP, 양산, IATF, SPC, 핵심특성, 특별특성",
        "output_dir": "control_plan",
        "prompt_kicker": (
            "Control Plan (관리계획서) 양산 단계 버전을 작성합니다. 대상: EMP 워터펌프. "
            "IATF 16949 요구사항 — Pre-launch 와 Production 단계 구분, 특별특성(SC/CC) 관리."
        ),
    },
    {
        "doc_id": "CP-2026-002",
        "doc_type": "Control Plan",
        "part_name": "CCH 냉각플레이트",
        "title": "CCH 냉각플레이트 Control Plan (Pre-launch)",
        "department": "품질관리팀",
        "customer": "현대차 EV",
        "created_date": "2026-05-25",
        "tags": "Control Plan, 관리계획서, CCH, 배터리, EV, Pre-launch, 누수시험",
        "output_dir": "control_plan",
        "prompt_kicker": (
            "Control Plan (관리계획서) Pre-launch 버전을 작성합니다. 대상: CCH 냉각플레이트 "
            "(전기차 배터리 모듈 냉각). 누수 시험 0.2 MPa 5분, 평탄도 ±0.3mm 중점."
        ),
    },
    {
        "doc_id": "AUDIT-2026-001",
        "doc_type": "Audit Report",
        "part_name": "전사",
        "title": "IATF 16949 내부 감사 보고서 (2026 1차)",
        "department": "품질관리팀",
        "customer": "내부",
        "created_date": "2026-04-20",
        "tags": "Audit, 내부감사, IATF, 16949, NCR, 부적합, 개선조치, 2026 Q1",
        "output_dir": "audit",
        "prompt_kicker": (
            "IATF 16949 내부 감사 보고서를 작성합니다. 2026년 1분기 감사. "
            "Process Approach 기반 — Customer Specific Requirements 준수, "
            "MSA/SPC/Control Plan 효과성 검증. NCR (부적합) 3건 발견."
        ),
    },
    {
        "doc_id": "INSP-2026-001",
        "doc_type": "Inspection Report",
        "part_name": "EMP 워터펌프 하우징 소재",
        "title": "수입검사 보고서 — AL6061-T6 (2026-05 LOT)",
        "department": "수입검사팀",
        "customer": "내부",
        "created_date": "2026-05-22",
        "tags": "수입검사, IQC, AL6061, T6, 화학성분, 인장강도, ICP, 합격",
        "output_dir": "inspection",
        "prompt_kicker": (
            "수입검사(IQC) 보고서를 작성합니다. 대상: EMP 워터펌프 하우징용 AL6061-T6 알루미늄 빌렛. "
            "공급업체 동주물산, LOT 2026-05-15, 5톤 입고. ICP-OES 화학성분 + 인장시험."
        ),
    },
    {
        "doc_id": "TRAIN-2026-001",
        "doc_type": "Training Material",
        "part_name": "전사",
        "title": "SPC 기본 교육자료 — 관리도와 공정능력",
        "department": "생산기술팀",
        "customer": "사내 교육",
        "created_date": "2026-05-25",
        "tags": "SPC, 교육, 관리도, Xbar-R, Cpk, Cp, 공정능력, Nelson, 사내교육",
        "output_dir": "training",
        "prompt_kicker": (
            "사내 교육 자료를 작성합니다. 주제: SPC (Statistical Process Control) 기본. "
            "대상: 생산직 신입~3년차. Xbar-R 관리도, Nelson Rule 8개, Cpk/Cp 해석, "
            "AJIN 의 실제 공정(프레스/용접) 사례 포함."
        ),
    },
]


def build_prompt(sample: dict) -> str:
    """양식별 Gemini prompt 빌드 — markdown 구조 + AJIN 컨텍스트."""
    return f"""{COMMON_CONTEXT}

작업: {sample["prompt_kicker"]}

작성 지침:
- 한국어, markdown 형식.
- 첫 줄에 `# <문서 제목>` 으로 시작.
- 두 번째 블록은 `| 항목 | 내용 |` 표 — 문서번호({sample["doc_id"]}), 작성일({sample["created_date"]}), 작성부서({sample["department"]}), 대상부품({sample["part_name"]}), 고객({sample["customer"]}) 포함.
- 각 섹션은 `---` 구분자로 분리. 최소 6개 섹션.
- 표(`| ... | ... |`)와 본문 텍스트 혼합. 실제 수치/공정 조건/허용공차 포함 (예: 두께 1.2±0.05mm, 인장강도 270MPa 이상).
- AJIN 실제 제품/공정/고객사 명확히 반영.
- 끝에 결재/검토자 표 1개.
- 분량: 2000-3500 자.

출력은 markdown 본문만. 메타 설명/머리말/꼬리말 없이 곧바로 `# ...` 으로 시작.
"""


def chunk_markdown(md_text: str, sample: dict, source_path: Path) -> list[dict]:
    """`---` 기준 chunk 분할 + metadata 부여."""
    sections = [s.strip() for s in md_text.split("\n---\n") if s.strip()]
    chunks = []
    for section in sections:
        if len(section) < 50:
            continue
        chunks.append({
            "doc_id": sample["doc_id"],
            "content": section,
            "metadata": {
                "source": str(source_path),
                "doc_id": sample["doc_id"],
                "doc_type": sample["doc_type"],
                "part_name": sample["part_name"],
                "customer": sample.get("customer", ""),
                "department": sample.get("department", ""),
                "created_date": sample.get("created_date", ""),
                "title": sample["title"],
                "tags": sample.get("tags", ""),
            },
        })
    return chunks


def generate_one(sample: dict) -> tuple[Path, list[dict]]:
    """단일 양식 생성 + 저장 + chunk 변환."""
    print(f"  ▸ {sample['doc_id']} ({sample['doc_type']}) — Gemini 호출 중...")
    prompt = build_prompt(sample)
    response = MODEL.generate_content(prompt)
    md_text = (getattr(response, "text", "") or "").strip()
    if not md_text:
        raise RuntimeError(f"{sample['doc_id']}: Gemini 빈 응답")
    if not md_text.startswith("#"):
        # 앞에 잡설이 붙은 경우 첫 # 부터 자르기
        idx = md_text.find("\n# ")
        if idx >= 0:
            md_text = md_text[idx + 1:].lstrip()

    out_dir = DATA_DIR / sample["output_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{sample['doc_id']}.md"
    out_path.write_text(md_text, encoding="utf-8")

    chunks = chunk_markdown(md_text, sample, out_path)
    print(f"    ✓ {len(md_text)} chars, {len(chunks)} chunks → {out_path.relative_to(ROOT)}")
    return out_path, chunks


def main() -> int:
    if not CORPUS_PATH.exists():
        print(f"ERROR: {CORPUS_PATH} 없음 — vectorstore baked corpus 필요.", file=sys.stderr)
        return 1

    with CORPUS_PATH.open("r", encoding="utf-8") as f:
        corpus = json.load(f)
    print(f"기존 corpus: {len(corpus)} chunks")

    all_new_chunks: list[dict] = []
    for sample in SAMPLES:
        try:
            _, chunks = generate_one(sample)
            all_new_chunks.extend(chunks)
        except Exception as e:
            print(f"    ✗ {sample['doc_id']} 실패: {e}", file=sys.stderr)

    if not all_new_chunks:
        print("ERROR: 생성된 chunk 가 0개.", file=sys.stderr)
        return 1

    # 중복 doc_id 가 이전 corpus 에 있으면 제거 후 append (idempotent 재실행 지원)
    new_doc_ids = {c["doc_id"] for c in all_new_chunks}
    corpus = [c for c in corpus if c.get("doc_id") not in new_doc_ids]
    corpus.extend(all_new_chunks)

    with CORPUS_PATH.open("w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, indent=2)

    print(f"\n신규 chunks: {len(all_new_chunks)}")
    print(f"전체 corpus: {len(corpus)} chunks (이전 +{len(all_new_chunks) - 0} 변화)")
    print(f"saved: {CORPUS_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
