import { useMemo, useState } from 'react';

import { ErrorState, Spinner } from '@/components/common/Feedback';
import { ConditionEditor } from '@/components/review/ConditionEditor';
import { useReviewDraft } from '@/hooks/useReviewDraft';
import { ApiError } from '@/services/apiClient';
import { submitReview } from '@/services/reviewsApi';
import type {
  AnalysisResponse,
  DocumentationStatus,
  ReviewResponse,
} from '@/types/api';

import styles from './ReviewPanel.module.css';

function AddConditionForm({
  onAdd,
}: {
  onAdd: (condition: {
    name: string;
    documentationStatus: DocumentationStatus;
    icd10Code: string;
  }) => void;
}): JSX.Element {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');

  const handleAdd = (): void => {
    if (name.trim() === '') {
      return;
    }
    onAdd({
      name: name.trim(),
      documentationStatus: 'mentioned_without_plan',
      icd10Code: code.trim(),
    });
    setName('');
    setCode('');
  };

  return (
    <div className={styles.addForm}>
      <span className={styles.addTitle}>Add a condition the model missed</span>
      <div className={styles.addRow}>
        <input
          type="text"
          placeholder="Condition name"
          value={name}
          onChange={(event) => {
            setName(event.target.value);
          }}
        />
        <input
          type="text"
          placeholder="ICD-10 (optional)"
          value={code}
          onChange={(event) => {
            setCode(event.target.value);
          }}
        />
        <button type="button" onClick={handleAdd} disabled={name.trim() === ''}>
          Add
        </button>
      </div>
    </div>
  );
}

export function ReviewPanel({
  analysis,
  savedReview,
  onSubmitted,
}: {
  analysis: AnalysisResponse;
  savedReview: ReviewResponse | null;
  onSubmitted: () => void;
}): JSX.Element {
  const draft = useReviewDraft(analysis, savedReview?.reviewed_conditions ?? null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

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

  const verificationById = useMemo(
    () =>
      new Map(
        (analysis.verification?.quote_results ?? []).map((result) => [
          result.condition_id,
          result,
        ]),
      ),
    [analysis],
  );

  const handleSubmit = (): void => {
    if (draft.blockingIssue !== null) {
      return;
    }
    setError(null);
    setIsSubmitting(true);

    void submitReview(analysis.analysis_id, draft.toPayload())
      .then(() => {
        onSubmitted();
      })
      .catch((caught: unknown) => {
        if (caught instanceof ApiError) {
          setError(caught);
        }
      })
      .finally(() => {
        setIsSubmitting(false);
      });
  };

  return (
    <section className={styles.panel}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>Review</h2>
          <p className={styles.subtitle}>
            The machine produced a draft. Correct anything it got wrong — the
            original stays on record either way.
          </p>
        </div>
        {savedReview !== null && (
          <span className={styles.version}>Saved version {savedReview.version}</span>
        )}
      </header>

      <div className={styles.conditions}>
        {draft.conditions.map((condition) => (
          <ConditionEditor
            key={condition.conditionId}
            draft={condition}
            original={originalById.get(condition.conditionId)}
            verification={verificationById.get(condition.conditionId)}
            action={draft.actionFor(condition.conditionId)}
            onChange={(edits) => {
              draft.updateCondition(condition.conditionId, edits);
            }}
            onRemove={
              condition.origin === 'human'
                ? () => {
                    draft.removeAddedCondition(condition.conditionId);
                  }
                : undefined
            }
          />
        ))}
      </div>

      <AddConditionForm onAdd={draft.addCondition} />

      <label className={styles.noteField}>
        <span className={styles.label}>Reviewer note (optional)</span>
        <textarea
          rows={3}
          value={draft.reviewerNote}
          placeholder="Anything a colleague should know about this review."
          onChange={(event) => {
            draft.setReviewerNote(event.target.value);
          }}
        />
      </label>

      {error !== null && (
        <ErrorState
          title={
            error.status === 409
              ? 'This analysis is out of date'
              : 'The review could not be saved'
          }
          message={
            error.status === 409
              ? 'A newer analysis exists for this note. Reload the page before reviewing.'
              : error.message
          }
          requestId={error.requestId}
        />
      )}

      <footer className={styles.footer}>
        <span className={styles.changeCount}>
          {draft.changedCount === 0
            ? 'No changes to the model output'
            : `${String(draft.changedCount)} ${draft.changedCount === 1 ? 'change' : 'changes'} to the model output`}
        </span>

        <div className={styles.actions}>
          {draft.blockingIssue !== null && (
            <span className={styles.blocking}>{draft.blockingIssue}</span>
          )}
          <button
            type="button"
            className={styles.submit}
            disabled={isSubmitting || draft.blockingIssue !== null}
            onClick={handleSubmit}
          >
            {isSubmitting ? <Spinner label="Saving…" /> : 'Save review'}
          </button>
        </div>
      </footer>
    </section>
  );
}
