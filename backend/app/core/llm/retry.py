"""Retry helpers for transient LLM errors."""

from __future__ import annotations

from .types import (
    LLMRateLimitError, LLMConnectionError, LLMOverloadedError,
)


def is_retryable(exc: Exception) -> bool:
    """Check if an error is transient and worth retrying.

    Handles both generic LLM error types and provider-specific errors
    (for cases where errors bypass translation, e.g. during streaming).
    """
    import asyncio

    # Generic LLM errors
    if isinstance(
        exc, (LLMRateLimitError, LLMConnectionError, LLMOverloadedError)
    ):
        return True

    # Standard Python errors
    if isinstance(exc, (asyncio.TimeoutError, ConnectionError, TimeoutError)):
        return True

    # httpx transport errors (connection drops mid-stream)
    try:
        import httpx
        import httpcore
        if isinstance(exc, (httpx.ReadError, httpx.RemoteProtocolError, httpx.ConnectError)):
            return True
        if isinstance(exc, (httpcore.ReadError, httpcore.RemoteProtocolError, httpcore.ConnectError)):
            return True
    except ImportError:
        pass

    # Provider-specific (fallback for untranslated errors)
    try:
        import anthropic

        if isinstance(exc, anthropic.RateLimitError):
            return True
        if (
            isinstance(exc, anthropic.APIStatusError)
            and exc.status_code in (429, 529)
        ):
            return True
        if isinstance(
            exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)
        ):
            return True
        if isinstance(exc, anthropic.InternalServerError):
            return True
    except ImportError:
        pass

    try:
        import openai

        if isinstance(exc, openai.RateLimitError):
            return True
        if (
            isinstance(exc, openai.APIStatusError)
            and exc.status_code in (429, 529)
        ):
            return True
        if isinstance(
            exc, (openai.APIConnectionError, openai.APITimeoutError)
        ):
            return True
        if isinstance(exc, openai.InternalServerError):
            return True
        # Generic APIError with "Provider returned error" — transient OpenRouter issue
        if isinstance(exc, openai.APIError):
            msg = str(exc).lower()
            if "provider returned error" in msg or "provider" in msg:
                return True
    except ImportError:
        pass

    return False


def extract_retry_after(exc: Exception) -> float | None:
    """Extract Retry-After header from API errors.

    Checks the error itself and __cause__ (for wrapped LLM errors).
    """
    for err in (exc, getattr(exc, "__cause__", None)):
        if err is None:
            continue
        response = getattr(err, "response", None)
        if response is not None:
            headers = getattr(response, "headers", None)
            if headers:
                val = headers.get("retry-after")
                if val:
                    try:
                        return float(val)
                    except (ValueError, TypeError):
                        pass
    return None

