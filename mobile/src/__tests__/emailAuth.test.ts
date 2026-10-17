import { describe, expect, it } from '@jest/globals';

import { cleanCode, isValidCode, isValidEmail, normalizeEmail, passwordProblem } from '@/lib/emailAuth';

describe('email sign-in checks', () => {
  it('accepts normal emails and trims/lowercases them', () => {
    expect(isValidEmail(' Kavya@Example.com ')).toBe(true);
    expect(normalizeEmail(' Kavya@Example.com ')).toBe('kavya@example.com');
    expect(isValidEmail('kavya@')).toBe(false);
    expect(isValidEmail('no spaces@example.com')).toBe(false);
  });

  it('keeps only six digits in the code field', () => {
    expect(cleanCode('12 34-5678')).toBe('123456');
    expect(isValidCode('123456')).toBe(true);
    expect(isValidCode('12345')).toBe(false);
  });

  it('explains weak passwords', () => {
    expect(passwordProblem('short')).toMatch(/at least 8/);
    expect(passwordProblem(' padded-pass')).toMatch(/spaces/);
    expect(passwordProblem('aaaaaaaaaa')).toMatch(/stronger/);
    expect(passwordProblem('x'.repeat(73))).toMatch(/too long/);
    expect(passwordProblem('mango-tree-42')).toBeNull();
  });
});
