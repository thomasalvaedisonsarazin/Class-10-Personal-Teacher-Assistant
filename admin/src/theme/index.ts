import { createSystem, defaultConfig, defineConfig } from '@chakra-ui/react';

/**
 * Flat, calm palette. Solid colours only - no gradients anywhere in the admin app.
 * `danger` is a muted terracotta used for errors and destructive actions.
 */
export const palette = {
  background: '#F7F5F0',
  surface: '#FFFFFF',
  text: '#1F2A37',
  textMuted: '#556170',
  primary: '#3B6EA5',
  primaryHover: '#335F8F',
  primarySubtle: '#E8EEF5',
  success: '#4F8A6B',
  successSubtle: '#E7F0EB',
  warning: '#C08A3E',
  warningSubtle: '#F6EEE2',
  danger: '#B05A4F',
  dangerSubtle: '#F5E8E6',
  muted: '#B8BEC6',
  border: '#E4E1DA',
} as const;

const config = defineConfig({
  globalCss: {
    'html, body': {
      bg: 'bg',
      color: 'fg',
    },
  },
  theme: {
    tokens: {
      fonts: {
        heading: { value: "system-ui, 'Segoe UI', Roboto, sans-serif" },
        body: { value: "system-ui, 'Segoe UI', Roboto, sans-serif" },
      },
    },
    semanticTokens: {
      colors: {
        bg: { DEFAULT: { value: palette.background } },
        surface: { value: palette.surface },
        fg: { DEFAULT: { value: palette.text } },
        fgMuted: { value: palette.textMuted },
        border: { DEFAULT: { value: palette.border } },
        primary: {
          DEFAULT: { value: palette.primary },
          hover: { value: palette.primaryHover },
          subtle: { value: palette.primarySubtle },
          contrast: { value: palette.surface },
        },
        success: {
          DEFAULT: { value: palette.success },
          subtle: { value: palette.successSubtle },
        },
        warning: {
          DEFAULT: { value: palette.warning },
          subtle: { value: palette.warningSubtle },
        },
        danger: {
          DEFAULT: { value: palette.danger },
          subtle: { value: palette.dangerSubtle },
        },
        muted: { value: palette.muted },
      },
    },
  },
});

export const system = createSystem(defaultConfig, config);
