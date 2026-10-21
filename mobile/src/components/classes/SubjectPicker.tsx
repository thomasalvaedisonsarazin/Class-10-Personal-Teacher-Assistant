import { useQuery } from '@tanstack/react-query';
import { StyleSheet, View } from 'react-native';
import { Checkbox } from 'react-native-paper';

import { AppText, ErrorState, LoadingView } from '@/components/ui';
import { SUBJECTS_TO_CHOOSE, canTickMore } from '@/lib/classes';
import { getApiErrorMessage } from '@/services/api';
import { authService } from '@/services/authService';
import { MIN_TOUCH_TARGET, palette, radius, spacing } from '@/theme';

interface SubjectPickerProps {
  boardId: number;
  value: readonly number[];
  onChange: (subjectIds: number[]) => void;
}

/** 11th / 12th: tick exactly six subjects of your group (only those are shown and unlocked). */
export function SubjectPicker({ boardId, value, onChange }: SubjectPickerProps) {
  const subjects = useQuery({
    queryKey: ['board-subjects', boardId],
    queryFn: () => authService.getBoardSubjects(boardId),
  });

  if (subjects.isPending) {
    return <LoadingView />;
  }
  if (subjects.isError) {
    return (
      <ErrorState
        message={getApiErrorMessage(subjects.error)}
        onRetry={() => void subjects.refetch()}
        retrying={subjects.isFetching}
      />
    );
  }

  const toggle = (id: number): void => {
    onChange(value.includes(id) ? value.filter((v) => v !== id) : [...value, id]);
  };

  return (
    <View style={styles.section} testID="subject-picker">
      <AppText variant="subtitle">
        Your {SUBJECTS_TO_CHOOSE} subjects ({value.length}/{SUBJECTS_TO_CHOOSE})
      </AppText>
      <AppText variant="caption" tone="secondary">
        Tick your language, English and the 4 subjects of your group. Only these subjects are
        shown in the app. After your first payment they can&apos;t be changed.
      </AppText>
      <View style={styles.list}>
        {subjects.data.map((subject) => {
          const checked = value.includes(subject.id);
          const disabled = !checked && !canTickMore(value);
          return (
            <Checkbox.Item
              key={subject.id}
              label={subject.name}
              status={checked ? 'checked' : 'unchecked'}
              onPress={() => toggle(subject.id)}
              disabled={disabled}
              color={palette.primary}
              style={[styles.item, checked && styles.itemSelected]}
              labelStyle={styles.label}
              testID={`subject-choice-${subject.id}`}
            />
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    gap: spacing.md,
  },
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
