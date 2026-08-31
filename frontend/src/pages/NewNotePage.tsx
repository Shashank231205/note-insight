import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';

import { ErrorState, Spinner } from '@/components/common/Feedback';
import { ApiError } from '@/services/apiClient';
import { createNote, runAnalysis } from '@/services/notesApi';
import {
  NOTE_MAX_CHARS,
  NOTE_MAX_WORDS,
  NOTE_MIN_WORDS,
  countWords,
  noteLengthState,
} from '@/utils/text';

import styles from './NewNotePage.module.css';

type Phase = 'editing' | 'saving' | 'analyzing';

const PSEUDONYM_MAX_LENGTH = 64;

export function NewNotePage(): JSX.Element {
  const navigate = useNavigate();
  const [content, setContent] = useState('');
  const [pseudonym, setPseudonym] = useState('');
  const [visitDate, setVisitDate] = useState('');
  const [phase, setPhase] = useState<Phase>('editing');
  const [error, setError] = useState<ApiError | null>(null);

  const words = countWords(content);
  const lengthState = noteLengthState(content);
  const canSubmit = lengthState === 'valid' && phase === 'editing';

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (!canSubmit) {
      return;
    }

    setError(null);
    setPhase('saving');

    // Two calls, presented as one action. The note is persisted first so a
    // provider outage cannot lose what the clinician typed.
    void createNote({
      content,
      pseudonym: pseudonym.trim() === '' ? null : pseudonym.trim(),
      visit_date: visitDate === '' ? null : visitDate,
    })
      .then(async (note) => {
        setPhase('analyzing');
        try {
          await runAnalysis(note.note_id);
        } catch (analysisError: unknown) {
          // The note is saved. The detail page offers a retry, so an analysis
          // failure here must not discard the clinician's work.
          if (!(analysisError instanceof ApiError)) {
            throw analysisError;
          }
        }
        void navigate(`/notes/${note.note_id}`);
      })
      .catch((caught: unknown) => {
        setError(
          caught instanceof ApiError
            ? caught
            : new ApiError({
                code: 'UNEXPECTED',
                message: 'Something went wrong while saving the note.',
                status: 0,
                details: null,
                requestId: null,
                retryAfterSeconds: null,
              }),
        );
        setPhase('editing');
      });
  };

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <h1 className={styles.title}>Analyze a clinical note</h1>
        <p className={styles.subtitle}>
          Paste the encounter note. You will get back the conditions it
          documents, the evidence for each, and what a coder would query.
        </p>
      </header>

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.metadata}>
          <label className={styles.field}>
            <span className={styles.label}>Patient pseudonym</span>
            <input
              type="text"
              maxLength={PSEUDONYM_MAX_LENGTH}
              placeholder="e.g. PT-014"
              value={pseudonym}
              onChange={(event) => {
                setPseudonym(event.target.value);
              }}
            />
            <span className={styles.hint}>
              An internal reference only. Never a name, MRN or date of birth.
            </span>
          </label>

          <label className={styles.field}>
            <span className={styles.label}>Visit date</span>
            <input
              type="date"
              value={visitDate}
              max={new Date().toISOString().slice(0, 10)}
              onChange={(event) => {
                setVisitDate(event.target.value);
              }}
            />
            <span className={styles.hint}>Optional.</span>
          </label>
        </div>

        <label className={styles.field}>
          <span className={styles.label}>Clinical note</span>
          <textarea
            className={styles.textarea}
            rows={18}
            value={content}
            placeholder="Paste the free-text encounter note here…"
            onChange={(event) => {
              setContent(event.target.value);
            }}
            aria-describedby="note-counter"
          />
        </label>

        <div className={styles.footer}>
          <p
            id="note-counter"
            className={
              lengthState === 'valid' ? styles.counterValid : styles.counterInvalid
            }
            aria-live="polite"
          >
            {lengthState === 'too-short' &&
              `${String(words)} / ${String(NOTE_MIN_WORDS)} words minimum`}
            {lengthState === 'valid' &&
              `${String(words)} words — within the ${String(NOTE_MIN_WORDS)}–${String(NOTE_MAX_WORDS)} word range`}
            {lengthState === 'too-long' &&
              (content.length > NOTE_MAX_CHARS
                ? `${String(content.length)} characters — the limit is ${String(NOTE_MAX_CHARS)}`
                : `${String(words)} words — the maximum is ${String(NOTE_MAX_WORDS)}`)}
          </p>

          <button type="submit" className={styles.submit} disabled={!canSubmit}>
            {phase === 'editing' && 'Analyze note'}
            {phase === 'saving' && <Spinner label="Saving note…" />}
            {phase === 'analyzing' && <Spinner label="Analyzing — this takes a few seconds…" />}
          </button>
        </div>

        {error !== null && (
          <ErrorState
            title="The note could not be saved"
            message={error.message}
            requestId={error.requestId}
          />
        )}
      </form>
    </div>
  );
}
