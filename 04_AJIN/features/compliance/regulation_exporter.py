"""v2.6 Phase 3: 규제 항목을 DOCX/PDF 문서로 내보내기

크롤링된 규제 데이터를 마크다운으로 변환한 뒤,
기존 draft 모듈의 DOCX/PDF exporter를 활용하여 문서화한다.

v2.6: APQP/MSDS 전용 마크다운 포매터 추가 — 고유 필드 완전 지원
"""
from __future__ import annotations

import json
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────
# v2.6: APQP 전용 마크다운 포매터
# ─────────────────────────────────────────────

def _apqp_item_to_md(item: dict, idx: int) -> list[str]:
    """APQP 단계(Phase) 1건을 마크다운으로 변환한다."""
    lines: list[str] = []

    name_ko = item.get("name_ko", item.get("name", "N/A"))
    name_en = item.get("name", "")
    lines.append(f"### {idx}. {name_ko}")
    if name_en and name_en != name_ko:
        lines.append(f"*{name_en}*")
    lines.append("")

    if item.get("phase_id"):
        lines.append(f"- **ID**: {item['phase_id']}")
    if item.get("typical_duration"):
        lines.append(f"- **소요 기간**: {item['typical_duration']}")
    if item.get("responsible_dept"):
        depts = item["responsible_dept"]
        if isinstance(depts, list):
            depts = ", ".join(depts)
        lines.append(f"- **담당 부서**: {depts}")

    if item.get("description"):
        lines.append(f"\n{item['description']}")

    # 핵심 활동
    activities = item.get("key_activities") or []
    if activities:
        lines.append("\n**핵심 활동:**")
        for a in activities:
            lines.append(f"- {a}")

    # 산출물
    deliverables = item.get("deliverables_ko") or item.get("deliverables") or []
    if deliverables:
        lines.append("\n**산출물 (Deliverables):**")
        for d in deliverables:
            lines.append(f"- {d}")

    # 게이트 리뷰 기준
    gate = item.get("gate_review_criteria") or []
    if gate:
        lines.append("\n**게이트 리뷰 기준:**")
        for g in gate:
            lines.append(f"- {g}")

    # OEM 요구사항
    oem = item.get("oem_requirements") or {}
    if isinstance(oem, dict) and oem:
        lines.append("\n**OEM별 요구사항:**")
        for oem_name, req in oem.items():
            lines.append(f"- **{oem_name}**: {req}")

    lines.extend(["", "---", ""])
    return lines


# ─────────────────────────────────────────────
# v2.6: MSDS 전용 마크다운 포매터
# ─────────────────────────────────────────────

