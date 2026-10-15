import { StyleSheet } from 'react-native';
import { SegmentedButtons } from 'react-native-paper';

import type { LessonLanguage } from '@/types/api';

export const LANGUAGE_CHOICES: { value: LessonLanguage; label: string; spoken: string }[] = [
  { value: 'en', label: 'English', spoken: 'English' },
  { value: 'ta', label: 'தமிழ்', spoken: 'Tamil' },
  { value: 'tanglish', label: 'Tanglish', spoken: 'Tanglish' },
];

export interface LanguageToggleProps {
  value: LessonLanguage | null;
  disabled?: boolean;
  onChange: (language: LessonLanguage) => void;
}

/** Explain this lesson in English, Tamil or Tanglish (independent of the textbook medium). */
export function LanguageToggle({ value, disabled = false, onChange }: LanguageToggleProps) {
  return (
    <SegmentedButtons
      value={value ?? ''}
      onValueChange={(next) => {
        const choice = LANGUAGE_CHOICES.find((c) => c.value === next);
        if (choice && choice.value !== value) onChange(choice.value);
      }}
      buttons={LANGUAGE_CHOICES.map((c) => ({
        value: c.value,
        label: c.label,
        disabled,
        accessibilityLabel: `Explain in ${c.spoken}`,
        testID: `language-${c.value}`,
      }))}
      style={styles.toggle}
    />
  );
}

const styles = StyleSheet.create({
  toggle: {
    alignSelf: 'stretch',
  },
});
