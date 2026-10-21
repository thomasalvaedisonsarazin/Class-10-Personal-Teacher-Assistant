import { describe, expect, it, jest } from '@jest/globals';

import { codeFromReferrer, formatRupees, normalizeReferralCode } from '@/lib/referral';

jest.mock('expo-application', () => ({ getInstallReferrerAsync: jest.fn() }));

describe('referral codes', () => {
  it('normalizes typed codes like the server', () => {
    expect(normalizeReferralCode(' stjo-se 7k2 ')).toBe('STJOSE7K2');
  });

  it('reads the code from a Play install referrer', () => {
    expect(codeFromReferrer('pta_ref=STJOSE7K2')).toBe('STJOSE7K2');
    expect(codeFromReferrer('utm_source=google-play&pta_ref=stjose7k2')).toBe('STJOSE7K2');
    expect(codeFromReferrer('utm_source=google-play&utm_medium=organic')).toBeNull();
    expect(codeFromReferrer('')).toBeNull();
    expect(codeFromReferrer(null)).toBeNull();
  });

  it('formats rupees in Indian style', () => {
    expect(formatRupees(1234.5)).toContain('1,234.5');
  });
});
