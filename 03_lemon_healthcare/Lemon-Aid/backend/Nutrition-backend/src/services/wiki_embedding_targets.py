"""Registry of WIKI embedding models and their pgvector storage tables.

Each embedding model emits vectors of a fixed dimension, and pgvector columns are
dimension-typed, so every model is stored in a dedicated table. This module is the
single source of truth for the model -> (table, dimension, prompt) mapping shared
by the retrieval service (:mod:`src.services.llm_wiki_retrieval`) and the ingestion
and comparison scripts, so the read and write paths never drift apart.

Prompt prefixes follow each model's documented retrieval convention:

- ``bge-m3`` embeds raw text on both sides, matching the originally ingested data
  (changing it would desynchronize the existing 1024-dim embeddings from queries).
- ``embeddinggemma`` is instruction-tuned and expects asymmetric prompts: a
  ``task: search result | query:`` prefix for queries and a ``title: none | text:``
  prefix for documents (Google EmbeddingGemma model card / sentence-transformers
  prompt names). Ollama's template for the model is a bare ``{{ .Prompt }}`` (it
  does not auto-apply these), and the prefix materially changes the vector, so the
  query and document sides must use the matching prefixes to retrieve well.
"""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_EMBEDDING_MODEL = "bge-m3"

# EmbeddingGemma retrieval prompts (canonical sentence-transformers prompt names).
_GEMMA_QUERY_PREFIX = "task: search result | query: "
_GEMMA_DOCUMENT_PREFIX = "title: none | text: "


@dataclass(frozen=True)
class WikiEmbeddingTarget:
    """Storage and prompt descriptor for one WIKI embedding model.

    Attributes:
        model: Ollama embedding model name (matches ``embedding_model`` rows).
        table: ``public`` table holding this model's chunk embeddings.
        dimensions: Fixed embedding dimension of the table's ``embedding`` column.
        query_prompt_prefix: Text prepended to a query before embedding.
        document_prompt_prefix: Text prepended to a document chunk before embedding.
    """

    model: str
    table: str
    dimensions: int
    query_prompt_prefix: str = ""
    document_prompt_prefix: str = ""

    def format_query(self, text: str) -> str:
        """Return query text with this model's retrieval prefix applied.

        Args:
            text: Raw query text.

        Returns:
            The query text with the model's query prefix prepended.
        """
        return f"{self.query_prompt_prefix}{text}"

    def format_document(self, text: str) -> str:
        """Return document text with this model's retrieval prefix applied.

        Args:
            text: Raw document/chunk text.

        Returns:
            The document text with the model's document prefix prepended.
        """
        return f"{self.document_prompt_prefix}{text}"


_TARGETS: dict[str, WikiEmbeddingTarget] = {
    "bge-m3": WikiEmbeddingTarget(
        model="bge-m3",
        table="wiki_chunk_embeddings",
        dimensions=1024,
    ),
    "embeddinggemma": WikiEmbeddingTarget(
        model="embeddinggemma",
        table="wiki_chunk_embeddings_gemma",
        dimensions=768,
        query_prompt_prefix=_GEMMA_QUERY_PREFIX,
        document_prompt_prefix=_GEMMA_DOCUMENT_PREFIX,
    ),
}

# Allowlist of embedding table names. The retrieval service interpolates the table
# name into SQL (pgvector columns are dimension-typed, so the table cannot be a
# bound parameter), so only registry-owned identifiers may ever reach a query.
EMBEDDING_TABLES: frozenset[str] = frozenset(target.table for target in _TARGETS.values())


def known_models() -> tuple[str, ...]:
    """Return the registered embedding model names in definition order.

    Returns:
        Tuple of known embedding model names.
    """
    return tuple(_TARGETS)


def get_target(model: str) -> WikiEmbeddingTarget:
    """Return the storage and prompt target for an embedding model.

    Args:
        model: Embedding model name.

    Returns:
        The matching :class:`WikiEmbeddingTarget`.

    Raises:
        KeyError: If the model is not registered.
    """
    try:
        return _TARGETS[model]
    except KeyError as exc:
        raise KeyError(
            f"unknown WIKI embedding model {model!r}; known: {', '.join(_TARGETS)}"
        ) from exc
