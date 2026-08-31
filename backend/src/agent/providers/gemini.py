"""Google Gemini provider.

Structured output is requested with `response_mime_type=application/json` plus
a `response_schema`, so the model decodes into the shape we asked for rather
than into prose we would have to parse. The result is still validated by
Pydantic afterwards: a schema constrains generation, it does not guarantee it.

Failures are separated into two kinds, because they mean different things:
  - a key-level failure (quota, auth) rotates to the next key and retries;
  - anything else, or an exhausted pool, is ProviderUnavailableError, which
    the API surfaces as a 503 with a retry hint rather than a 500.
"""

from __future__ import annotations

import asyncio
import time

from google import genai
from google.genai import types as genai_types
from google.genai.errors import APIError, ClientError, ServerError

from src.agent.providers.base import ProviderRequest, ProviderResult
from src.agent.providers.key_pool import GeminiKeyPool, NoKeysAvailableError
from src.agent.schemas.response_schema import build_analysis_response_schema
from src.core.config import Settings
from src.core.errors import ProviderUnavailableError
from src.core.logger import get_logger
from src.models.analysis import TokenUsage
from src.models.enums import ProviderName

logger = get_logger(__name__)

# Status codes that mean "this key is spent", as opposed to "this request was
# bad" — only these justify rotating to a fallback key.
KEY_LEVEL_STATUS_CODES = frozenset({401, 403, 429})


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._key_pool = GeminiKeyPool(settings.gemini_key_list)
        self._model_id = settings.gemini_model_id
        self._response_schema = build_analysis_response_schema()

    @property
    def name(self) -> str:
        return ProviderName.GEMINI.value

    @property
    def model_id(self) -> str:
        return self._model_id

    async def generate_analysis(self, request: ProviderRequest) -> ProviderResult:
        attempted: set[str] = set()
        started = time.perf_counter()

        for _ in range(self._key_pool.size):
            try:
                key = self._key_pool.acquire(exclude=attempted)
            except NoKeysAvailableError as exc:
                raise ProviderUnavailableError from exc

            attempted.add(key)

            try:
                response = await self._call(key, request.prompt)
            except (ClientError, ServerError) as exc:
                if exc.code in KEY_LEVEL_STATUS_CODES:
                    self._key_pool.report_failure(key)
                    logger.warning(
                        "gemini_key_rotated",
                        extra={"status_code": exc.code, "keys_tried": len(attempted)},
                    )
                    continue
                logger.warning("gemini_request_failed", extra={"status_code": exc.code})
                raise ProviderUnavailableError from exc
            except (APIError, asyncio.TimeoutError) as exc:
                logger.warning("gemini_call_failed", extra={"error": type(exc).__name__})
                raise ProviderUnavailableError from exc

            self._key_pool.report_success(key)
            return self._to_result(response, started)

        raise ProviderUnavailableError

    async def _call(self, api_key: str, prompt: str) -> genai_types.GenerateContentResponse:
        client = genai.Client(api_key=api_key)
        config = genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=self._response_schema,
            max_output_tokens=self._settings.llm_max_output_tokens,
            temperature=0.1,
        )
        return await asyncio.wait_for(
            client.aio.models.generate_content(
                model=self._model_id,
                contents=prompt,
                config=config,
            ),
            timeout=self._settings.llm_timeout_seconds,
        )

    def _to_result(
        self, response: genai_types.GenerateContentResponse, started: float
    ) -> ProviderResult:
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = response.usage_metadata

        return ProviderResult(
            raw_text=response.text or "",
            model_id=self._model_id,
            latency_ms=latency_ms,
            token_usage=(
                TokenUsage(
                    prompt=usage.prompt_token_count or 0,
                    completion=usage.candidates_token_count or 0,
                    total=usage.total_token_count or 0,
                )
                if usage is not None
                else None
            ),
        )
