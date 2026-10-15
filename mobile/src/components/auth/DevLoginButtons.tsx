import { StyleSheet, View } from 'react-native';

import { AppText, PrimaryButton } from '@/components/ui';
import { palette, radius, spacing } from '@/theme';

export interface DevLoginButtonsProps {
  onLogin: (email: string) => void;
  loadingEmail: string | null;
}

const DEV_ACCOUNTS = [
  { email: 'student@dev.local', label: 'Sign in as test student' },
  { email: 'parent@dev.local', label: 'Sign in as test parent' },
] as const;

/** Development builds only: sign in as seeded users before Google OAuth is set up. */
export function DevLoginButtons({ onLogin, loadingEmail }: DevLoginButtonsProps) {
  return (
    <View style={styles.box} testID="dev-login">
      <AppText variant="caption" tone="secondary" center>
        Developer sign-in (not in the released app)
      </AppText>
      {DEV_ACCOUNTS.map((account) => (
        <PrimaryButton
          key={account.email}
          label={account.label}
          mode="outlined"
          onPress={() => onLogin(account.email)}
          loading={loadingEmail === account.email}
          disabled={loadingEmail !== null && loadingEmail !== account.email}
          testID={`dev-login-${account.email}`}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: palette.locked,
  },
});
