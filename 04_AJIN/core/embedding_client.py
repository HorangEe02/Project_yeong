"""임베딩 클라이언트 — Ollama / Gemini 백엔드 자동 선택.

환경변수:
  EMBEDDING_BACKEND=ollama|gemini|auto  (기본 auto)
  - auto: OLLAMA_BASE_URL 비어있으면 gemini, 아니면 ollama
  - ollama: bge-m3 (1024 dims)
  - gemini: text-embedding-004 (768 dims)

⚠️ 주의: 백엔드 전환 시 차원이 다르므로 기존 ChromaDB 인덱스 재빌드 필요.
   scripts/reembed_to_gemini.py 사용.
"""

from __future__ import annotations

import os
from typing import List

from config import OLLAMA_BASE_URL, EMBEDDING_MODEL, ollama_headers


def _embedding_backend() -> str:
    """env > OLLAMA_BASE_URL 유무 > 기본 ollama 순서로 결정."""
    explicit = os.environ.get("EMBEDDING_BACKEND", "").strip().lower()
    if explicit in ("ollama", "gemini"):
        return explicit
    if not (OLLAMA_BASE_URL or "").strip():
        return "gemini"
    return "ollama"


class GeminiEmbeddings:
    """LangChain Embeddings 인터페이스 호환 — google-genai SDK 직접 호출.

    - embed_documents(texts) → list[list[float]]
    - embed_query(text)      → list[float]
    """

    DEFAULT_MODEL = "gemini-embedding-001"  # 3072 dims (output_dimensionality 로 768 까지 축소 가능)

    def __init__(self, model: str | None = None, api_key: str | None = None):
        try:
            from google import genai  # type: ignore
        except ImportError as e:
            raise ImportError(
                "google-genai 패키지가 필요합니다. pip install google-genai"
            ) from e

        key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY 환경변수가 설정되어야 Gemini 임베딩 사용 가능."
            )

        self._client = genai.Client(api_key=key)
        self._model = model or self.DEFAULT_MODEL

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        # Gemini API 는 단일/배치 모두 지원하지만, 호환성 위해 순차 호출
        # (대량 배치는 batch_embed_contents 메서드가 더 효율적)
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        result = self._client.models.embed_content(
            model=self._model,
            contents=text,
        )
        embeddings = getattr(result, "embeddings", None)
        if not embeddings:
            raise RuntimeError(f"Gemini 임베딩 응답에 embeddings 없음: {result}")
        # SDK 버전에 따라 result.embeddings[0].values 또는 result.embedding.values
        first = embeddings[0]
        values = getattr(first, "values", None) or getattr(first, "embedding", None)
        if values is None:
            raise RuntimeError(f"Gemini 임베딩 결과 파싱 실패: {first}")
        return list(values)


def get_embeddings(model: str = EMBEDDING_MODEL):
    """환경변수 기반 임베딩 클라이언트 반환.

    LangChain Chroma 와 호환되는 객체 반환 (embed_documents/embed_query 메서드).
    """
    backend = _embedding_backend()

    if backend == "gemini":
        return GeminiEmbeddings()

    # ollama 기본
    # Plan A 변형: Caddy 경유 시 X-AJIN-Secret 헤더 부착 (langchain_ollama 0.x: client_kwargs)
    from langchain_ollama import OllamaEmbeddings
    _hdrs = ollama_headers()
    if _hdrs:
        return OllamaEmbeddings(
            model=model,
            base_url=OLLAMA_BASE_URL,
            client_kwargs={"headers": _hdrs},
        )
    return OllamaEmbeddings(model=model, base_url=OLLAMA_BASE_URL)
