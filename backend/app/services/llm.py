import logging
import httpx
import pybreaker
from app.config import settings

logger = logging.getLogger(__name__)

class LLMUnavailableError(Exception):
    """Raised when the LLM circuit breaker is OPEN or the request times out."""

# Circuit breaker: 3 failures → OPEN for 30 seconds
_breaker = pybreaker.CircuitBreaker(fail_max=3, reset_timeout=30)

async def _generate_ollama(prompt: str) -> str:
    """Send a prompt to Ollama."""
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.ollama_base_url}/api/generate",
            json=payload,
        )
        response.raise_for_status()
        return response.json().get("response", "").strip()

async def _generate_gemini(prompt: str) -> str:
    """Send a prompt to Google Gemini API."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    
    url = f"https://generativelanguage.googleapis.com/v1/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as e:
            logger.error("Unexpected Gemini response structure: %s", data)
            raise ValueError("Invalid response from Gemini API") from e

@_breaker
async def generate(prompt: str) -> str:
    """Send a prompt to the configured LLM provider and return the generated text."""
    provider = settings.llm_provider.lower()
    
    try:
        if provider == "ollama":
            return await _generate_ollama(prompt)
        elif provider == "gemini":
            return await _generate_gemini(prompt)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
            
    except httpx.TimeoutException as exc:
        logger.warning("%s request timed out: %s", provider, exc)
        raise
    except httpx.HTTPStatusError as exc:
        logger.error("%s HTTP error %s: %s", provider, exc.response.status_code, exc)
        raise
    except Exception as exc:
        logger.error("%s generation failed: %s", provider, exc)
        raise

async def safe_generate(prompt: str) -> str | None:
    """
    Generate a response, returning None if the circuit is OPEN or request fails.
    Callers should treat None as 'LLM unavailable'.
    """
    try:
        return await generate(prompt)
    except pybreaker.CircuitBreakerError:
        logger.warning("LLM circuit breaker is OPEN — returning None")
        return None
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        return None
