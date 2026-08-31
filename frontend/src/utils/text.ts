/**
 * Word counting, matching the backend's definition exactly.
 *
 * The backend counts `\S+`. If these two disagreed, the form would enable a
 * submit the API then rejects — so the definition is duplicated deliberately
 * and deliberately kept identical.
 */

export const NOTE_MIN_WORDS = 100;
export const NOTE_MAX_WORDS = 3000;
export const NOTE_MAX_CHARS = 40_000;

export function countWords(text: string): number {
  const matches = text.match(/\S+/g);
  return matches === null ? 0 : matches.length;
}

export type NoteLengthState = 'too-short' | 'valid' | 'too-long';

export function noteLengthState(text: string): NoteLengthState {
  const words = countWords(text);

  if (words < NOTE_MIN_WORDS) {
    return 'too-short';
  }
  if (words > NOTE_MAX_WORDS || text.length > NOTE_MAX_CHARS) {
    return 'too-long';
  }
  return 'valid';
}

export function formatDateTime(isoString: string): string {
  return new Date(isoString).toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

export function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, { dateStyle: 'medium' });
}
