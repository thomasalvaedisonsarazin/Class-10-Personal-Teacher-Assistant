import { describe, expect, it } from '@jest/globals';

import { SUBJECTS_TO_CHOOSE, boardFamilies, canTickMore, classLabel, classesOf, familyLabel } from '@/lib/classes';
import type { Board } from '@/types/api';

const board = (id: number, family: string, grade: number): Board => ({
  id,
  code: `${family}_${grade}`,
  name: `${family} ${grade}`,
  family,
  grade,
  chooseSubjects: grade >= 11,
});

describe('class picker helpers', () => {
  const boards = [board(1, 'TN_STATE', 10), board(2, 'TN_STATE', 9), board(3, 'CBSE', 10), board(4, 'TN_STATE', 12)];

  it('lists each board once in server order', () => {
    expect(boardFamilies(boards)).toEqual(['TN_STATE', 'CBSE']);
  });

  it('lists the classes of a board lowest first', () => {
    expect(classesOf(boards, 'TN_STATE').map((b) => b.grade)).toEqual([9, 10, 12]);
  });

  it('labels boards and classes', () => {
    expect(familyLabel('TN_STATE')).toBe('Tamil Nadu State Board');
    expect(familyLabel('NEW')).toBe('NEW');
    expect(classLabel(9)).toBe('Class 9');
    expect(classLabel(12)).toBe('Class 12 (+2)');
  });
});

describe('subject group', () => {
  it('allows ticking up to six subjects', () => {
    expect(SUBJECTS_TO_CHOOSE).toBe(6);
    expect(canTickMore([1, 2, 3, 4, 5])).toBe(true);
    expect(canTickMore([1, 2, 3, 4, 5, 6])).toBe(false);
  });
});
