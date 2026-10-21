import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { HelperText, TextInput } from 'react-native-paper';

import { AppText, PrimaryButton } from '@/components/ui';
import { normalizeReferralCode } from '@/lib/referral';
import { getApiErrorMessage } from '@/services/api';
import { partnerService } from '@/services/partnerService';
import { palette, spacing } from '@/theme';

export interface SchoolCodeEntryProps {
  /** Called after the code is accepted (refresh the user). */
  onLinked: () => Promise<unknown>;
}

/** Profile: a student who skipped it at sign-up can still add their school's code. */
export function SchoolCodeEntry({ onLinked }: SchoolCodeEntryProps) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ type: 'error' | 'info'; text: string } | null>(null);

  const submit = async (): Promise<void> => {
    const clean = normalizeReferralCode(code);
    if (clean.length < 3) {
      setMessage({ type: 'error', text: 'Type the code your school or teacher gave you.' });
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const name = await partnerService.useReferralCode(clean);
      setMessage({ type: 'info', text: `Added: ${name}` });
      await onLinked();
    } catch (err) {
      setMessage({ type: 'error', text: getApiErrorMessage(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={styles.box} testID="school-code-entry">
      <AppText variant="subtitle">School or teacher code</AppText>
      <AppText variant="caption" tone="secondary">
        Got a code from your school or teacher? Add it before your first purchase.
      </AppText>
      <TextInput
        label="Code"
        mode="outlined"
        autoCapitalize="characters"
        maxLength={30}
        value={code}
        onChangeText={setCode}
        outlineColor={palette.locked}
        activeOutlineColor={palette.primary}
      />
      <HelperText type={message?.type ?? 'info'} visible={message !== null}>
        {message?.text ?? ''}
      </HelperText>
      <PrimaryButton label="Add code" mode="outlined" onPress={() => void submit()} loading={busy} />
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    gap: spacing.sm,
  },
});
