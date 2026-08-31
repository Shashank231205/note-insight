/**
 * The review editing state machine.
 *
 * Holds the clinician's working copy of an analysis. The AI's values are never
 * mutated here — they stay on the `analysis` object, and the draft is compared
 * against them to decide whether a condition counts as `accepted` or `edited`.
 * That comparison is the whole point of the feature, so it lives in one place.
 */

import { useCallback, useMemo, useState } from 'react';

import type {
  AnalysisResponse,
  ConditionResponse,
  DocumentationStatus,
  ReviewAction,
  ReviewedConditionResponse,
} from '@/types/api';

export interface DraftCondition {
  readonly conditionId: string;
  readonly origin: 'ai' | 'human';
  readonly name: string;
  readonly evidenceQuote: string;
  readonly documentationStatus: DocumentationStatus;
  readonly icd10Code: string;
  readonly isRejected: boolean;
  readonly rejectionReason: string;
}

export interface ConditionEdits {
  readonly name?: string;
  readonly documentationStatus?: DocumentationStatus;
  readonly icd10Code?: string;
  readonly isRejected?: boolean;
  readonly rejectionReason?: string;
}

function toDraft(condition: ConditionResponse): DraftCondition {
  return {
    conditionId: condition.condition_id,
    origin: 'ai',
    name: condition.name,
    evidenceQuote: condition.evidence_quote,
    documentationStatus: condition.documentation_status,
    icd10Code: condition.icd10_code ?? '',
    isRejected: false,
    rejectionReason: '',
  };
}

/** Restores a saved review so a returning clinician edits their own last version. */
function fromSavedReview(saved: ReviewedConditionResponse): DraftCondition {
  return {
    conditionId: saved.condition_id,
    origin: saved.origin,
    name: saved.name,
    evidenceQuote: saved.evidence_quote,
    documentationStatus: saved.documentation_status,
    icd10Code: saved.icd10_code ?? '',
    isRejected: saved.action === 'rejected',
    rejectionReason: saved.rejection_reason ?? '',
  };
}

function initialDraft(
  analysis: AnalysisResponse,
  savedConditions: readonly ReviewedConditionResponse[] | null,
): readonly DraftCondition[] {
  if (savedConditions !== null && savedConditions.length > 0) {
    return savedConditions.map(fromSavedReview);
  }
  return (analysis.output?.conditions ?? []).map(toDraft);
}

function resolveAction(
  draft: DraftCondition,
  original: ConditionResponse | undefined,
): ReviewAction {
  if (draft.origin === 'human') {
    return 'added';
  }
  if (draft.isRejected) {
    return 'rejected';
  }
  if (original === undefined) {
    return 'accepted';
  }

  const isUnchanged =
    draft.name === original.name &&
    draft.documentationStatus === original.documentation_status &&
    draft.icd10Code === (original.icd10_code ?? '');

  return isUnchanged ? 'accepted' : 'edited';
}

export interface ReviewDraft {
  readonly conditions: readonly DraftCondition[];
  readonly reviewerNote: string;
  readonly setReviewerNote: (value: string) => void;
  readonly updateCondition: (conditionId: string, edits: ConditionEdits) => void;
  readonly addCondition: (condition: {
    name: string;
    documentationStatus: DocumentationStatus;
    icd10Code: string;
  }) => void;
  readonly removeAddedCondition: (conditionId: string) => void;
  readonly actionFor: (conditionId: string) => ReviewAction;
  readonly changedCount: number;
  readonly blockingIssue: string | null;
  readonly toPayload: () => {
    reviewed_conditions: readonly unknown[];
    reviewed_gaps: readonly unknown[];
    reviewer_note: string | null;
  };
}

export function useReviewDraft(
  analysis: AnalysisResponse,
  savedConditions: readonly ReviewedConditionResponse[] | null,
): ReviewDraft {
  const [conditions, setConditions] = useState<readonly DraftCondition[]>(() =>
    initialDraft(analysis, savedConditions),
  );
  const [reviewerNote, setReviewerNote] = useState('');

  const originalById = useMemo(
    () =>
      new Map(
        (analysis.output?.conditions ?? []).map((condition) => [
          condition.condition_id,
          condition,
        ]),
      ),
    [analysis],
  );

  const updateCondition = useCallback((conditionId: string, edits: ConditionEdits) => {
    setConditions((current) =>
      current.map((condition) =>
        condition.conditionId === conditionId ? { ...condition, ...edits } : condition,
      ),
    );
  }, []);

  const addCondition = useCallback(
    (condition: {
      name: string;
      documentationStatus: DocumentationStatus;
      icd10Code: string;
    }) => {
      setConditions((current) => [
        ...current,
        {
          conditionId: `human-${String(Date.now())}-${String(current.length)}`,
          origin: 'human',
          name: condition.name,
          evidenceQuote: '',
          documentationStatus: condition.documentationStatus,
          icd10Code: condition.icd10Code,
          isRejected: false,
          rejectionReason: '',
        },
      ]);
    },
    [],
  );

  const removeAddedCondition = useCallback((conditionId: string) => {
    setConditions((current) =>
      current.filter(
        (condition) => !(condition.conditionId === conditionId && condition.origin === 'human'),
      ),
    );
  }, []);

  const actionFor = useCallback(
    (conditionId: string): ReviewAction => {
      const draft = conditions.find((item) => item.conditionId === conditionId);
      if (draft === undefined) {
        return 'accepted';
      }
      return resolveAction(draft, originalById.get(conditionId));
    },
    [conditions, originalById],
  );

  const changedCount = useMemo(
    () =>
      conditions.filter((condition) => {
        const action = resolveAction(condition, originalById.get(condition.conditionId));
        return action !== 'accepted';
      }).length,
    [conditions, originalById],
  );

  // The backend refuses a rejection with no reason. Surfacing it here means the
  // clinician sees why submit is disabled instead of meeting a 400.
  const blockingIssue = useMemo(() => {
    const missingReason = conditions.find(
      (condition) => condition.isRejected && condition.rejectionReason.trim() === '',
    );
    if (missingReason !== undefined) {
      return `Give a reason for rejecting "${missingReason.name}".`;
    }

    const unnamed = conditions.find((condition) => condition.name.trim() === '');
    if (unnamed !== undefined) {
      return 'Every condition needs a name.';
    }
    return null;
  }, [conditions]);

  const toPayload = useCallback(() => {
    return {
      reviewed_conditions: conditions.map((condition) => ({
        condition_id: condition.conditionId,
        origin: condition.origin,
        action: resolveAction(condition, originalById.get(condition.conditionId)),
        name: condition.name.trim(),
        evidence_quote: condition.evidenceQuote,
        documentation_status: condition.documentationStatus,
        icd10_code: condition.icd10Code.trim() === '' ? null : condition.icd10Code.trim(),
        rejection_reason: condition.isRejected ? condition.rejectionReason.trim() : null,
      })),
      reviewed_gaps: [],
      reviewer_note: reviewerNote.trim() === '' ? null : reviewerNote.trim(),
    };
  }, [conditions, originalById, reviewerNote]);

  return {
    conditions,
    reviewerNote,
    setReviewerNote,
    updateCondition,
    addCondition,
    removeAddedCondition,
    actionFor,
    changedCount,
    blockingIssue,
    toPayload,
  };
}
