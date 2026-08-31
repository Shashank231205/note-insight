"""Transport failures must surface as provider unavailability, not as bugs.

A network, DNS or TLS failure means the model could not be reached. From the
clinician's side that is indistinguishable from an outage, and the note is
already saved either way — so it belongs on the 503 path with a retry hint,
never on the 500 path that reads as a defect in the application.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest

from src.agent.providers.base import ProviderRequest
from src.agent.providers.gemini import GeminiProvider
from src.core.config import Environment, LLMProviderName, Settings
from src.core.errors import ProviderUnavailableError

NOTE = "Patient seen for follow-up of hypertension."


def _settings() -> Settings:
    return Settings(
        environment=Environment.TEST,
        llm_provider=LLMProviderName.GEMINI,
        gemini_api_keys="key-primary,key-fallback",
        firebase_project_id="note-insight-test",
    )


def _request() -> ProviderRequest:
    return ProviderRequest(prompt="prompt", note_content=NOTE, prompt_version="v1")


@pytest.mark.parametrize(
    "raised",
    [
        httpx.ConnectError("dns failure"),
        httpx.ReadTimeout("read timed out"),
        OSError("certificate verify failed"),
        asyncio.TimeoutError(),
    ],
    ids=["connect-error", "read-timeout", "tls-error", "timeout"],
)
async def test_transport_failures_become_provider_unavailable(
    monkeypatch: pytest.MonkeyPatch, raised: Exception
) -> None:
    provider = GeminiProvider(_settings())

    async def fail(*_args: object, **_kwargs: object) -> object:
        raise raised

    monkeypatch.setattr(provider, "_call", fail)

    with pytest.raises(ProviderUnavailableError):
        await provider.generate_analysis(_request())


async def test_a_transport_failure_does_not_burn_the_key_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only quota and auth failures retire a key.

    A dropped connection says nothing about the key's health; benching it would
    spend the fallback for a reason that has nothing to do with either key.
    """
    provider = GeminiProvider(_settings())

    async def fail(*_args: object, **_kwargs: object) -> object:
        raise httpx.ConnectError("network down")

    monkeypatch.setattr(provider, "_call", fail)

    with pytest.raises(ProviderUnavailableError):
        await provider.generate_analysis(_request())

    assert len(provider._key_pool.available_keys()) == 2
