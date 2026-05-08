"""Phase 2: 문서 인덱싱 파이프라인 (확장판)

문서(33) + 지식베이스(12) + 용어집(85) + 크롤링 규제(9종) →
한국어 최적화 청크 분할 → Ollama BGE-M3 임베딩 → ChromaDB 저장 + BM25 코퍼스
"""

from __future__ import annotations

import json
import pickle
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma

from config import (
    DOCUMENTS_DIR, METADATA_PATH, VECTORSTORE_DIR,
    KNOWLEDGE_BASE_DIR, GLOSSARY_DIR, CRAWLED_DIR,
    CHUNK_SIZE, CHUNK_OVERLAP,
)
from core.embedding_client import get_embeddings


# ──────────────────────────────────────────────────────────────
# 1. 문서 로더 (data/documents/)
# ──────────────────────────────────────────────────────────────

def load_documents(doc_dir: Path, metadata_path: Path) -> list[Document]:
    """마크다운 문서와 메타데이터를 함께 로드한다."""
    meta_db: dict = {}
    if metadata_path.exists():
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta_db = {doc["id"]: doc for doc in json.load(f)["documents"]}

    documents: list[Document] = []
    for md_file in sorted(doc_dir.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        doc_id = md_file.stem
        meta = meta_db.get(doc_id, {})

        documents.append(Document(
            page_content=content,
            metadata={
                "source": str(md_file),
                "doc_id": doc_id,
                "doc_type": meta.get("doc_type", "Unknown"),
                "part_name": meta.get("part_name", ""),
                "customer": meta.get("customer", ""),
                "department": meta.get("department", ""),
                "created_date": meta.get("created_date", ""),
                "title": meta.get("title", ""),
                "tags": ", ".join(meta.get("tags", [])),
            }
        ))

    return documents


# ──────────────────────────────────────────────────────────────
# 2. 지식베이스 로더 (data/knowledge_base/)
# ──────────────────────────────────────────────────────────────

_KB_TYPE_MAP = {
    "sop": "SOP",
    "department_guides": "Department Guide",
    "collaboration": "Collaboration Guide",
}


def load_knowledge_base(kb_dir: Path) -> list[Document]:
    """SOP, 부서 가이드, 협업 가이드 마크다운을 로드한다."""
    documents: list[Document] = []
    for md_file in sorted(kb_dir.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        # 상위 폴더명으로 문서 유형 결정
        parent = md_file.parent.name
        doc_type = _KB_TYPE_MAP.get(parent, "Knowledge Base")
        doc_id = f"kb-{parent}-{md_file.stem}"

        # 첫 번째 줄에서 제목 추출 (# 제목)
        title = ""
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break

        documents.append(Document(
            page_content=content,
            metadata={
                "source": str(md_file),
                "doc_id": doc_id,
                "doc_type": doc_type,
                "part_name": "",
                "customer": "",
                "department": _guess_department(md_file.stem),
                "created_date": "",
                "title": title or md_file.stem.replace("_", " ").title(),
                "tags": f"{doc_type}, {parent}",
            }
        ))

    return documents


def _guess_department(stem: str) -> str:
    """파일명에서 부서를 추정한다."""
    mapping = {
        "quality": "품질관리팀",
        "production": "생산기술팀",
        "sales": "영업팀",
        "rnd": "연구소",
        "press": "프레스팀",
        "welding": "용접팀",
    }
    for key, dept in mapping.items():
        if key in stem:
            return dept
    return ""


# ──────────────────────────────────────────────────────────────
# 3. 용어집 로더 (data/knowledge_base/glossary/)
# ──────────────────────────────────────────────────────────────

def load_glossary(glossary_dir: Path) -> list[Document]:
    """JSON 용어집을 검색 가능한 Document로 변환한다."""
    documents: list[Document] = []

    for json_file in sorted(glossary_dir.glob("*.json")):
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        category = data.get("category", json_file.stem)

        for term_data in data.get("terms", []):
            term = term_data.get("term", "")
            full_name = term_data.get("full_name", "")
            korean_name = term_data.get("korean_name", "")
            definition = term_data.get("definition", "")
            ajin_context = term_data.get("ajin_context", "")
            example = term_data.get("example", "")
            related = ", ".join(term_data.get("related_terms", []))

            # 용어를 자연어 텍스트로 변환
            text_parts = [
                f"[용어] {term}",
            ]
            if full_name:
                text_parts.append(f"정식명칭: {full_name}")
            if korean_name:
                text_parts.append(f"한국어: {korean_name}")
            text_parts.append(f"분류: {category}")
            if definition:
                text_parts.append(f"정의: {definition}")
            if ajin_context:
                text_parts.append(f"아진산업 적용: {ajin_context}")
            if example:
                text_parts.append(f"예시: {example}")
            if related:
                text_parts.append(f"관련 용어: {related}")

            doc_id = f"glossary-{term.lower().replace(' ', '-')}"

            documents.append(Document(
                page_content="\n".join(text_parts),
                metadata={
                    "source": str(json_file),
                    "doc_id": doc_id,
                    "doc_type": "Glossary",
                    "part_name": "",
                    "customer": "",
                    "department": ", ".join(term_data.get("departments_involved", [])),
                    "created_date": "",
                    "title": f"{term} ({korean_name})" if korean_name else term,
                    "tags": ", ".join(term_data.get("tags", [])),
                }
            ))

    return documents


# ──────────────────────────────────────────────────────────────
# 4. 크롤링 규제 데이터 로더 (data/crawled/)
# ──────────────────────────────────────────────────────────────

def load_crawled_data(crawled_dir: Path) -> list[Document]:
    """크롤링된 규제/법규 JSON을 검색 가능한 Document로 변환한다."""
    documents: list[Document] = []

    _loaders = {
        "iso_standards.json": _load_iso,
        "apqp_process.json": _load_apqp,
        "msds_data.json": _load_msds,
        "domestic_laws.json": _load_domestic_laws,
        "eu_regulations.json": _load_eu_regulations,
        "oem_quality.json": _load_oem_quality,
        "carbon_esg.json": _load_carbon_esg,
        "ev_battery.json": _load_ev_battery,
        "global_trade.json": _load_global_trade,
    }

    for filename, loader_fn in _loaders.items():
        json_path = crawled_dir / filename
        if not json_path.exists():
            continue
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        docs = loader_fn(data, str(json_path))
        documents.extend(docs)

    return documents


def _load_iso(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for s in data.get("standards", []):
        text = (
            f"[ISO 국제규격] {s.get('title', '')} ({s.get('title_ko', '')})\n"
            f"표준ID: {s.get('standard_id', '')}\n"
            f"상태: {s.get('status', '')} | 카테고리: {s.get('category', '')}\n"
            f"범위: {s.get('scope', '')}\n"
            f"아진산업 관련성: {s.get('ajin_relevance', '')}\n"
            f"최신 개정: {s.get('latest_amendment', '')}\n"
            f"변경 요약: {s.get('changes_summary', '')}\n"
            f"전환 기한: {s.get('transition_deadline', '')}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"iso-{s.get('standard_id', '')}",
                "doc_type": "Compliance/ISO",
                "part_name": "",
                "customer": "",
                "department": "품질관리팀",
                "created_date": s.get("crawled_at", ""),
                "title": s.get("title_ko", s.get("title", "")),
                "tags": "ISO, 국제규격, compliance",
            }
        ))
    return docs


def _load_apqp(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for p in data.get("phases", []):
        deliverables = "\n".join(f"  - {d}" for d in p.get("deliverables_ko", []))
        oem_reqs = ""
        for oem_name, reqs in p.get("oem_specific_requirements", {}).items():
            oem_reqs += f"\n[{oem_name}] " + "; ".join(reqs)

        text = (
            f"[APQP Phase] {p.get('phase_id', '')} - {p.get('name_ko', '')}\n"
            f"설명: {p.get('description_ko', '')}\n"
            f"기간: {p.get('duration_weeks', '')}주 | 담당: {p.get('responsible_dept', '')}\n"
            f"산출물:\n{deliverables}\n"
            f"OEM별 요구사항:{oem_reqs}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"apqp-{p.get('phase_id', '')}",
                "doc_type": "Compliance/APQP",
                "part_name": "",
                "customer": "",
                "department": "연구소, 품질관리팀",
                "created_date": "",
                "title": f"APQP {p.get('name_ko', '')}",
                "tags": "APQP, 연구개발, 프로세스",
            }
        ))

    for u in data.get("updates", []):
        text = (
            f"[APQP 업데이트] {u.get('title', '')}\n"
            f"출처: {u.get('source', '')} | 심각도: {u.get('severity', '')}\n"
            f"시행일: {u.get('effective_date', '')}\n"
            f"변경 내용: {u.get('changes_ko', '')}\n"
            f"요구 조치: {'; '.join(u.get('required_actions', []))}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"apqp-update-{u.get('update_id', '')}",
                "doc_type": "Compliance/APQP",
                "part_name": "",
                "customer": "",
                "department": "연구소",
                "created_date": u.get("effective_date", ""),
                "title": u.get("title", ""),
                "tags": "APQP, 업데이트",
            }
        ))
    return docs


