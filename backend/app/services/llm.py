import logging
import httpx
import pybreaker
from app.config import settings

logger = logging.getLogger(__name__)


class LLMUnavailableError(Exception):
    """Raised when the LLM circuit breaker is OPEN or the request times out."""


# Circuit breaker: 5 failures → OPEN for 20 seconds
_breaker = pybreaker.CircuitBreaker(fail_max=5, reset_timeout=20)


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
    """Send a plain prompt to Google Gemini API (no tools)."""
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        response = await client.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except (KeyError, IndexError) as e:
            logger.error("Unexpected Gemini response structure: %s", data)
            raise ValueError("Invalid response from Gemini API") from e


async def _generate_openai(prompt: str) -> str:
    """Send a plain prompt to OpenAI Chat Completions API."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()


async def _generate_gemini_with_tools(prompt: str, tools: list) -> str:
    """
    Send a prompt to Gemini with function calling tools.
    Handles multi-turn tool call → result → final answer loop.
    """
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set")

    from app.services.psx_tools import TOOL_FUNCTIONS

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent?key={settings.gemini_api_key}"
    contents = [{"role": "user", "parts": [{"text": prompt}]}]
    payload = {"contents": contents, "tools": tools}

    async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
        for _ in range(5):
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidate = data["candidates"][0]["content"]
            parts = candidate.get("parts", [])
            text_parts = [p["text"] for p in parts if "text" in p]
            func_calls = [p["functionCall"] for p in parts if "functionCall" in p]

            if not func_calls:
                return " ".join(text_parts).strip()

            function_response_parts = []
            for fc in func_calls:
                func_name = fc["name"]
                func_args = fc.get("args", {})
                logger.info("Calling PSX tool: %s(%s)", func_name, func_args)
                tool_fn = TOOL_FUNCTIONS.get(func_name)
                if tool_fn:
                    import inspect
                    result = await tool_fn(**func_args) if inspect.iscoroutinefunction(tool_fn) else tool_fn(**func_args)
                else:
                    result = {"error": f"Unknown tool: {func_name}"}
                logger.info("Tool result: %s", result)
                function_response_parts.append({
                    "functionResponse": {"name": func_name, "response": {"result": result}}
                })

            contents.append({"role": "model", "parts": parts})
            contents.append({"role": "user", "parts": function_response_parts})
            payload["contents"] = contents

    return "I was unable to complete the request. Please try again."


@_breaker
async def generate(prompt: str) -> str:
    """Send a prompt to the configured LLM and return the generated text."""
    provider = settings.llm_provider.lower()
    try:
        if provider == "ollama":
            return await _generate_ollama(prompt)
        elif provider == "gemini":
            return await _generate_gemini(prompt)
        elif provider == "openai":
            return await _generate_openai(prompt)
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


@_breaker
async def generate_with_tools(prompt: str, tools: list) -> str:
    """Send a prompt with tool support (Gemini only). Falls back to plain generate for others."""
    provider = settings.llm_provider.lower()
    try:
        if provider == "gemini":
            return await _generate_gemini_with_tools(prompt, tools)
        elif provider == "openai":
            return await _generate_openai(prompt)
        else:
            return await _generate_ollama(prompt)
    except httpx.TimeoutException as exc:
        logger.warning("%s tool request timed out: %s", provider, exc)
        raise
    except httpx.HTTPStatusError as exc:
        logger.error("%s HTTP error %s: %s", provider, exc.response.status_code, exc)
        raise
    except Exception as exc:
        logger.error("%s tool generation failed: %s", provider, exc)
        raise


async def _get_fallback(prompt: str) -> str | None:
    """Return a response from the fallback provider (opposite of the primary)."""
    provider = settings.llm_provider.lower()
    if provider == "openai":
        # Primary is OpenAI → fall back to Gemini
        if not settings.gemini_api_key:
            return None
        try:
            result = await _generate_gemini(prompt)
            logger.info("Gemini fallback succeeded")
            return result
        except Exception as exc:
            logger.error("Gemini fallback failed: %s", exc)
            return None
    else:
        # Primary is Gemini/Ollama → fall back to OpenAI
        if not settings.openai_api_key:
            return None
        try:
            result = await _generate_openai(prompt)
            logger.info("OpenAI fallback succeeded")
            return result
        except Exception as exc:
            logger.error("OpenAI fallback failed: %s", exc)
            return None


async def safe_generate(prompt: str) -> str | None:
    """Generate a response; automatically falls back to the other provider on failure."""
    try:
        return await generate(prompt)
    except pybreaker.CircuitBreakerError:
        logger.warning("LLM circuit breaker OPEN — trying fallback provider")
        return await _get_fallback(prompt)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            logger.warning("LLM rate limited (429) — trying fallback provider")
            return await _get_fallback(prompt)
        logger.error("LLM generation failed: %s", exc)
        return None
    except Exception as exc:
        logger.error("LLM generation failed: %s", exc)
        return None


async def safe_generate_with_tools(prompt: str, tools: list) -> str | None:
    """Generate with tools; automatically falls back to the other provider on failure."""
    try:
        return await generate_with_tools(prompt, tools)
    except pybreaker.CircuitBreakerError:
        logger.warning("LLM circuit breaker OPEN — trying fallback provider")
        return await _get_fallback(prompt)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            logger.warning("LLM rate limited (429) — trying fallback provider")
            return await _get_fallback(prompt)
        logger.error("LLM tool generation failed: %s", exc)
        return None
    except Exception as exc:
        logger.error("LLM tool generation failed: %s", exc)
        return None
