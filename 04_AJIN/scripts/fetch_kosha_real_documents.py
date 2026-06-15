#!/usr/bin/env python3
"""KOSHA OSHRI 공개 PDF 14건 다운로드 + 본문 파싱 + seed_documents 호환 JSON 생성.

사용자 명시 승인(2026-05-26) 하에 한국산업안전보건공단 산업안전보건연구원 게시판의
공개 정책연구·사례집 PDF 를 수집하여 pgvector 시드용 corpus 로 변환한다.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from pypdf import PdfReader
except ImportError:
    print("ERROR: pypdf 모듈이 필요. pip install --user pypdf", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "real_documents" / "kosha_oshri"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = REPO_ROOT / "data" / "real_documents" / "kosha_real_seed.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
REFERER = "https://oshri.kosha.or.kr/"
BASE = "https://oshri.kosha.or.kr"

# (articleNo, attachNo, board_path, slug, korean_title, doc_type_hint)
DOWNLOADS: list[tuple[int, int, str, str, str, str]] = [
    (274481, 147235, "kosha/data/disasterCasebook_C.do",
     "occupational_disease_casebook",
     "직업병 사례집 (자동차·유리·제조 노동자 사례 포함)", "8d_report"),
    (451304, 256947, "kosha/data/disasterCasebook_C.do",
     "2023_epidemiology_report",
     "2023년도 산업안전보건연구원 역학조사 결과보고서", "8d_report"),
    (408401, 229719, "oshri/researchField/researchdata.do",
     "manufacturing_safety_culture_v1",
     "제조업 안전문화 정책연구 (정책연구분야 vol.1)", "ecn"),
    (408401, 229720, "oshri/researchField/researchdata.do",
     "manufacturing_safety_culture_v2",
     "제조업 안전문화 정책연구 (정책연구분야 vol.2)", "ecn"),
    (416800, 235063, "_custom/kosha/_common/board/index/429.do",
     "public_research_disclosure",
     "산업안전보건연구원 공개 정책연구 자료", "meeting_note"),
    (63060, 259793, "oshri/publication/researchReportSearch.do",
     "equipment_risk_assessment",
     "산업장비·화학물질 설계/제조 단계 위험성평가 연구", "8d_report"),
    (338877, 185864, "kosha/data/activity_A.do",
     "singapore_near_miss_guide",
     "싱가포르 아차사고(Near miss) 보고 지침 최종본", "meeting_note"),
    (428033, 242549, "kosha/business/safetyManagementInstitutionData.do",
     "safety_mgmt_institution",
     "안전관리기관 운영 데이터 (제조업 적용)", "ppap"),
    (401814, 225315, "_custom/kosha/_common/board/index/406.do",
     "kosha_midterm_plan",
     "한국산업안전보건공단 중장기 경영목표(2018-2022)", "meeting_note"),
    (427870, 242335, "oshri/publication/researchReportSearch.do",
     "OSH_law_violation",
     "산업안전보건법 위반 범죄 법 적용 문제점 및 개선방안", "ecn"),
    (454371, 260733, "oshri/publication/researchReportSearch.do",
     "tower_crane_license",
     "타워크레인 설치·해체 기능사 자격제도 운영·발전 방안", "ppap"),
    (454369, 260678, "oshri/publication/researchReportSearch.do",
     "hazardous_work_restriction",
     "유해·위험작업 취업 제한 규칙 개정방안", "ecn"),
    (454367, 260674, "oshri/publication/researchReportSearch.do",
     "contract_approval_work",
     "도급승인 대상 작업 범위 및 내용의 합리성 검토", "meeting_note"),
    (454366, 260672, "oshri/publication/researchReportSearch.do",
     "chemical_facility_safety",
     "장기간 사용 화학설비의 안전성 확보 방안 연구", "8d_report"),
]


def fetch_pdf(article_no: int, attach_no: int, board_path: str, slug: str) -> Path | None:
    """단일 PDF 다운로드. 성공 시 저장 경로 반환, 실패 시 None."""
    out_path = OUT_DIR / f"{slug}_{article_no}.pdf"
    if out_path.exists() and out_path.stat().st_size > 5000:
        return out_path  # 이미 받은 파일 skip

    url = f"{BASE}/{board_path}?mode=download&articleNo={article_no}&attachNo={attach_no}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": UA, "Referer": REFERER, "Accept": "*/*"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        out_path.write_bytes(data)
        # PDF 매직 넘버 검증
        if data[:5] != b"%PDF-":
            print(f"  ! {slug:35s} downloaded but not PDF (size={len(data)})")
            out_path.unlink(missing_ok=True)
            return None
        return out_path
    except Exception as e:
        print(f"  ! {slug:35s} fetch failed: {e}")
        return None


def extract_text(pdf_path: Path, max_pages: int = 30) -> str:
    """pypdf 로 본문 추출. 첫 max_pages 페이지까지 (큰 보고서 trim)."""
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"  ! parse failed for {pdf_path.name}: {e}")
        return ""
    parts: list[str] = []
    pages = reader.pages
    n = min(len(pages), max_pages)
    for i in range(n):
        try:
            t = pages[i].extract_text() or ""
        except Exception:
            t = ""
        parts.append(t)
    return "\n\n".join(parts).strip()


def build_seed_entry(
    article_no: int,
    attach_no: int,
    board_path: str,
    slug: str,
    title: str,
    doc_type: str,
    pdf_path: Path,
    content: str,
) -> dict:
    """seed_documents.json 호환 entry."""
    url = f"{BASE}/{board_path}?mode=download&articleNo={article_no}&attachNo={attach_no}"
    return {
        "doc_id": f"REAL-KOSHA-{article_no}-{attach_no}",
        "title": title,
        "doc_type": doc_type,
        "part_name": "",
        "content": content,
        "source_path": str(pdf_path.relative_to(REPO_ROOT)),
        "metadata": {
            "source_org": "한국산업안전보건공단 산업안전보건연구원 (KOSHA OSHRI)",
            "source_type": "real",
            "source_url": url,
            "article_no": article_no,
            "attach_no": attach_no,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
            "file_size_bytes": pdf_path.stat().st_size,
            "doc_type_hint": doc_type,
        },
    }


def main() -> int:
    print(f"=== KOSHA OSHRI 실제 PDF 14건 다운로드 + 파싱 ===")
    print(f"출력 디렉토리: {OUT_DIR}")
    print()

    entries: list[dict] = []
    success = 0
    fail = 0

    for i, (ano, attno, path, slug, title, dt) in enumerate(DOWNLOADS, 1):
        print(f"[{i:2d}/14] {slug:35s} ano={ano} ", end="", flush=True)
        pdf_path = fetch_pdf(ano, attno, path, slug)
        if not pdf_path:
            fail += 1
            print("FAIL")
            continue
        sz = pdf_path.stat().st_size
        content = extract_text(pdf_path)
        if not content or len(content) < 200:
            print(f"  PDF ok ({sz} bytes) but text empty (len={len(content)})")
            fail += 1
            continue
        entry = build_seed_entry(ano, attno, path, slug, title, dt, pdf_path, content)
        entries.append(entry)
        success += 1
        print(f"  PDF {sz:>9} bytes  text {len(content):>6} chars  type={dt}")
        time.sleep(0.5)  # rate-limit 친화

    print()
    print(f"=== 결과: 성공 {success} / 실패 {fail} / 총 {len(DOWNLOADS)} ===")

    OUT_JSON.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n=== seed JSON 저장: {OUT_JSON} ===")
    print(f"  doc_type 분포: ", end="")
    types: dict[str, int] = {}
    for e in entries:
        types[e["doc_type"]] = types.get(e["doc_type"], 0) + 1
    print(types)

    return 0 if success >= 4 else 1


if __name__ == "__main__":
    sys.exit(main())
