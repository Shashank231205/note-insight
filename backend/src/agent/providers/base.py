"""The boundary between the application and any language model.

Everything above this line is provider-agnostic. Adding a second provider is a
new implementation of `LLMProvider` plus one configuration value; because each
analysis records the provider and model id it came from, historical rows stay
interpretable after the switch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from src.models.analysis import TokenUsage


@dataclass(frozen=True)
class ProviderRequest:
    """What to send, and the note it was built from.

    `prompt` is the fully rendered instruction text — the only thing a real
    provider transmits. `note_content` is the clinician's raw note, carried
    alongside because callers that reason about the source (the mock provider,
    and any future provider that needs the note separately) must not have to
    parse it back out of the prompt.
    """

    prompt: str
    note_content: str
    prompt_version: str


@dataclass(frozen=True)
class ProviderResult:
    """Raw text plus the metadata needed to make the call auditable.

    The text is deliberately unparsed: interpreting it is the validator's job,
    not the transport's.
    """

    raw_text: str
    model_id: str
    latency_ms: int
    token_usage: TokenUsage | None


@runtime_checkable
class LLMProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def model_id(self) -> str: ...

    async def generate_analysis(self, request: ProviderRequest) -> ProviderResult:
        """Return the model's raw response.

        Raises ProviderUnavailableError when the model could not be reached at
        all — which is a different outcome from a model that answered badly,
        and the two are handled differently upstream.
        """
        ...
