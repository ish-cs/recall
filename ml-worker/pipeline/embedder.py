"""Resemblyzer speaker embedding (256-d) wrapper."""

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 256
AUTO_LINK_THRESHOLD = 0.85
SUGGEST_THRESHOLD = 0.70
MAX_EXEMPLARS = 20
MIN_SPEECH_SECONDS = 2.0


class SpeakerEmbedder:
    """
    Resemblyzer GE2E model wrapper.
    Generates 256-d speaker embeddings and matches against stored profiles.
    """

    def __init__(self):
        self._encoder = None

    def load(self) -> bool:
        """Load Resemblyzer. Returns True on success."""
        try:
            from resemblyzer import VoiceEncoder
            self._encoder = VoiceEncoder(device="cpu")
            logger.info("Speaker embedder loaded")
            return True
        except ImportError:
            logger.warning("resemblyzer not installed; speaker matching disabled")
        except Exception as e:
            logger.error("Failed to load speaker embedder: %s", e)
        return False

    def embed(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[np.ndarray]:
        """
        Generate a 256-d speaker embedding from audio.
        Returns None if audio is too short or model not loaded.
        """
        if self._encoder is None:
            return None

        duration_s = len(audio) / sample_rate
        if duration_s < MIN_SPEECH_SECONDS:
            logger.debug("Audio too short for embedding: %.1fs", duration_s)
            return None

        try:
            # Resemblyzer expects float32 at 16kHz
            embedding = self._encoder.embed_utterance(audio)
            return embedding
        except Exception as e:
            logger.error("Embedding error: %s", e)
            return None

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two embeddings."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def match_profile(
        self,
        embedding: np.ndarray,
        exemplars: list[np.ndarray],
    ) -> float:
        """
        Compute match score against a list of exemplar embeddings.
        Returns max cosine similarity.
        """
        if not exemplars:
            return 0.0
        scores = [self.cosine_similarity(embedding, ex) for ex in exemplars]
        return max(scores)

    def classify_match(self, score: float) -> str:
        """Returns 'auto', 'suggest', or 'new' based on score thresholds."""
        if score >= AUTO_LINK_THRESHOLD:
            return "auto"
        elif score >= SUGGEST_THRESHOLD:
            return "suggest"
        else:
            return "new"

    @property
    def is_loaded(self) -> bool:
        return self._encoder is not None
