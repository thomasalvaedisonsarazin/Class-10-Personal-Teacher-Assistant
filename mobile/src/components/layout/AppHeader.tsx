import { StyleSheet } from 'react-native';
import { Appbar } from 'react-native-paper';
import type { ReactNode } from 'react';

import { palette } from '@/theme';

export interface AppHeaderProps {
  title: string;
  subtitle?: string;
  onBack?: () => void;
  /** Extra actions rendered on the right (e.g. <Appbar.Action />). */
  actions?: ReactNode;
  testID?: string;
}

export function AppHeader({ title, subtitle, onBack, actions, testID }: AppHeaderProps) {
  return (
    <Appbar.Header style={styles.header} statusBarHeight={0} testID={testID}>
      {onBack ? <Appbar.BackAction onPress={onBack} accessibilityLabel="Go back" /> : null}
      <Appbar.Content
        title={title}
        subtitle={subtitle}
        titleStyle={styles.title}
      />
      {actions}
    </Appbar.Header>
  );
}

const styles = StyleSheet.create({
  header: {
    backgroundColor: palette.background,
    elevation: 0,
  },
  title: {
    color: palette.textPrimary,
  },
});