def _msds_item_to_md(item: dict, idx: int) -> list[str]:
    """MSDS 화학물질 레코드 1건을 마크다운으로 변환한다."""
    lines: list[str] = []

    name = item.get("substance_name_ko", item.get("substance_name", "N/A"))
    lines.append(f"### {idx}. {name}")
    lines.append("")

    if item.get("chemical_id"):
        lines.append(f"- **ID**: {item['chemical_id']}")
    if item.get("cas_number"):
        lines.append(f"- **CAS No.**: {item['cas_number']}")
    if item.get("ec_number"):
        lines.append(f"- **EC No.**: {item['ec_number']}")
    if item.get("molecular_formula"):
        lines.append(f"- **분자식**: {item['molecular_formula']}")
    if item.get("supplier"):
        lines.append(f"- **공급사**: {item['supplier']}")

    # MSDS 버전 상태
    ver = item.get("msds_version", "")
    latest = item.get("msds_latest_version", "")
    update = item.get("msds_update_needed", False)
    status_icon = "업데이트 필요" if update else "최신"
    if ver or latest:
        lines.append(f"- **MSDS 버전**: {ver} / 최신: {latest} ({status_icon})")

    # 경고 표시
    if item.get("signal_word"):
        lines.append(f"- **경고 표시**: {item['signal_word']}")

    # GHS 분류
    ghs = item.get("ghs_classification") or []
    if ghs:
        lines.append(f"\n**GHS 분류**: {', '.join(ghs[:5])}")

    # 위험 문구
    hazards = item.get("hazard_statements") or []
    if hazards:
        lines.append("\n**위험 문구 (H-code):**")
        for h in hazards[:8]:
            lines.append(f"- {h}")

    # 예방 조치
    precautions = item.get("precautionary_statements") or []
    if precautions:
        lines.append("\n**예방 조치 (P-code):**")
        for p in precautions[:5]:
            lines.append(f"- {p}")

    # CMR / SVHC
    cmr = item.get("cmr_classification", "")
    if cmr and cmr != "해당 없음":
        lines.append(f"\n**CMR 분류**: {cmr}")
    if item.get("svhc_candidate"):
        lines.append(f"**SVHC 후보물질**: 예 — {item.get('svhc_details', '')}")
    if item.get("pops_listed"):
        lines.append("**POPs 등재**: 예")

    # 노출 기준
    if item.get("oel_twa_ppm") is not None or item.get("oel_twa_mg_m3") is not None:
        twa_ppm = item.get("oel_twa_ppm", "—")
        twa_mg = item.get("oel_twa_mg_m3", "—")
        lines.append(f"\n**노출 기준 (TWA)**: {twa_ppm} ppm / {twa_mg} mg/m3")
    if item.get("oel_stel_ppm") is not None:
        lines.append(f"**노출 기준 (STEL)**: {item['oel_stel_ppm']} ppm")
    if item.get("oel_source"):
        lines.append(f"**기준 출처**: {item['oel_source']}")

    # REACH 상태
    if item.get("reach_status"):
        lines.append(f"**REACH 상태**: {item['reach_status']}")
    if item.get("k_reach_registered") is not None:
        kr = "등록 완료" if item["k_reach_registered"] else "미등록"
        lines.append(f"**K-REACH 등록**: {kr}")

    # 국내/국제 규제
    regs_kr = item.get("regulations_kr") or []
    if regs_kr:
        lines.append("\n**국내 규제:**")
        for r in regs_kr:
            lines.append(f"- {r}")

    regs_intl = item.get("regulations_intl") or []
    if regs_intl:
        lines.append("\n**국제 규제:**")
        for r in regs_intl:
            lines.append(f"- {r}")

    # 보관 요건
    if item.get("storage_requirements"):
        lines.append(f"\n**보관 요건**: {item['storage_requirements']}")

    lines.extend(["", "---", ""])
    return lines


# ─────────────────────────────────────────────
# v2.6: 적용 시설 상세 섹션 — plant_regulation_mapper 연동
# ─────────────────────────────────────────────

def _build_plant_detail_section(doc_type: str) -> list[str]:
    """규제 유형에 해당하는 적용 시설 상세를 마크다운 테이블로 생성한다."""
    try:
        from features.compliance.plant_regulation_mapper import get_applicable_plants
    except ImportError:
        return []

    plants = get_applicable_plants(doc_type)
    if not plants:
        return []

    lines: list[str] = ["", "## 적용 시설 상세", ""]

    # 카테고리별 그룹핑 (순서 유지)
    groups: dict[str, list[dict]] = {}
    for p in plants:
        cat = p.get("_category", "자사")
        groups.setdefault(cat, []).append(p)

    cat_order = ["자사", "국내 계열사", "해외법인"]
    for cat in cat_order:
        cat_plants = groups.get(cat, [])
        if not cat_plants:
            continue

        lines.append(f"### {cat} ({len(cat_plants)}개소)")
        lines.append("")
        lines.append("| 시설명 | 보유 인증 | 주요 생산품 |")
        lines.append("|--------|----------|------------|")

        for p in cat_plants:
            name = p.get("name", p.get("plant_id", ""))
            certs = p.get("certifications", [])
            certs_str = ", ".join(certs)[:80] if certs else "—"
            products = p.get("main_products", p.get("main_business", []))
            if isinstance(products, list):
                prod_str = ", ".join(str(x) for x in products[:3])
            else:
                prod_str = str(products)
            prod_str = prod_str[:80] or "—"
            lines.append(f"| {name} | {certs_str} | {prod_str} |")

        lines.append("")

    return lines


