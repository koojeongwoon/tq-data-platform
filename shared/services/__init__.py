"""Shared services module"""

# Lazy imports to avoid dependency issues
__all__ = ["EmbeddingService", "get_embedding_service", "WelfareChunker", "QdrantService"]


def __getattr__(name):
    if name in ("EmbeddingService", "get_embedding_service"):
        from .embedding import EmbeddingService, get_embedding_service
        return EmbeddingService if name == "EmbeddingService" else get_embedding_service
    elif name == "WelfareChunker":
        from .chunker import WelfareChunker
        return WelfareChunker
    elif name == "QdrantService":
        from .qdrant_service import QdrantService
        return QdrantService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