def _load_msds(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for r in data.get("records", []):
        hazard_stmts = "; ".join(r.get("hazard_statements_ko", []))
        precaution = "; ".join(r.get("precautionary_statements_ko", []))
        text = (
            f"[MSDS 유해물질] {r.get('substance_name_ko', '')} ({r.get('substance_name', '')})\n"
            f"화학물질ID: {r.get('chemical_id', '')} | CAS: {r.get('cas_number', '')}\n"
            f"GHS 분류: {', '.join(r.get('ghs_classification', []))}\n"
            f"위험 문구: {hazard_stmts}\n"
            f"예방 조치: {precaution}\n"
            f"사용 공정: {', '.join(r.get('used_in_processes', []))}\n"
            f"노출기준(TWA): {r.get('oel_twa_mg_m3', '')} mg/m³\n"
            f"규정: {', '.join(r.get('regulations_kr', []))}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"msds-{r.get('chemical_id', '')}",
                "doc_type": "Compliance/MSDS",
                "part_name": "",
                "customer": "",
                "department": "환경안전팀",
                "created_date": r.get("crawled_at", ""),
                "title": r.get("substance_name_ko", ""),
                "tags": "MSDS, 유해물질, 화학물질",
            }
        ))

    for s in data.get("svhc_updates", []):
        text = (
            f"[SVHC 고위험물질] {s.get('substance_name', '')}\n"
            f"CAS: {s.get('cas_number', '')} | EC: {s.get('ec_number', '')}\n"
            f"등재 사유: {s.get('reason_for_inclusion', '')}\n"
            f"일몰일자: {s.get('sunset_date', '')}\n"
            f"영향 화학물질: {', '.join(s.get('affected_chemicals', []))}\n"
            f"필요 조치: {'; '.join(s.get('required_actions', []))}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"svhc-{s.get('cas_number', '')}",
                "doc_type": "Compliance/MSDS",
                "part_name": "",
                "customer": "",
                "department": "환경안전팀",
                "created_date": "",
                "title": f"SVHC {s.get('substance_name', '')}",
                "tags": "SVHC, REACH, 유해물질",
            }
        ))
    return docs


