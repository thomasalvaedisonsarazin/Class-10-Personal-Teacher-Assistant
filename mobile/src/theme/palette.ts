/**
 * Flat, calm, solid colour palette (PRP "MOBILE DESIGN SYSTEM").
 * No gradients anywhere — every token is a single solid hex colour.
 */
export const palette = {
  background: '#F7F5F0',
  surface: '#FFFFFF',
  textPrimary: '#1F2A37',
  textSecondary: '#556170',
  primary: '#3B6EA5',
  success: '#4F8A6B',
  warning: '#C08A3E',
  locked: '#B8BEC6',
  error: '#B3261E',
  onColor: '#FFFFFF',
  outline: '#D9D6CF',
  surfaceMuted: '#EFECE5',
} as const;

export type PaletteToken = keyof typeof palette;

/** Subject tile colours, in order: Maths, Science, Social, Tamil, English, extra. */
export const subjectColors = {
  maths: '#3B6EA5',
  science: '#4F8A6B',
  social: '#3E8C8C',
  tamil: '#7A6A9E',
  english: '#B0745A',
  extra: '#5C7A99',
} as const;

export type SubjectColorKey = keyof typeof subjectColors;

export const subjectColorList: readonly string[] = Object.values(subjectColors);

/** Deterministic tile colour for a subject (by known code, else by index). */
export function getSubjectColor(codeOrIndex: string | number): string {
  if (typeof codeOrIndex === 'string') {
    const key = codeOrIndex.toLowerCase();
    if (key in subjectColors) {
      return subjectColors[key as SubjectColorKey];
    }
    let hash = 0;
    for (let i = 0; i < key.length; i += 1) {
      hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
    }
    return subjectColorList[hash % subjectColorList.length];
  }
  const idx = Math.abs(Math.trunc(codeOrIndex)) % subjectColorList.length;
  return subjectColorList[idx];
}
