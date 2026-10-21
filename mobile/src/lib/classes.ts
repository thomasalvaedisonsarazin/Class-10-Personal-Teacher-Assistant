/** Board + class picker helpers (each server "board" is one class of a board). */

import type { Board } from '@/types/api';

/** 11th / 12th: language + English + 4 group subjects (the server checks the same). */
export const SUBJECTS_TO_CHOOSE = 6;

/** Whether one more subject may be ticked. */
export function canTickMore(selected: readonly number[]): boolean {
  return selected.length < SUBJECTS_TO_CHOOSE;
}

const FAMILY_LABELS: Record<string, string> = {
  TN_STATE: 'Tamil Nadu State Board',
  CBSE: 'CBSE',
};

export function familyLabel(family: string): string {
  return FAMILY_LABELS[family] ?? family;
}

/** "Class 10", "Class 11 (+1)", "Class 12 (+2)". */
export function classLabel(grade: number): string {
  if (grade === 11) return 'Class 11 (+1)';
  if (grade === 12) return 'Class 12 (+2)';
  return `Class ${grade}`;
}

/** Boards (families) in the order the server lists them, without repeats. */
export function boardFamilies(boards: readonly Board[]): string[] {
  return [...new Set(boards.map((board) => board.family))];
}

/** The classes of one board, lowest first. */
export function classesOf(boards: readonly Board[], family: string): Board[] {
  return boards.filter((board) => board.family === family).sort((a, b) => a.grade - b.grade);
}
