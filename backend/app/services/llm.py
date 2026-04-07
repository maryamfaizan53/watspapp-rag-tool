import logging

import httpx
import pybreaker

from app.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the LLM circuit breaker is OPEN or the request times out."""


# Circuit breaker: 3 failures → OPEN for 30 seconds
_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=30)


@_breaker
async def generate(prompt: str) -> str:
    """Send a prompt to Ollama and return the generated text."""
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{settings.ollama_base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
    except httpx.TimeoutException as exc:
        logger.warning("Ollama request timed out: %s", exc)
        raise
    except httpx.HTTPStatusError as exc:
        logger.error("Ollama HTTP error %s: %s", exc.response.status_code, exc)
        raise


async def safe_generate(prompt: str) -> str | None:
    """
    Generate a response, returning None if the circuit is OPEN or request fails.
    Callers should treat None as 'LLM unavailable'.
    """
    try:
        return await generate(prompt)
    except pybreaker.CircuitBreakerError:
        logger.warning("Ollama circuit breaker is OPEN — returning None")
        return None
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        return None
