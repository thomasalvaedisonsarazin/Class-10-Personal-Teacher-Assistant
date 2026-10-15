import {
  NotoSans_400Regular,
  NotoSans_500Medium,
  NotoSans_700Bold,
} from '@expo-google-fonts/noto-sans';
import {
  NotoSansTamil_400Regular,
  NotoSansTamil_500Medium,
  NotoSansTamil_700Bold,
} from '@expo-google-fonts/noto-sans-tamil';
import { MD3LightTheme, configureFonts, useTheme } from 'react-native-paper';
import type { MD3Theme } from 'react-native-paper';

import type { Medium } from '@/types/api';

import { palette, subjectColors } from './palette';

export { palette, subjectColors, getSubjectColor, safeTileColor } from './palette';

export const spacing = {
  xxs: 2,
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  pill: 999,
} as const;

/** Minimum touch target in dp (PRP: >= 48dp). */
export const MIN_TOUCH_TARGET = 48;

/** Subtle transition durations (ms). No heavy animation on lesson/quiz screens. */
export const motion = {
  fast: 120,
  normal: 200,
} as const;

/** Font assets to load with expo-font `useFonts`. */
export const fontAssets = {
  NotoSans_400Regular,
  NotoSans_500Medium,
  NotoSans_700Bold,
  NotoSansTamil_400Regular,
  NotoSansTamil_500Medium,
  NotoSansTamil_700Bold,
};

interface FontFamilies {
  regular: string;
  medium: string;
  bold: string;
}

export const fontFamilies: Record<Medium, FontFamilies> = {
  en: {
    regular: 'NotoSans_400Regular',
    medium: 'NotoSans_500Medium',
    bold: 'NotoSans_700Bold',
  },
  ta: {
    regular: 'NotoSansTamil_400Regular',
    medium: 'NotoSansTamil_500Medium',
    bold: 'NotoSansTamil_700Bold',
  },
};

export interface AppThemeExtras {
  palette: typeof palette;
  subjectColors: typeof subjectColors;
  spacing: typeof spacing;
  radius: typeof radius;
  motion: typeof motion;
  fontFamilies: FontFamilies;
  minTouchTarget: number;
}

export type AppTheme = MD3Theme & AppThemeExtras;

function buildFonts(families: FontFamilies): MD3Theme['fonts'] {
  const base = configureFonts({ config: { fontFamily: families.regular } });
  return {
    ...base,
    titleLarge: { ...base.titleLarge, fontFamily: families.bold },
    titleMedium: { ...base.titleMedium, fontFamily: families.medium },
    titleSmall: { ...base.titleSmall, fontFamily: families.medium },
    headlineLarge: { ...base.headlineLarge, fontFamily: families.bold },
    headlineMedium: { ...base.headlineMedium, fontFamily: families.bold },
    headlineSmall: { ...base.headlineSmall, fontFamily: families.bold },
    displaySmall: { ...base.displaySmall, fontFamily: families.bold },
    labelLarge: { ...base.labelLarge, fontFamily: families.medium },
    labelMedium: { ...base.labelMedium, fontFamily: families.medium },
    labelSmall: { ...base.labelSmall, fontFamily: families.medium },
  };
}

/** Build the flat MD3 theme for the given study medium (font family differs for Tamil). */
export function createAppTheme(medium: Medium = 'en'): AppTheme {
  const families = fontFamilies[medium];
  return {
    ...MD3LightTheme,
    dark: false,
    roundness: 3,
    fonts: buildFonts(families),
    colors: {
      ...MD3LightTheme.colors,
      primary: palette.primary,
      onPrimary: palette.onColor,
      primaryContainer: '#DCE6F2',
      onPrimaryContainer: '#14304F',
      secondary: palette.success,
      onSecondary: palette.onColor,
      secondaryContainer: '#DCEBE2',
      onSecondaryContainer: '#1E3A2B',
      tertiary: palette.warning,
      // White on #C08A3E is only 3.0:1 (large-text AA), so use dark slate text.
      onTertiary: palette.textPrimary,
      tertiaryContainer: '#F4E6D2',
      onTertiaryContainer: '#4A3210',
      error: palette.error,
      onError: palette.onColor,
      background: palette.background,
      onBackground: palette.textPrimary,
      surface: palette.surface,
      onSurface: palette.textPrimary,
      surfaceVariant: palette.surfaceMuted,
      onSurfaceVariant: palette.textSecondary,
      outline: palette.outline,
      outlineVariant: palette.outline,
      surfaceDisabled: 'rgba(31, 42, 55, 0.12)',
      onSurfaceDisabled: 'rgba(31, 42, 55, 0.38)',
      elevation: {
        level0: 'transparent',
        level1: palette.surface,
        level2: palette.surface,
        level3: palette.surface,
        level4: palette.surface,
        level5: palette.surface,
      },
    },
    palette,
    subjectColors,
    spacing,
    radius,
    motion,
    fontFamilies: families,
    minTouchTarget: MIN_TOUCH_TARGET,
  };
}

export const appTheme: AppTheme = createAppTheme('en');

/** Typed access to the app theme inside components. */
export const useAppTheme = (): AppTheme => useTheme<AppTheme>();
