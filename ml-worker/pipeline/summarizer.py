"""Ollama-based conversation summarization (optional cold path)."""

import json
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

OLLAMA_URL = "http://localhost:11434"
TIMEOUT_SECONDS = 30

SUMMARY_PROMPT = """\
Given this conversation transcript, extract:
1. A one-sentence summary (max 25 words)
2. Up to 5 topic tags (single words or short phrases)

Transcript:
{transcript}

Respond in JSON: {{"summary": "...", "tags": ["...", "..."]}}"""


class Summarizer:
    """
    Ollama HTTP client for conversation summarization.
    Gracefully degrades if Ollama is not running.
    """

    def __init__(self, model: str = "qwen2.5:7b"):
        self.model = model
        self._available: Optional[bool] = None

    async def check_available(self) -> bool:
        """Check if Ollama is running. Cached after first check."""
        if self._available is not None:
            return self._available
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{OLLAMA_URL}/api/tags")
                self._available = resp.status_code == 200
        except Exception:
            self._available = False
        logger.info("Ollama available: %s", self._available)
        return self._available

    async def summarize(
        self, transcript_text: str
    ) -> tuple[Optional[str], list[str]]:
        """
        Summarize a conversation transcript.
        Returns (summary, tags) or (None, []) if unavailable/failed.
        """
        if not await self.check_available():
            return None, []

        prompt = SUMMARY_PROMPT.format(transcript=transcript_text[:8000])

        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                resp = await client.post(
                    f"{OLLAMA_URL}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                result_text = data.get("response", "{}")

                result = json.loads(result_text)
                summary = result.get("summary")
                tags = result.get("tags", [])

                if isinstance(summary, str) and isinstance(tags, list):
                    return summary.strip(), [str(t).strip() for t in tags[:5]]
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse Ollama response: %s", e)
        except Exception as e:
            logger.warning("Summarization failed: %s", e)

        return None, []
