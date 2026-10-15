import { describe, expect, it } from '@jest/globals';

import { relativeDay } from '@/lib/time';

describe('relativeDay', () => {
  const now = new Date(2026, 9, 15, 18, 0, 0);

  it('describes recent days in plain words', () => {
    expect(relativeDay(new Date(2026, 9, 15, 8, 0).toISOString(), now)).toBe('today');
    expect(relativeDay(new Date(2026, 9, 14, 23, 0).toISOString(), now)).toBe('yesterday');
    expect(relativeDay(new Date(2026, 9, 12, 9, 0).toISOString(), now)).toBe('3 days ago');
  });

  it('handles missing or invalid dates', () => {
    expect(relativeDay(null, now)).toBe('never');
    expect(relativeDay('not-a-date', now)).toBe('never');
  });
});