def _load_domestic_laws(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for law in data.get("laws", []):
        articles_text = ""
        for art in law.get("key_articles", [])[:5]:
            articles_text += (
                f"\n  제{art.get('article', '')}조 {art.get('title', '')}: "
                f"{art.get('content', '')[:200]}"
            )
        text = (
            f"[국내법규] {law.get('name', '')}\n"
            f"법규ID: {law.get('law_id', '')} | 분류: {law.get('category', '')}\n"
            f"소관부처: {law.get('authority', '')}\n"
            f"최근개정: {law.get('last_amended', '')}\n"
            f"개정요약: {law.get('amendment_summary', '')}\n"
            f"준수상태: {law.get('compliance_status', '')}\n"
            f"적용공장: {', '.join(law.get('affected_plants', []))}\n"
            f"적용공정: {', '.join(law.get('affected_processes', []))}\n"
            f"주요조항:{articles_text}\n"
            f"벌칙: {law.get('penalties', '')[:200]}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"law-{law.get('law_id', '')}",
                "doc_type": "Compliance/DomesticLaw",
                "part_name": "",
                "customer": "",
                "department": "환경안전팀, 품질관리팀",
                "created_date": law.get("crawled_at", ""),
                "title": law.get("name", ""),
                "tags": f"국내법규, {law.get('category', '')}",
            }
        ))
    return docs


