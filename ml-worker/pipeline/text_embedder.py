"""nomic-embed-text text embedding via sentence-transformers."""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768
TASK_PREFIX = "search_document: "


class TextEmbedder:
    """
    nomic-embed-text-v1.5 wrapper using sentence-transformers with MPS.
    """

    def __init__(self):
        self._model = None

    def load(self) -> bool:
        """Load the model. Returns True on success."""
        try:
            from sentence_transformers import SentenceTransformer
            import torch

            device = "cpu"
            try:
                if torch.backends.mps.is_available():
                    device = "mps"
            except Exception:
                pass

            self._model = SentenceTransformer(
                MODEL_NAME,
                trust_remote_code=True,
                device=device,
            )
            logger.info("Text embedder loaded on %s", device)
            return True
        except ImportError:
            logger.warning("sentence-transformers not installed; semantic search disabled")
        except Exception as e:
            logger.error("Failed to load text embedder: %s", e)
        return False

    def embed(self, text: str, is_query: bool = False) -> Optional[np.ndarray]:
        """
        Embed text. Returns 768-d float32 numpy array.
        Use is_query=True for search queries (uses search_query prefix).
        """
        if self._model is None:
            return None

        prefix = "search_query: " if is_query else TASK_PREFIX
        prefixed = prefix + text.strip()

        try:
            embedding = self._model.encode(
                prefixed,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error("Text embedding error: %s", e)
            return None

    def embed_batch(self, texts: list[str]) -> Optional[np.ndarray]:
        """Batch embed multiple texts."""
        if self._model is None:
            return None
        prefixed = [TASK_PREFIX + t.strip() for t in texts]
        try:
            return self._model.encode(
                prefixed,
                normalize_embeddings=True,
                show_progress_bar=False,
            ).astype(np.float32)
        except Exception as e:
            logger.error("Batch embedding error: %s", e)
            return None

    @property
    def is_loaded(self) -> bool:
        return self._model is not None
