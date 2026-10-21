import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AppText, ChoiceList } from '@/components/ui';
import type { ChoiceOption } from '@/components/ui';
import { boardFamilies, classLabel, classesOf, familyLabel } from '@/lib/classes';
import { spacing } from '@/theme';
import type { Board } from '@/types/api';

interface ClassPickerProps {
  boards: readonly Board[];
  value: number | null;
  onChange: (boardId: number) => void;
}

/** Board (TN State / CBSE, shown only when there is more than one) and then class. */
export function ClassPicker({ boards, value, onChange }: ClassPickerProps) {
  const families = boardFamilies(boards);
  const selected = boards.find((board) => board.id === value);
  const [family, setFamily] = useState<string | null>(selected?.family ?? (families.length === 1 ? families[0] : null));

  const familyOptions: ChoiceOption<string>[] = families.map((f) => ({ value: f, label: familyLabel(f) }));
  const classOptions: ChoiceOption<number>[] = family
    ? classesOf(boards, family).map((board) => ({ value: board.id, label: classLabel(board.grade) }))
    : [];

  return (
    <View style={styles.wrap}>
      {families.length > 1 ? (
        <View style={styles.section}>
          <AppText variant="subtitle">Your board</AppText>
          <ChoiceList options={familyOptions} value={family} onChange={setFamily} testID="family-picker" />
        </View>
      ) : null}
      {family ? (
        <View style={styles.section}>
          <AppText variant="subtitle">
            {families.length > 1 ? 'Your class' : `Your class (${familyLabel(family)})`}
          </AppText>
          <ChoiceList
            options={classOptions}
            value={selected?.family === family ? selected.id : null}
            onChange={onChange}
            testID="class-picker"
          />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    gap: spacing.xl,
  },
  section: {
    gap: spacing.md,
  },
});