def _load_eu_regulations(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for r in data.get("regulations", []):
        reqs_text = ""
        for req in r.get("key_requirements", [])[:5]:
            reqs_text += f"\n  - {req.get('requirement', '')}: {req.get('detail', '')[:150]}"
        deadlines_text = ""
        for dl in r.get("transition_deadlines", []):
            deadlines_text += f"\n  - {dl.get('date', '')}: {dl.get('description', '')}"
        text = (
            f"[EU 규제] {r.get('name', '')} ({r.get('name_ko', '')})\n"
            f"규제ID: {r.get('reg_id', '')} | 분류: {r.get('category', '')}\n"
            f"시행일: {r.get('effective_date', '')}\n"
            f"준수상태: {r.get('compliance_status', '')}\n"
            f"아진 관련: {r.get('ajin_relevance', '')}\n"
            f"주요 요구사항:{reqs_text}\n"
            f"전환 일정:{deadlines_text}\n"
            f"영향 화학물질: {', '.join(r.get('affected_chemicals', []))}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"eu-{r.get('reg_id', '')}",
                "doc_type": "Compliance/EU",
                "part_name": "",
                "customer": "",
                "department": "품질관리팀, 환경안전팀",
                "created_date": r.get("crawled_at", ""),
                "title": r.get("name_ko", r.get("name", "")),
                "tags": f"EU, {r.get('category', '')}, compliance",
            }
        ))
    return docs


def _load_oem_quality(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for s in data.get("standards", []):
        reqs_text = ""
        for req in s.get("key_requirements", [])[:5]:
            title_key = "title_ko" if "title_ko" in req else "title"
            desc_key = "description_ko" if "description_ko" in req else "description"
            reqs_text += f"\n  - {req.get(title_key, '')}: {req.get(desc_key, '')[:150]}"
        text = (
            f"[OEM 품질기준] {s.get('name', '')} ({s.get('name_ko', '')})\n"
            f"기준ID: {s.get('standard_id', '')} | OEM: {s.get('issuing_org', s.get('oem', ''))}\n"
            f"카테고리: {s.get('category', '')} | 버전: {s.get('version', '')}\n"
            f"아진 관련: {s.get('ajin_relevance', '')}\n"
            f"주요 요구사항:{reqs_text}\n"
            f"변경요약: {s.get('changes_summary_ko', s.get('changes_summary', ''))}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"oem-{s.get('standard_id', '')}",
                "doc_type": "Compliance/OEM",
                "part_name": "",
                "customer": s.get("issuing_org", s.get("oem", "")),
                "department": "품질관리팀",
                "created_date": s.get("crawled_at", ""),
                "title": s.get("name_ko", s.get("name", "")),
                "tags": f"OEM, {s.get('category', '')}, 품질기준",
            }
        ))
    return docs


def _load_carbon_esg(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for r in data.get("regulations", []):
        reqs_text = ""
        reqs_key = "key_requirements_ko" if "key_requirements_ko" in r else "key_requirements"
        for req in r.get(reqs_key, [])[:5]:
            if isinstance(req, dict):
                reqs_text += f"\n  - {req.get('requirement', '')}: {req.get('detail', '')[:150]}"
            else:
                reqs_text += f"\n  - {req}"
        text = (
            f"[탄소/ESG] {r.get('name', '')} ({r.get('name_ko', '')})\n"
            f"규제ID: {r.get('regulation_id', '')} | 분류: {r.get('category', '')}\n"
            f"발행기관: {r.get('issuing_org', r.get('authority', ''))}\n"
            f"시행일: {r.get('effective_date', '')}\n"
            f"아진 준비도: {r.get('ajin_readiness', '')}\n"
            f"아진 관련: {r.get('ajin_relevance', '')}\n"
            f"주요 요구사항:{reqs_text}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"esg-{r.get('regulation_id', '')}",
                "doc_type": "Compliance/ESG",
                "part_name": "",
                "customer": "",
                "department": "경영기획팀, 환경안전팀",
                "created_date": r.get("crawled_at", ""),
                "title": r.get("name_ko", r.get("name", "")),
                "tags": f"ESG, 탄소, {r.get('category', '')}",
            }
        ))
    return docs


def _load_ev_battery(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for s in data.get("standards", []):
        tests_text = ""
        for t in s.get("test_requirements", [])[:5]:
            name_key = "test_name_ko" if "test_name_ko" in t else "test_name"
            criteria_key = "pass_criteria_ko" if "pass_criteria_ko" in t else "pass_criteria"
            tests_text += f"\n  - {t.get(name_key, '')}: {t.get(criteria_key, '')[:120]}"
        text = (
            f"[EV 배터리 안전] {s.get('name', '')} ({s.get('name_ko', '')})\n"
            f"규격ID: {s.get('standard_id', '')} | 분류: {s.get('category', '')}\n"
            f"발행기관: {s.get('issuing_org', s.get('authority', ''))}\n"
            f"아진 준수: {s.get('ajin_compliance_status', '')}\n"
            f"전환기한: {s.get('transition_deadline', '')}\n"
            f"아진 관련: {s.get('ajin_relevance', '')}\n"
            f"시험 요구사항:{tests_text}\n"
            f"조치사항: {'; '.join(s.get('action_items_ko', []))}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"ev-{s.get('standard_id', '')}",
                "doc_type": "Compliance/EV Battery",
                "part_name": "",
                "customer": "",
                "department": "연구소, 품질관리팀",
                "created_date": s.get("crawled_at", ""),
                "title": s.get("name_ko", s.get("name", "")),
                "tags": f"EV, 배터리, {s.get('category', '')}",
            }
        ))
    return docs


