"""v1.6: 새로운 용어집 + 기업정보를 ChromaDB에 인덱싱하는 스크립트

사용법:
    cd ajin-ai-assistant
    python -m scripts.reindex_v16
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# 프로젝트 루트 설정
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config import KNOWLEDGE_BASE_DIR, GLOSSARY_DIR, VECTORSTORE_DIR


def index_glossary_terms():
    """용어집 JSON → ChromaDB 인덱싱 (각 용어를 1개 청크로)"""
    try:
        from langchain_chroma import Chroma
        from core.embedding_client import get_embeddings
    except ImportError as e:
        print(f"[SKIP] ChromaDB/embedding 모듈 없음: {e}")
        return 0

    embeddings = get_embeddings()
    vs = Chroma(
        persist_directory=str(VECTORSTORE_DIR / "glossary"),
        embedding_function=embeddings,
        collection_name="ajin_glossary",
    )

    texts, metadatas, ids = [], [], []
    for json_file in sorted(GLOSSARY_DIR.glob("*.json")):
        with open(json_file, encoding="utf-8") as f:
            data = json.load(f)

        # v2.0: 3종 JSON 구조 호환 (Array / Dict / Dict+metadata)
        if isinstance(data, dict) and "terms" in data:
            category = data.get("category", "unknown")
            items = data["terms"]
        elif isinstance(data, list):
            category = json_file.stem.replace("_terms", "").replace("_", " ")
            items = data
        elif isinstance(data, dict):
            category = "unknown"
            items = []
            for key, val in data.items():
                if isinstance(val, dict):
                    if "term" not in val:
                        val["term"] = key
                    items.append(val)
        else:
            continue

        for item in items:
            if isinstance(item, str):
                # 문자열만 있는 경우 (예: ["용어1", "용어2"])
                item = {"term": item, "definition": item}
            if not isinstance(item, dict):
                continue
            term = item.get("term", "")
            if not term:
                continue
            text = (
                f"{term} ({item.get('full_name', '')}) — {item.get('korean_name', '')}\n"
                f"정의: {item.get('definition', '')}\n"
                f"아진산업 맥락: {item.get('ajin_context', item.get('usage_example', ''))}"
            )
            texts.append(text)
            metadatas.append({
                "source": "glossary",
                "category": category,
                "term": term,
                "file": json_file.name,
            })
            ids.append(f"glossary_{term}")

    if texts:
        vs.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        print(f"[OK] 용어집 {len(texts)}개 항목 인덱싱 완료")
    return len(texts)


def index_company_info():
    """company_info 마크다운 → ChromaDB 인덱싱 (섹션별 청크)"""
    try:
        from langchain_chroma import Chroma
        from core.embedding_client import get_embeddings
    except ImportError as e:
        print(f"[SKIP] ChromaDB/embedding 모듈 없음: {e}")
        return 0

    company_dir = KNOWLEDGE_BASE_DIR / "company_info"
    if not company_dir.exists():
        print("[SKIP] company_info 디렉토리 없음")
        return 0

    embeddings = get_embeddings()
    vs = Chroma(
        persist_directory=str(VECTORSTORE_DIR / "company_info"),
        embedding_function=embeddings,
        collection_name="ajin_company_info",
    )

    texts, metadatas, ids = [], [], []
    for md_file in sorted(company_dir.glob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        # 섹션 기반 청킹 (## 헤더로 분할)
        sections = content.split("\n## ")
        for i, section in enumerate(sections):
            if not section.strip():
                continue
            chunk = section if i == 0 else f"## {section}"
            # 500자 이하면 통합, 초과 시 분할
            if len(chunk) > 1000:
                chunk = chunk[:1000]

            texts.append(chunk)
            metadatas.append({
                "source": "company_info",
                "category": md_file.stem,
                "file": md_file.name,
                "section_idx": i,
            })
            ids.append(f"company_{md_file.stem}_{i}")

    if texts:
        vs.add_texts(texts=texts, metadatas=metadatas, ids=ids)
        print(f"[OK] 기업정보 {len(texts)}개 청크 인덱싱 완료")
    return len(texts)


def _check_ollama() -> bool:
    """Ollama 서버가 실행 중인지 확인하고, bge-m3 모델을 사전 로드한다."""
    import requests

    # 1. 서버 연결 확인
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=3)
        if resp.status_code != 200:
            print(f"[ERROR] Ollama 서버 응답 비정상: HTTP {resp.status_code}")
            return False
        models = [m["name"] for m in resp.json().get("models", [])]
        print(f"[OK] Ollama 서버 연결 성공 — 모델: {', '.join(models[:5])}")
    except Exception as e:
        print(f"[ERROR] Ollama 서버에 연결할 수 없습니다: {e}")
        print("  → 'ollama serve' 명령으로 서버를 먼저 시작해주세요.")
        return False

    # 2. bge-m3 모델 사전 로드 (서버가 모델을 캐시에 올리도록 강제)
    print("[INFO] bge-m3 임베딩 모델 로드 중...")
    try:
        resp = requests.post(
            "http://localhost:11434/api/embed",
            json={"model": "bge-m3", "input": "warmup"},
            timeout=120,
        )
        if resp.status_code == 200:
            print("[OK] bge-m3 모델 로드 성공")
            return True
        # 404인 경우 — generate로 모델 로드 시도 후 재시도
        if resp.status_code == 404:
            print("[INFO] bge-m3가 /api/embed에서 인식되지 않음 — generate로 워밍업 시도...")
            resp2 = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "bge-m3", "prompt": "test", "stream": False},
                timeout=120,
            )
            if resp2.status_code == 200:
                print("[OK] bge-m3 모델 로드 완료 (generate 경유)")
                return True
            print(f"[ERROR] bge-m3 로드 실패: {resp2.text[:200]}")
            return False
        print(f"[ERROR] bge-m3 임베딩 테스트 실패: HTTP {resp.status_code}")
        return False
    except Exception as e:
        print(f"[ERROR] bge-m3 로드 실패: {e}")
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("v2.6 ChromaDB 재인덱싱 (용어집 + 기업정보)")
    print("=" * 50)

    # v2.6: Ollama 서버 사전 검증
    if not _check_ollama():
        print("\n[중단] Ollama 서버가 필요합니다. 임베딩 생성을 위해 BGE-M3 모델이 필요합니다.")
        print("  1. ollama serve")
        print("  2. ollama pull bge-m3")
        print("  3. python -m scripts.reindex_v16")
        sys.exit(1)

    g = index_glossary_terms()
    c = index_company_info()

    print(f"\n총 인덱싱: 용어집 {g}개 + 기업정보 {c}개 = {g + c}개")
    print("[완료] vectorstore/glossary/ 및 vectorstore/company_info/ 에 저장됨")
