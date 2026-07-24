"""Chat-model and embeddings factories."""
from __future__ import annotations

import hashlib
from typing import List

import numpy as np
from langchain_core.embeddings import Embeddings

from ..config import settings


def build_chat_model():
    """Build the default OpenRouter chat model.

    Uses ``langchain_openrouter.ChatOpenRouter`` (the langchain-openrouter
    integration package). Raises a clear error when the API key is missing.
    """
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. The chat model requires an "
            "OpenRouter API key to run. Set OPENROUTER_API_KEY in the "
            "environment (see .env.example)."
        )

    from langchain_openrouter import ChatOpenRouter

    return ChatOpenRouter(
        model=settings.OPENROUTER_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0,
    )


class FakeEmbeddings(Embeddings):
    """Deterministic, offline embeddings.

    Hashes text into a reproducible float vector of length ``EMBEDDING_DIM``
    and L2-normalizes it so cosine distance behaves sensibly. Requires zero
    external calls, letting the whole stack run offline.
    """

    def __init__(self, dim: int):
        self.dim = dim

    def _embed(self, text: str) -> List[float]:
        # Seed a deterministic RNG from a stable hash of the text.
        digest = hashlib.sha256((text or "").encode("utf-8")).digest()
        seed = int.from_bytes(digest[:8], "big", signed=False)
        rng = np.random.default_rng(seed)
        vec = rng.standard_normal(self.dim).astype(np.float32)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._embed(text)

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.embed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return self.embed_query(text)


def build_embeddings() -> Embeddings:
    if settings.EMBEDDINGS_PROVIDER.lower() == "ollama":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(
            model=settings.OLLAMA_EMBED_MODEL,
            base_url=settings.OLLAMA_BASE_URL,
        )
    return FakeEmbeddings(dim=settings.EMBEDDING_DIM)
