import { DocumentationStatusBadge, EvidenceBadge } from '@/components/common/Badge';
import type { ConditionEdits, DraftCondition } from '@/hooks/useReviewDraft';
import type {
  ConditionResponse,
  DocumentationStatus,
  QuoteVerificationResponse,
  ReviewAction,
} from '@/types/api';

import styles from './ConditionEditor.module.css';

const STATUS_OPTIONS: readonly { value: DocumentationStatus; label: string }[] = [
  { value: 'well_documented', label: 'Well documented' },
  { value: 'ambiguous', label: 'Ambiguous' },
  { value: 'mentioned_without_plan', label: 'No assessment or plan' },
];

const ACTION_LABELS: Record<ReviewAction, string> = {
  accepted: 'Unchanged',
  edited: 'Edited',
  rejected: 'Rejected',
  added: 'Added by you',
};

/**
 * One condition, editable, with the model's original value shown beside any
 * field the clinician changed. Seeing both at once is what makes the
 * correction deliberate rather than accidental.
 */
export function ConditionEditor({
  draft,
  original,
  verification,
  action,
  onChange,
  onRemove,
}: {
  draft: DraftCondition;
  original: ConditionResponse | undefined;
  verification: QuoteVerificationResponse | undefined;
  action: ReviewAction;
  onChange: (edits: ConditionEdits) => void;
  onRemove: (() => void) | undefined;
}): JSX.Element {
  const nameChanged = original !== undefined && draft.name !== original.name;
  const statusChanged =
    original !== undefined && draft.documentationStatus !== original.documentation_status;
  const codeChanged =
    original !== undefined && draft.icd10Code !== (original.icd10_code ?? '');

  return (
    <article className={draft.isRejected ? styles.cardRejected : styles.card}>
      <header className={styles.header}>
        <span className={`${styles.action} ${styles[`action_${action}`] ?? ''}`}>
          {ACTION_LABELS[action]}
        </span>
        {verification !== undefined && <EvidenceBadge status={verification.status} />}
      </header>

      <label className={styles.field}>
        <span className={styles.label}>Condition</span>
        <input
          type="text"
          value={draft.name}
          disabled={draft.isRejected}
          onChange={(event) => {
            onChange({ name: event.target.value });
          }}
        />
        {nameChanged && <span className={styles.was}>Model said: {original.name}</span>}
      </label>

      {draft.origin === 'ai' && (
        <div className={styles.evidence}>
          <span className={styles.label}>Evidence quoted from the note</span>
          <blockquote className={styles.quote}>{draft.evidenceQuote}</blockquote>
          {verification?.status === 'not_found' && (
            <p className={styles.warning}>
              This quote was not found in the note. Reject the condition if the
              model invented it.
            </p>
          )}
        </div>
      )}

      <div className={styles.row}>
        <label className={styles.field}>
          <span className={styles.label}>Documentation status</span>
          <select
            value={draft.documentationStatus}
            disabled={draft.isRejected}
            onChange={(event) => {
              onChange({
                documentationStatus: event.target.value as DocumentationStatus,
              });
            }}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {statusChanged && (
            <span className={styles.was}>
              Model said: <DocumentationStatusBadge status={original.documentation_status} />
            </span>
          )}
        </label>

        <label className={styles.field}>
          <span className={styles.label}>ICD-10 code</span>
          <input
            type="text"
            value={draft.icd10Code}
            placeholder="None"
            disabled={draft.isRejected}
            onChange={(event) => {
              onChange({ icd10Code: event.target.value });
            }}
          />
          {codeChanged && (
            <span className={styles.was}>
              Model said: {original.icd10_code ?? 'no code'}
            </span>
          )}
        </label>
      </div>

      <footer className={styles.footer}>
        {draft.origin === 'ai' ? (
          <label className={styles.reject}>
            <input
              type="checkbox"
              checked={draft.isRejected}
              onChange={(event) => {
                onChange({ isRejected: event.target.checked });
              }}
            />
            <span>This condition is incorrect</span>
          </label>
        ) : (
          <button
            type="button"
            className={styles.remove}
            onClick={() => {
              onRemove?.();
            }}
          >
            Remove
          </button>
        )}
      </footer>

      {draft.isRejected && (
        <label className={styles.field}>
          <span className={styles.label}>Why is it incorrect?</span>
          <input
            type="text"
            value={draft.rejectionReason}
            placeholder="e.g. this is family history, not an active condition"
            onChange={(event) => {
              onChange({ rejectionReason: event.target.value });
            }}
          />
        </label>
      )}
    </article>
  );
}
