/**
 * Renders the note with verified evidence spans highlighted in place.
 *
 * The offsets come from the backend's evidence verifier, which recorded where
 * each quote was actually found. Segments are built as React elements from
 * those offsets — never as an HTML string — so note text is always a text node
 * and `dangerouslySetInnerHTML` never appears.
 */

import { useMemo } from 'react';

import type { ConditionResponse, QuoteVerificationResponse } from '@/types/api';

import styles from './NoteHighlighter.module.css';

interface Segment {
  readonly key: string;
  readonly text: string;
  readonly conditionId: string | null;
}

function buildSegments(
  content: string,
  verifications: readonly QuoteVerificationResponse[],
): readonly Segment[] {
  const spans = verifications
    .filter(
      (result): result is QuoteVerificationResponse & { match_offset: number; match_length: number } =>
        result.match_offset !== null && result.match_length !== null && result.match_length > 0,
    )
    .map((result) => ({
      start: result.match_offset,
      end: result.match_offset + result.match_length,
      conditionId: result.condition_id,
    }))
    .sort((left, right) => left.start - right.start);

  const segments: Segment[] = [];
  let cursor = 0;

  for (const span of spans) {
    // Two conditions can cite overlapping spans; the first one wins rather
    // than producing interleaved, unreadable markup.
    if (span.start < cursor) {
      continue;
    }
    if (span.start > cursor) {
      segments.push({
        key: `plain-${String(cursor)}`,
        text: content.slice(cursor, span.start),
        conditionId: null,
      });
    }
    segments.push({
      key: `mark-${span.conditionId}`,
      text: content.slice(span.start, span.end),
      conditionId: span.conditionId,
    });
    cursor = span.end;
  }

  if (cursor < content.length) {
    segments.push({
      key: `plain-${String(cursor)}`,
      text: content.slice(cursor),
      conditionId: null,
    });
  }

  return segments;
}

export function NoteHighlighter({
  content,
  verifications,
  conditions,
  activeConditionId,
}: {
  content: string;
  verifications: readonly QuoteVerificationResponse[];
  conditions: readonly ConditionResponse[];
  activeConditionId: string | null;
}): JSX.Element {
  const segments = useMemo(
    () => buildSegments(content, verifications),
    [content, verifications],
  );

  const nameById = useMemo(
    () => new Map(conditions.map((condition) => [condition.condition_id, condition.name])),
    [conditions],
  );

  return (
    <div className={styles.note}>
      {segments.map((segment) =>
        segment.conditionId === null ? (
          <span key={segment.key}>{segment.text}</span>
        ) : (
          <mark
            key={segment.key}
            className={
              activeConditionId === segment.conditionId ? styles.markActive : styles.mark
            }
            title={`Evidence for ${nameById.get(segment.conditionId) ?? 'a condition'}`}
          >
            {segment.text}
          </mark>
        ),
      )}
    </div>
  );
}
