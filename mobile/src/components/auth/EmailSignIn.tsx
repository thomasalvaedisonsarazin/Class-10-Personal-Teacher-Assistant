import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { TextInput } from 'react-native-paper';

import { AppText, PrimaryButton } from '@/components/ui';
import { cleanCode, isValidCode, isValidEmail, normalizeEmail, passwordProblem } from '@/lib/emailAuth';
import { getApiErrorMessage } from '@/services/api';
import { authService } from '@/services/authService';
import { palette, spacing } from '@/theme';
import type { AuthTokens } from '@/types/api';

type Step = 'email' | 'code' | 'password' | 'newPassword';

export interface EmailSignInProps {
  /** Called with our tokens after a successful sign-in. */
  onSignedIn: (tokens: AuthTokens) => Promise<void>;
  onError: (message: string | null) => void;
  /** Go back to the first sign-in screen. */
  onCancel: () => void;
}

/**
 * Email sign-in: a 6-digit code by email, or email + password. Creating a password
 * account and "Forgot password?" both prove the email with a code first.
 */
export function EmailSignIn({ onSignedIn, onError, onCancel }: EmailSignInProps) {
  const [step, setStep] = useState<Step>('email');
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const run = async (action: () => Promise<void>): Promise<void> => {
    onError(null);
    setBusy(true);
    try {
      await action();
    } catch (err) {
      onError(getApiErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const sendCode = (next: Step): Promise<void> =>
    run(async () => {
      if (!isValidEmail(email)) {
        onError('Please type a valid email address.');
        return;
      }
      await authService.requestEmailCode(normalizeEmail(email));
      setCode('');
      setNotice(`We sent a 6-digit code to ${normalizeEmail(email)}. Check your inbox and spam folder.`);
      setStep(next);
    });

  const signInWithCode = (): Promise<void> =>
    run(async () => {
      if (!isValidCode(code)) {
        onError('Type the 6-digit code from the email.');
        return;
      }
      await onSignedIn(await authService.loginWithEmailCode(normalizeEmail(email), code));
    });

  const signInWithPassword = (): Promise<void> =>
    run(async () => {
      if (!isValidEmail(email) || password.length === 0) {
        onError('Type your email and password.');
        return;
      }
      await onSignedIn(await authService.loginWithPassword(normalizeEmail(email), password));
    });

  const savePassword = (): Promise<void> =>
    run(async () => {
      const problem = isValidCode(code) ? passwordProblem(password) : 'Type the 6-digit code from the email.';
      if (problem) {
        onError(problem);
        return;
      }
      await onSignedIn(await authService.setPasswordWithCode(normalizeEmail(email), code, password));
    });

  const goTo = (next: Step): void => {
    onError(null);
    setNotice(null);
    setPassword('');
    setStep(next);
  };

  const emailField = (
    <TextInput
      label="Email address"
      mode="outlined"
      value={email}
      onChangeText={setEmail}
      autoCapitalize="none"
      autoComplete="email"
      keyboardType="email-address"
      textContentType="emailAddress"
      outlineColor={palette.locked}
      activeOutlineColor={palette.primary}
      testID="email-input"
    />
  );

  const codeField = (
    <TextInput
      label="6-digit code"
      mode="outlined"
      value={code}
      onChangeText={(value) => setCode(cleanCode(value))}
      keyboardType="number-pad"
      autoComplete="one-time-code"
      textContentType="oneTimeCode"
      maxLength={6}
      outlineColor={palette.locked}
      activeOutlineColor={palette.primary}
      testID="code-input"
    />
  );

  const passwordField = (label: string, isNew: boolean) => (
    <TextInput
      label={label}
      mode="outlined"
      value={password}
      onChangeText={setPassword}
      secureTextEntry={!showPassword}
      autoCapitalize="none"
      autoComplete={isNew ? 'new-password' : 'current-password'}
      textContentType={isNew ? 'newPassword' : 'password'}
      maxLength={72}
      outlineColor={palette.locked}
      activeOutlineColor={palette.primary}
      right={
        <TextInput.Icon
          icon={showPassword ? 'eye-off' : 'eye'}
          onPress={() => setShowPassword((shown) => !shown)}
          accessibilityLabel={showPassword ? 'Hide password' : 'Show password'}
        />
      }
      testID="password-input"
    />
  );

  return (
    <View style={styles.box} testID="email-sign-in">
      {notice ? (
        <AppText tone="secondary" center>
          {notice}
        </AppText>
      ) : null}

      {step === 'email' ? (
        <>
          {emailField}
          <PrimaryButton
            label="Send me a code"
            icon="email-outline"
            onPress={() => void sendCode('code')}
            loading={busy}
            testID="send-code"
          />
          <PrimaryButton
            label="Sign in with password"
            mode="outlined"
            onPress={() => goTo('password')}
            disabled={busy}
            testID="use-password"
          />
        </>
      ) : null}

      {step === 'code' ? (
        <>
          {codeField}
          <PrimaryButton label="Sign in" onPress={() => void signInWithCode()} loading={busy} testID="code-sign-in" />
          <PrimaryButton label="Send a new code" mode="text" onPress={() => void sendCode('code')} disabled={busy} />
        </>
      ) : null}

      {step === 'password' ? (
        <>
          {emailField}
          {passwordField('Password', false)}
          <PrimaryButton
            label="Sign in"
            onPress={() => void signInWithPassword()}
            loading={busy}
            testID="password-sign-in"
          />
          <PrimaryButton
            label="Create a password / Forgot password?"
            mode="text"
            onPress={() => void sendCode('newPassword')}
            disabled={busy}
            testID="forgot-password"
          />
        </>
      ) : null}

      {step === 'newPassword' ? (
        <>
          {codeField}
          {passwordField('New password (8 or more characters)', true)}
          <PrimaryButton
            label="Save password and sign in"
            onPress={() => void savePassword()}
            loading={busy}
            testID="save-password"
          />
        </>
      ) : null}

      <PrimaryButton
        label="Back"
        mode="text"
        onPress={() => (step === 'email' ? onCancel() : goTo('email'))}
        disabled={busy}
        testID="email-back"
      />
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    gap: spacing.sm,
  },
});
