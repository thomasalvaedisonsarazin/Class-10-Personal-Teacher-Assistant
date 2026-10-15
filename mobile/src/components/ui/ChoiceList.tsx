import { StyleSheet, View } from 'react-native';
import { RadioButton } from 'react-native-paper';

import { MIN_TOUCH_TARGET, palette, radius, spacing } from '@/theme';

export interface ChoiceOption<T extends string | number> {
  value: T;
  label: string;
  description?: string;
}

export interface ChoiceListProps<T extends string | number> {
  options: readonly ChoiceOption<T>[];
  value: T | null;
  onChange: (value: T) => void;
  testID?: string;
}

/** Single-choice list with large radio rows (board / medium pickers). */
export function ChoiceList<T extends string | number>({
  options,
  value,
  onChange,
  testID,
}: ChoiceListProps<T>) {
  const selected = value === null ? '' : String(value);

  const handleChange = (raw: string): void => {
    const match = options.find((option) => String(option.value) === raw);
    if (match) {
      onChange(match.value);
    }
  };

  return (
    <RadioButton.Group onValueChange={handleChange} value={selected}>
      <View style={styles.list} testID={testID}>
        {options.map((option) => {
          const isSelected = String(option.value) === selected;
          return (
            <RadioButton.Item
              key={String(option.value)}
              value={String(option.value)}
              label={option.description ? `${option.label}\n${option.description}` : option.label}
              color={palette.primary}
              style={[styles.item, isSelected && styles.itemSelected]}
              labelStyle={styles.label}
              accessibilityLabel={option.label}
              testID={testID ? `${testID}-${String(option.value)}` : undefined}
            />
          );
        })}
      </View>
    </RadioButton.Group>
  );
}

const styles = StyleSheet.create({
  list: {
    gap: spacing.sm,
  },
  item: {
    minHeight: MIN_TOUCH_TARGET + spacing.sm,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.locked,
    backgroundColor: palette.surface,
  },
  itemSelected: {
    borderColor: palette.primary,
    borderWidth: 2,
  },
  label: {
    color: palette.textPrimary,
  },
});
