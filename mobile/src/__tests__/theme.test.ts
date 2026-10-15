import { describe, expect, it } from '@jest/globals';

import { appTheme, createAppTheme, MIN_TOUCH_TARGET, palette, subjectColors } from '@/theme';
import { getSubjectColor } from '@/theme/palette';

function collectStrings(value: unknown, out: string[] = []): string[] {
  if (typeof value === 'string') {
    out.push(value);
  } else if (Array.isArray(value)) {
    value.forEach((v) => collectStrings(v, out));
  } else if (value !== null && typeof value === 'object') {
    Object.values(value as Record<string, unknown>).forEach((v) => collectStrings(v, out));
  }
  return out;
}

function relativeLuminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastWithWhite(hex: string): number {
  return 1.05 / (relativeLuminance(hex) + 0.05);
}

describe('palette', () => {
  it('matches the PRP design system exactly', () => {
    expect(palette.background).toBe('#F7F5F0');
    expect(palette.surface).toBe('#FFFFFF');
    expect(palette.textPrimary).toBe('#1F2A37');
    expect(palette.textSecondary).toBe('#556170');
    expect(palette.primary).toBe('#3B6EA5');
    expect(palette.success).toBe('#4F8A6B');
    expect(palette.warning).toBe('#C08A3E');
    expect(palette.locked).toBe('#B8BEC6');
  });

  it('has the six subject tile colours in order', () => {
    expect(Object.values(subjectColors)).toEqual([
      '#3B6EA5',
      '#4F8A6B',
      '#3E8C8C',
      '#7A6A9E',
      '#B0745A',
      '#5C7A99',
    ]);
  });

  it('uses only solid hex colours for palette tokens', () => {
    collectStrings({ palette, subjectColors }).forEach((value) => {
      expect(value).toMatch(/^#[0-9A-F]{6}$/);
    });
  });

  it('gives white tile text at least WCAG AA large-text contrast (3:1)', () => {
    Object.values(subjectColors).forEach((hex) => {
      expect(contrastWithWhite(hex)).toBeGreaterThanOrEqual(3);
    });
  });

  it('maps subjects to stable tile colours', () => {
    expect(getSubjectColor('maths')).toBe(subjectColors.maths);
    expect(getSubjectColor(7)).toBe(subjectColors.science);
    expect(getSubjectColor('unknown-subject')).toBe(getSubjectColor('unknown-subject'));
  });
});

describe('theme', () => {
  it('contains no gradient tokens anywhere', () => {
    [appTheme, createAppTheme('ta')].forEach((theme) => {
      collectStrings(theme).forEach((value) => {
        expect(value.toLowerCase()).not.toContain('gradient');
      });
    });
  });

  it('maps palette onto MD3 colours', () => {
    expect(appTheme.colors.primary).toBe(palette.primary);
    expect(appTheme.colors.background).toBe(palette.background);
    expect(appTheme.colors.surface).toBe(palette.surface);
    expect(appTheme.colors.onSurface).toBe(palette.textPrimary);
    expect(appTheme.dark).toBe(false);
  });

  it('uses Noto Sans for English and Noto Sans Tamil for Tamil medium', () => {
    expect(appTheme.fonts.bodyLarge.fontFamily).toBe('NotoSans_400Regular');
    expect(createAppTheme('ta').fonts.bodyLarge.fontFamily).toBe('NotoSansTamil_400Regular');
  });

  it('enforces a 48dp minimum touch target', () => {
    expect(MIN_TOUCH_TARGET).toBeGreaterThanOrEqual(48);
    expect(appTheme.minTouchTarget).toBe(48);
  });
});