def _load_global_trade(data: dict, source: str) -> list[Document]:
    docs: list[Document] = []
    for r in data.get("regulations", []):
        reqs_text = ""
        reqs_key = "key_requirements_ko" if "key_requirements_ko" in r else "key_requirements"
        for req in r.get(reqs_key, [])[:5]:
            if isinstance(req, dict):
                reqs_text += f"\n  - {req.get('requirement', '')}: {req.get('detail', '')[:150]}"
            else:
                reqs_text += f"\n  - {req}"
        text = (
            f"[글로벌 무역규제] {r.get('name', '')} ({r.get('name_ko', '')})\n"
            f"규제ID: {r.get('regulation_id', '')} | 국가: {r.get('country', '')}\n"
            f"분류: {r.get('category', '')} | 발행기관: {r.get('issuing_org', '')}\n"
            f"시행일: {r.get('effective_date', '')}\n"
            f"준수상태: {r.get('ajin_compliance_status', '')}\n"
            f"아진 관련: {r.get('ajin_relevance', '')}\n"
            f"주요 요구사항:{reqs_text}\n"
            f"조치사항: {'; '.join(r.get('action_items_ko', []))}"
        )
        docs.append(Document(
            page_content=text,
            metadata={
                "source": source,
                "doc_id": f"trade-{r.get('regulation_id', '')}",
                "doc_type": "Compliance/GlobalTrade",
                "part_name": "",
                "customer": "",
                "department": "경영기획팀, 영업팀",
                "created_date": r.get("crawled_at", ""),
                "title": r.get("name_ko", r.get("name", "")),
                "tags": f"무역, {r.get('country', '')}, {r.get('category', '')}",
            }
        ))
    return docs


# ──────────────────────────────────────────────────────────────
# 텍스트 분할기
# ──────────────────────────────────────────────────────────────

def create_splitter() -> RecursiveCharacterTextSplitter:
    """한국어 문서에 최적화된 텍스트 분할기를 생성한다."""
    return RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=[
            "\n## ",    # 마크다운 H2
            "\n### ",   # 마크다운 H3
            "\n\n",     # 빈 줄
            "\n",       # 줄바꿈
            "다. ",     # 한국어 종결
            "요. ",
            "음. ",
            ". ",       # 일반 마침표
            " ",
        ],
        length_function=len,
        is_separator_regex=False,
    )


# ──────────────────────────────────────────────────────────────
# 벡터스토어 구축
# ──────────────────────────────────────────────────────────────

def build_vectorstore(
    documents: list[Document],
    batch_size: int = 50,
) -> Chroma:
    """문서를 임베딩하여 ChromaDB에 저장한다.

    대량 문서를 배치로 나누어 OOM을 방지한다.
    """
    splitter = create_splitter()
    chunks = splitter.split_documents(documents)

    print(f"  원본 문서 수: {len(documents)}")
    print(f"  청크 분할 후: {len(chunks)}")

    embeddings = get_embeddings()
    persist_dir = str(VECTORSTORE_DIR / "documents")

    # 기존 DB 삭제 후 새로 생성 (클린 빌드)
    import shutil
    persist_path = Path(persist_dir)
    if persist_path.exists():
        shutil.rmtree(persist_path)
    # chroma.sqlite3도 삭제
    sqlite_path = VECTORSTORE_DIR / "chroma.sqlite3"
    if sqlite_path.exists():
        sqlite_path.unlink()

    # 배치 처리
    vectorstore = None
    total_batches = (len(chunks) + batch_size - 1) // batch_size

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_num = i // batch_size + 1
        print(f"  임베딩 배치 {batch_num}/{total_batches} ({len(batch)} 청크)...")

        if vectorstore is None:
            vectorstore = Chroma.from_documents(
                documents=batch,
                embedding=embeddings,
                persist_directory=persist_dir,
                collection_name="ajin_documents",
            )
        else:
            vectorstore.add_documents(batch)

    if vectorstore is not None:
        count = vectorstore._collection.count()
        print(f"  ChromaDB 저장 완료: {count} 청크")
    else:
        print("  ⚠️ 저장할 청크가 없습니다.")

    return vectorstore


