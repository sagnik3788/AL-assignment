import json
import logging
import time
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)


class LLMError(RuntimeError):
    pass


class OpenRouter:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client or httpx.Client(timeout=settings.openrouter_timeout_seconds)
        self.prompt_tokens = 0
        self.completion_tokens = 0

    @property
    def enabled(self) -> bool:
        return bool(self.settings.openrouter_api_key)

    def complete_json(self, *, system: str, user: str, schema_name: str, schema: dict) -> dict[str, Any]:
        if not self.enabled:
            raise LLMError("OpenRouter is not configured")
        body = {
            "model": self.settings.openrouter_model,
            "temperature": 0,
            "max_tokens": 2500,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
        }
        headers = {
            "Authorization": f"Bearer {self.settings.openrouter_api_key}",
            "Content-Type": "application/json",
            "X-Title": "AI Study Assistant Assessment",
        }
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                response = self.client.post(
                    f"{self.settings.openrouter_base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=body,
                )
                response.raise_for_status()
                payload = response.json()
                usage = payload.get("usage", {})
                self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)
                content = payload["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise ValueError("Model returned non-text content")
                value = json.loads(content)
                if not isinstance(value, dict):
                    raise ValueError("Model response must be a JSON object")
                return value
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError, KeyError, IndexError, ValueError) as exc:
                last_error = exc
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                    break
                status = f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError) else type(exc).__name__
                logger.warning("OpenRouter request failed (attempt %s): %s", attempt + 1, status)
                if attempt == 0 and not isinstance(exc, ValueError):
                    time.sleep(0.25)
        raise LLMError(f"Model request failed: {type(last_error).__name__ if last_error else 'unknown error'}") from last_error
