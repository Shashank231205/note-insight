"""Orchestration of the analysis pipeline.

The only layer permitted to combine a provider with a repository. It owns the
decisions the brief asks us to make deliberately:

  - what happens when the model returns garbage (persist the failure, tell the
    truth, keep the note)
  - what happens when the same note is analyzed twice (a new document; the old
    one survives)
  - what happens to a quote that cannot be found in the note (flagged, kept,
    surfaced to the clinician)
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from src.agent.prompts.registry import render_prompt
from src.agent.providers.base import LLMProvider, ProviderRequest, ProviderResult
from src.agent.schemas.raw_output import RawAnalysis
from src.agent.validators.evidence import build_verification_report
from src.agent.validators.output import parse_analysis_output
from src.core.errors import AnalysisNotFoundError, ProviderUnavailableError
from src.core.logger import get_logger
from src.models.analysis import (
    Analysis,
    AnalysisFailure,
    AnalysisOutput,
    Condition,
    DocumentationGap,
    VerificationReport,
)
from src.models.enums import AnalysisStatus, ProviderName
from src.models.note import Note
from src.models.user import AuthenticatedUser
from src.repositories.base import AnalysisRepository, NoteRepository
from src.utils.ids import new_id

logger = get_logger(__name__)


class AnalysisService:
    def __init__(
        self,
        provider: LLMProvider,
        analyses: AnalysisRepository,
        notes: NoteRepository,
        prompt_version: str,
    ) -> None:
        self._provider = provider
        self._analyses = analyses
        self._notes = notes
        self._prompt_version = prompt_version

    async def analyze(
        self, caller: AuthenticatedUser, note: Note, force: bool = False
    ) -> Analysis:
        if not force:
            cached = await self._analyses.find_cached(
                owner_uid=caller.uid,
                content_hash=note.content_hash,
                prompt_version=self._prompt_version,
                model_id=self._provider.model_id,
            )
            if cached is not None:
                logger.info(
                    "analysis_cache_hit",
                    extra={"note_id": note.note_id, "analysis_id": cached.analysis_id},
                )
                return cached

        analysis = await self._run_pipeline(caller, note)
        stored = await self._analyses.create(analysis)

        await self._notes.apply_analysis_result(
            note_id=note.note_id,
            owner_uid=caller.uid,
            analysis_id=stored.analysis_id,
            condition_count=stored.condition_count,
        )
        return stored

    async def get_owned(self, caller: AuthenticatedUser, analysis_id: str) -> Analysis:
        analysis = await self._analyses.get(analysis_id, caller.uid)
        if analysis is None:
            raise AnalysisNotFoundError
        return analysis

    async def list_for_note(self, caller: AuthenticatedUser, note_id: str) -> list[Analysis]:
        return await self._analyses.list_for_note(note_id, caller.uid)

    async def _run_pipeline(self, caller: AuthenticatedUser, note: Note) -> Analysis:
        started = time.perf_counter()
        prompt = render_prompt(self._prompt_version, note.content)

        try:
            result = await self._provider.generate_analysis(
                ProviderRequest(
                    prompt=prompt,
                    note_content=note.content,
                    prompt_version=self._prompt_version,
                )
            )
        except ProviderUnavailableError:
            # Nothing was produced, so nothing is persisted and the caller gets
            # a 503. The note itself is already saved and can be retried.
            logger.warning("provider_unavailable", extra={"note_id": note.note_id})
            raise

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        parsed = parse_analysis_output(result.raw_text)

        if parsed.analysis is None:
            failure = parsed.failure
            assert failure is not None
            logger.warning(
                "analysis_output_invalid",
                extra={"note_id": note.note_id, "failure_code": failure.code.value},
            )
            return self._build_analysis(
                caller=caller,
                note=note,
                status=AnalysisStatus.INVALID_OUTPUT,
                output=None,
                verification=None,
                failure=AnalysisFailure(
                    code=failure.code.value,
                    message=failure.message,
                    raw_excerpt=failure.raw_excerpt,
                ),
                latency_ms=elapsed_ms,
                result=result,
            )

        output = self._assign_identifiers(parsed.analysis)
        report, _ = build_verification_report(
            note.content,
            {condition.condition_id: condition.evidence_quote for condition in output.conditions},
        )

        logger.info(
            "analysis_completed",
            extra={
                "note_id": note.note_id,
                "condition_count": len(output.conditions),
                "unverified_quotes": report.unverified_count,
                "latency_ms": elapsed_ms,
            },
        )

        return self._build_analysis(
            caller=caller,
            note=note,
            status=AnalysisStatus.SUCCEEDED,
            output=output,
            verification=report,
            failure=None,
            latency_ms=elapsed_ms,
            result=result,
        )

    def _assign_identifiers(self, raw: RawAnalysis) -> AnalysisOutput:
        """Attach server-generated ids to the model's findings.

        Reviews reference these ids, so they are ours to mint. Gaps are linked
        to conditions by name here and by id everywhere after.
        """
        conditions = [
            Condition(
                condition_id=new_id(),
                name=raw_condition.condition_name,
                evidence_quote=raw_condition.evidence_quote,
                documentation_status=raw_condition.documentation_status,
                icd10_code=raw_condition.icd10_code,
                confidence=raw_condition.confidence,
            )
            for raw_condition in raw.conditions
        ]
        id_by_name = {condition.name.casefold(): condition.condition_id for condition in conditions}

        gaps = [
            DocumentationGap(
                gap_id=new_id(),
                description=raw_gap.description,
                related_condition_id=(
                    id_by_name.get(raw_gap.related_condition_name.casefold())
                    if raw_gap.related_condition_name
                    else None
                ),
                severity=raw_gap.severity,
            )
            for raw_gap in raw.documentation_gaps
        ]

        return AnalysisOutput(
            summary=raw.summary,
            conditions=conditions,
            documentation_gaps=gaps,
        )

    def _build_analysis(
        self,
        caller: AuthenticatedUser,
        note: Note,
        status: AnalysisStatus,
        output: AnalysisOutput | None,
        verification: VerificationReport | None,
        failure: AnalysisFailure | None,
        latency_ms: int,
        result: ProviderResult,
    ) -> Analysis:
        return Analysis(
            analysis_id=new_id(),
            note_id=note.note_id,
            owner_uid=caller.uid,
            content_hash=note.content_hash,
            status=status,
            provider=ProviderName(self._provider.name),
            model_id=result.model_id,
            prompt_version=self._prompt_version,
            output=output,
            verification=verification,
            failure=failure,
            latency_ms=latency_ms,
            token_usage=result.token_usage,
            cache_hit=False,
            created_at=datetime.now(timezone.utc),
        )
