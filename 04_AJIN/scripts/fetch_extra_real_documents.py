#!/usr/bin/env python3
"""KOSHA seriousAccident/regionalCase + 법령정보(law.go.kr) + 고용노동부(moel.go.kr) +
KATECH 자동차산업분석 등 정적 공개 PDF 추가 수집.

사용자 추가 승인(2026-05-26) 하에 Chrome MCP 확장 페어링이 불가한 환경에서
대체 경로로 정적 PDF 를 추가 다운로드 → pgvector 시드 추가.
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
    print("ERROR: pip install --user pypdf", file=sys.stderr)
    sys.exit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "real_documents" / "extra_sources"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSON = REPO_ROOT / "data" / "real_documents" / "extra_real_seed.json"

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"

# (도메인 라벨, full URL, slug, korean_title, doc_type_hint, doc_id_prefix)
SOURCES: list[tuple[str, str, str, str, str, str]] = [
    ("KOSHA-중대산업사고",
     "https://oshri.kosha.or.kr/kosha/data/seriousAccident.do?mode=download&articleNo=274084&attachNo=146749",
     "serious_accident_2004", "중대산업사고 사례집 (2004년 안전분야 기술자료)",
     "8d_report", "REAL-KOSHA-SA"),
    ("KOSHA-지역사례",
     "https://oshri.kosha.or.kr/kosha/data/regionalCase.do?mode=download&articleNo=434368&attachNo=244588",
     "regional_case_434368", "안전보건공단 지역사고 사례 (제2022-호 보고서)",
     "8d_report", "REAL-KOSHA-RC"),
    ("KOSHA-사고조사지침",
     "https://kosha.or.kr/extappKosha/kosha/guidance/fileDownload.do?sfhlhTchnlgyManualNo=Z-8-2023&fileOrdrNo=2",
     "incident_investigation_guide_2023", "사고조사의 실시 및 활용에 관한 지침 (KOSHA Z-8-2023)",
     "meeting_note", "REAL-KOSHA-IG"),
    ("KOSHA-재해조사연구",
     "https://www.kosha.or.kr/oshri/publication/researchReportSearch.do?mode=download&articleNo=419756&attachNo=237830",
     "disaster_investigation_research", "재해조사 보고서의 질적 제고를 위한 방안 연구",
     "ecn", "REAL-KOSHA-DR"),
    ("법령정보-안전사고조사양식",
     "https://www.law.go.kr/LSW/flDownload.do?flSeq=149440009",
     "safety_incident_form", "안전사고조사보고서 양식 (별지 제3호)",
     "ppap", "REAL-LAW-SF"),
    ("고용노동부-중대산업사고지침",
     "https://www.moel.go.kr/local/busanbukbu/common/downloadFile.do?file_seq=21171050392&bbs_seq=62784&bbs_id=LOCAL5",
     "moel_serious_accident_guide", "중대산업사고 조사지침 (고용노동부)",
     "meeting_note", "REAL-MOEL-SA"),
    ("KATECH-자동차산업분석",
     "https://www.katech.re.kr/download/b6725834-149a-4cc6-96d6-6a2f02912c14",
     "katech_auto_analysis_2024", "한국자동차연구원 산업분석 특별호 (2024.12 자동차 산업동향)",
     "ecn", "REAL-KATECH-IA"),
]


def fetch_pdf(url: str, out_path: Path) -> bool:
    """단일 PDF 다운로드. PDF 매직 헤더 검증."""
    if out_path.exists() and out_path.stat().st_size > 5000:
        return True
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if "kosha.or.kr" in url:
        headers["Referer"] = "https://oshri.kosha.or.kr/"
    elif "law.go.kr" in url:
        headers["Referer"] = "https://www.law.go.kr/"
    elif "moel.go.kr" in url:
        headers["Referer"] = "https://www.moel.go.kr/"
    elif "katech.re.kr" in url:
        headers["Referer"] = "https://www.katech.re.kr/"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = resp.read()
    except Exception as e:
        print(f"  ! fetch failed: {e}")
        return False
    if data[:5] != b"%PDF-":
        print(f"  ! not PDF (size={len(data)}, head={data[:20]!r})")
        return False
    out_path.write_bytes(data)
    return True


def extract_text(pdf_path: Path, max_pages: int = 30) -> str:
    try:
        reader = PdfReader(str(pdf_path))
    except Exception as e:
        print(f"  ! parse failed: {e}")
        return ""
    parts = []
    n = min(len(reader.pages), max_pages)
    for i in range(n):
        try:
            t = reader.pages[i].extract_text() or ""
        except Exception:
            t = ""
        parts.append(t)
    return "\n\n".join(parts).strip()


def main() -> int:
    print(f"=== 정적 사이트 추가 PDF 7건 다운로드 + 파싱 ===")
    entries: list[dict] = []
    success = 0
    fail = 0

    for i, (label, url, slug, title, dt, prefix) in enumerate(SOURCES, 1):
        out_path = OUT_DIR / f"{slug}.pdf"
        print(f"\n[{i}/7] {label} — {slug}")
        ok = fetch_pdf(url, out_path)
        if not ok:
            fail += 1
            continue
        sz = out_path.stat().st_size
        content = extract_text(out_path)
        if not content or len(content) < 200:
            print(f"  PDF {sz} bytes but text too short (len={len(content)})")
            fail += 1
            continue
        # doc_id 는 hash 기반 안정성 위해 slug 활용
        doc_id = f"{prefix}-{slug.upper().replace('_','-')[:60]}"
        entries.append({
            "doc_id": doc_id,
            "title": title,
            "doc_type": dt,
            "part_name": "",
            "content": content,
            "source_path": str(out_path.relative_to(REPO_ROOT)),
            "metadata": {
                "source_label": label,
                "source_type": "real",
                "source_url": url,
                "ingested_at": datetime.now(timezone.utc).isoformat(),
                "file_size_bytes": sz,
                "doc_type_hint": dt,
            },
        })
        success += 1
        print(f"  ✓ {sz:>9} bytes / {len(content):>6} chars / doc_id={doc_id}")
        time.sleep(0.5)

    print(f"\n=== 결과: 성공 {success} / 실패 {fail} / 총 {len(SOURCES)} ===")
    OUT_JSON.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ {OUT_JSON}")
    types = {}
    for e in entries:
        types[e["doc_type"]] = types.get(e["doc_type"], 0) + 1
    print(f"   doc_type 분포: {types}")
    return 0 if success >= 2 else 1


if __name__ == "__main__":
    sys.exit(main())