# ─────────────────────────────────────────────
# 메인 마크다운 변환기
# ─────────────────────────────────────────────

def regulations_to_markdown(
    items: list[dict],
    doc_type: str = "",
    display_name: str = "",
    crawled_at: str = "",
) -> str:
    """규제 항목 리스트를 마크다운 문서로 변환한다.

    v2.6: doc_type에 따라 APQP/MSDS 전용 포매터로 분기
    """
    lines = []

    # 헤더
    title = display_name or doc_type or "규제 보고서"
    date_str = crawled_at or datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append(f"# {title} 규제 보고서")
    lines.append("")
    lines.append(f"**발행**: 아진산업(주) 품질경영팀")
    lines.append(f"**기준일**: {date_str}")
    lines.append(f"**총 항목**: {len(items)}건")
    lines.append("")
    lines.append("---")
    lines.append("")

    # v2.6: 적용 시설 상세 (doc_type 기반 공장 매핑)
    if doc_type:
        lines.extend(_build_plant_detail_section(doc_type))

    # v2.6: APQP/MSDS는 전용 요약 생성
    is_apqp = doc_type == "APQP"
    is_msds = doc_type in ("MSDS", "MSDS/화학물질", "MSDS 유해물질")

    if is_apqp:
        lines.append("## APQP 5단계 프로세스 상세")
        lines.append("")
    elif is_msds:
        # MSDS 요약: 업데이트 필요 건수
        need_update = sum(1 for it in items if it.get("msds_update_needed"))
        svhc_count = sum(1 for it in items if it.get("svhc_candidate"))
        cmr_count = sum(1 for it in items if it.get("cmr_classification", "해당 없음") != "해당 없음")
        lines.append("## 유해물질 현황 요약")
        lines.append("")
        lines.append("| 항목 | 건수 |")
        lines.append("|------|------|")
        lines.append(f"| 전체 물질 | {len(items)} |")
        lines.append(f"| MSDS 업데이트 필요 | {need_update} |")
        lines.append(f"| SVHC 후보물질 | {svhc_count} |")
        lines.append(f"| CMR 분류 물질 | {cmr_count} |")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 물질별 상세")
        lines.append("")
    else:
        # 범용: 상태 요약 테이블
        status_counts: dict[str, int] = {}
        for item in items:
            s = _get_status(item)
            if s:
                status_counts[s] = status_counts.get(s, 0) + 1

        if status_counts:
            lines.append("## 준수 현황 요약")
            lines.append("")
            lines.append("| 상태 | 건수 |")
            lines.append("|------|------|")
            for status, count in sorted(status_counts.items()):
                lines.append(f"| {status} | {count} |")
            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append("## 규제 항목 상세")
        lines.append("")

    # 개별 항목
    for i, item in enumerate(items, 1):
        if is_apqp:
            lines.extend(_apqp_item_to_md(item, i))
        elif is_msds:
            lines.extend(_msds_item_to_md(item, i))
        else:
            # 범용 포매터 (기존 로직)
            lines.extend(_generic_item_to_md(item, i))

    # 하단
    lines.append("")
    lines.append("---")
    lines.append(f"*아진산업(주) | 경북 경산시 진량읍 공단8로 26길 40 | TEL 053-856-9100*")
    lines.append(f"*Confidential — 본 문서는 사내 업무용으로 작성되었습니다.*")

    return "\n".join(lines)