def save_bm25_corpus(documents: list[Document]) -> None:
    """BM25 검색용 코퍼스를 JSON으로 저장한다. (pickle → JSON 보안 개선)"""
    splitter = create_splitter()
    chunks = splitter.split_documents(documents)

    corpus_data = []
    for chunk in chunks:
        corpus_data.append({
            "doc_id": chunk.metadata.get("doc_id", ""),
            "content": chunk.page_content,
            "metadata": chunk.metadata,
        })

    # JSON 저장 (pickle RCE 위험 제거)
    corpus_path = VECTORSTORE_DIR / "bm25_corpus.json"
    corpus_path.parent.mkdir(parents=True, exist_ok=True)
    with open(corpus_path, "w", encoding="utf-8") as f:
        json.dump(corpus_data, f, ensure_ascii=False)

    # 레거시 .pkl 파일이 존재하면 삭제
    legacy_pkl = VECTORSTORE_DIR / "bm25_corpus.pkl"
    if legacy_pkl.exists():
        legacy_pkl.unlink()

    print(f"  BM25 코퍼스 저장 완료: {len(corpus_data)} 청크 → {corpus_path}")


# ──────────────────────────────────────────────────────────────
# 실행 파이프라인
# ──────────────────────────────────────────────────────────────

def run_indexing():
    """전체 인덱싱 파이프라인을 실행한다."""
    print("=" * 60)
    print("📚 문서 인덱싱 시작 (확장판 — 전체 지식베이스)")
    print("=" * 60)

    all_documents: list[Document] = []

    # 1. 업무 문서 (8D, ECN, PPAP, 이메일, 회의록)
    print("\n[1/4] 업무 문서 로딩 중...")
    docs = load_documents(DOCUMENTS_DIR, METADATA_PATH)
    print(f"  → {len(docs)}건 (8D, ECN, PPAP, Email, Meeting)")
    all_documents.extend(docs)

    # 2. 지식베이스 (SOP, 부서 가이드, 협업 가이드)
    print("\n[2/4] 지식베이스 로딩 중...")
    kb_docs = load_knowledge_base(KNOWLEDGE_BASE_DIR)
    print(f"  → {len(kb_docs)}건 (SOP, Department Guide, Collaboration)")
    all_documents.extend(kb_docs)

    # 3. 용어집
    print("\n[3/4] 용어집 로딩 중...")
    glossary_docs = load_glossary(GLOSSARY_DIR)
    print(f"  → {len(glossary_docs)}건 (Glossary)")
    all_documents.extend(glossary_docs)

    # 4. 크롤링 규제 데이터
    print("\n[4/4] 크롤링 규제 데이터 로딩 중...")
    crawled_docs = load_crawled_data(CRAWLED_DIR)
    print(f"  → {len(crawled_docs)}건 (ISO, APQP, MSDS, 국내법, EU, OEM, ESG, EV, Global)")
    all_documents.extend(crawled_docs)

    # 총합
    print(f"\n총 로드 문서: {len(all_documents)}건")

    if not all_documents:
        print("⚠️ 로드된 문서가 없습니다.")
        return

    # 5. 청크 분할 + 임베딩 + ChromaDB 저장
    print("\n[5/6] 청크 분할 및 임베딩 중... (시간 소요)")
    vectorstore = build_vectorstore(all_documents)

    # 6. BM25 인덱스 구축용 코퍼스 저장
    print("\n[6/6] BM25 코퍼스 저장 중...")
    save_bm25_corpus(all_documents)

    # 소스별 통계
    print("\n" + "=" * 60)
    print("✅ 인덱싱 완료! 소스별 통계:")
    print("=" * 60)
    from collections import Counter
    type_counts = Counter(d.metadata["doc_type"] for d in all_documents)
    for dtype, count in sorted(type_counts.items()):
        print(f"  {dtype:30s} {count:>4}건")
    print(f"  {'TOTAL':30s} {len(all_documents):>4}건")
    print("=" * 60)

    return vectorstore


if __name__ == "__main__":
    run_indexing()