def _generic_item_to_md(item: dict, idx: int) -> list[str]:
    """범용 규제 항목 마크다운 변환 (ISO, EU, 국내법 등)."""
    lines: list[str] = []

    name = item.get("name", item.get("name_ko", item.get("title_ko", "N/A")))
    reg_id = _get_id(item)
    status = _get_status(item)

    lines.append(f"### {idx}. {name}")
    if reg_id:
        lines.append(f"**ID**: {reg_id}")
    if status:
        lines.append(f"**준수 상태**: {status}")

    _FIELDS = [
        ("category", "분류"), ("authority", "발행 기관"), ("issuing_org", "발행 기관"),
        ("effective_date", "시행일"), ("last_amended", "최종 개정일"),
        ("version", "버전"), ("ajin_relevance", "아진산업 관련성"),
        ("country", "국가"), ("regulation_basis", "법적 근거"),
    ]
    for key, label in _FIELDS:
        val = item.get(key)
        if val and val != "N/A":
            lines.append(f"- **{label}**: {val}")

    # v2.6: 개별 항목의 적용 시설 (affected_plants 배열)
    aff_plants = item.get("affected_plants") or []
    if aff_plants:
        lines.append(f"- **적용 시설**: {', '.join(aff_plants)}")

    # v2.6: 적용 공정 (affected_processes 배열)
    aff_procs = item.get("affected_processes") or []
    if aff_procs:
        proc_names = [p if isinstance(p, str) else p.get("name", str(p)) for p in aff_procs]
        lines.append(f"- **적용 공정**: {', '.join(proc_names)}")

    # 핵심 요구사항
    reqs = item.get("key_requirements") or item.get("key_requirements_ko") or item.get("key_articles") or []
    if reqs:
        lines.append("")
        lines.append("**핵심 요구사항:**")
        for r in reqs[:5]:
            if isinstance(r, dict):
                rtitle = r.get("requirement", r.get("title", r.get("title_ko", "")))
                lines.append(f"- {rtitle}")
            elif isinstance(r, str):
                lines.append(f"- {r}")

    # 조치 항목
    actions = item.get("action_items") or item.get("action_items_ko") or []
    if actions:
        lines.append("")
        lines.append("**필요 조치:**")
        for a in actions[:5]:
            text = str(a) if isinstance(a, str) else a.get("action", a.get("description", str(a)))
            lines.append(f"- {text}")

    lines.extend(["", "---", ""])
    return lines


# ─────────────────────────────────────────────
# DOCX / PDF 내보내기
# ─────────────────────────────────────────────

def export_regulations_docx(
    items: list[dict],
    doc_type: str = "",
    display_name: str = "",
    crawled_at: str = "",
) -> bytes | None:
    """규제 항목을 DOCX 바이트로 변환한다."""
    try:
        import tempfile
        from features.draft.docx_exporter import DocxExporter

        md = regulations_to_markdown(items, doc_type, display_name, crawled_at)
        exporter = DocxExporter()

        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        title = f"{display_name or doc_type} 규제 보고서"
        exporter.export(markdown_text=md, output_path=tmp_path, doc_title=title, doc_type="compliance")

        data = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        return data
    except Exception:
        return None


def export_regulations_pdf(
    items: list[dict],
    doc_type: str = "",
    display_name: str = "",
    crawled_at: str = "",
) -> bytes | None:
    """규제 항목을 PDF 바이트로 변환한다."""
    try:
        from features.draft.pdf_exporter import PdfExporter

        md = regulations_to_markdown(items, doc_type, display_name, crawled_at)
        exporter = PdfExporter()
        title = f"{display_name or doc_type} 규제 보고서"
        return exporter.export_bytes(markdown_text=md, doc_title=title)
    except Exception:
        return None


# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────

def _get_id(item: dict) -> str:
    for k in ["law_id", "standard_id", "reg_id", "regulation_id", "chemical_id", "phase_id"]:
        if k in item and item[k]:
            return str(item[k])
    return ""


def _get_status(item: dict) -> str:
    for k in ["compliance_status", "ajin_compliance_status", "ajin_readiness", "status"]:
        if k in item and item[k]:
            return str(item[k])
    return ""
