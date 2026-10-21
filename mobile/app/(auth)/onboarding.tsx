import { useQuery } from '@tanstack/react-query';
import { Redirect } from 'expo-router';
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { HelperText, TextInput } from 'react-native-paper';

import { AppText, ChoiceList, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import type { ChoiceOption } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { getApiErrorMessage } from '@/services/api';
import { installReferralCode, normalizeReferralCode } from '@/lib/referral';
import { authService } from '@/services/authService';
import { partnerService } from '@/services/partnerService';
import { palette, spacing } from '@/theme';
import type { Medium } from '@/types/api';

type SetupRole = 'student' | 'parent';

const ROLE_OPTIONS: readonly ChoiceOption<SetupRole>[] = [
  { value: 'student', label: "I'm a student (10th standard)" },
  { value: 'parent', label: "I'm a parent — I want to follow my child's progress" },
];

const MEDIUM_OPTIONS: readonly ChoiceOption<Medium>[] = [
  { value: 'en', label: 'English medium' },
  { value: 'ta', label: 'தமிழ் வழி (Tamil medium)' },
];

const APP_LANGUAGE_OPTIONS: readonly ChoiceOption<Medium>[] = [
  { value: 'en', label: 'English' },
  { value: 'ta', label: 'தமிழ் (Tamil)' },
];

export default function OnboardingScreen() {
  const { status, user, refreshUser, signOut } = useAuth();
  const [role, setRole] = useState<SetupRole>(user?.role === 'parent' ? 'parent' : 'student');
  const [boardId, setBoardId] = useState<number | null>(user?.boardId ?? null);
  const [medium, setMedium] = useState<Medium | null>(user?.medium ?? null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [schoolCode, setSchoolCode] = useState('');

  // Installed from a school's / teacher's link: fill in their code automatically.
  useEffect(() => {
    let active = true;
    void installReferralCode().then((code) => {
      if (active && code) setSchoolCode((current) => current || code);
    });
    return () => {
      active = false;
    };
  }, []);

  // Admins keep their role (the API refuses to change it); they set up like a student.
  const isAdmin = user?.role === 'admin';
  const isParent = !isAdmin && role === 'parent';
  const boardsQuery = useQuery({
    queryKey: ['boards'],
    queryFn: authService.getBoards,
    enabled: status === 'needsOnboarding' && !isParent,
  });

  if (status === 'signedOut') {
    return <Redirect href="/login" />;
  }

  // Only one board available (TN State Board for now): pre-select it.
  const boards = boardsQuery.data;
  const selectedBoardId = boardId ?? (boards?.length === 1 ? boards[0].id : null);
  const canSave = medium !== null && (isParent || selectedBoardId !== null);

  const handleSave = async (): Promise<void> => {
    if (!canSave || medium === null) {
      return;
    }
    setError(null);
    setSaving(true);
    try {
      const code = normalizeReferralCode(schoolCode);
      if (!isParent && code) {
        await partnerService.useReferralCode(code);
      }
      await authService.updateMe(
        isParent
          ? { role: 'parent', medium }
          : {
              role: isAdmin ? undefined : 'student',
              boardId: selectedBoardId ?? undefined,
              medium,
            },
      );
      await refreshUser();
    } catch (err) {
      setError(getApiErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  if (!isParent && boardsQuery.isPending) {
    return <LoadingView />;
  }
  if (!isParent && boardsQuery.isError) {
    return (
      <Screen>
        <ErrorState
          message={getApiErrorMessage(boardsQuery.error)}
          onRetry={() => void boardsQuery.refetch()}
          retrying={boardsQuery.isFetching}
        />
      </Screen>
    );
  }

  const boardOptions: ChoiceOption<number>[] = (boards ?? []).map((board) => ({
    value: board.id,
    label: board.name,
  }));

  return (
    <Screen scroll testID="onboarding-screen">
      <View style={styles.content}>
        <View style={styles.header}>
          <AppText variant="display">Welcome!</AppText>
          <AppText tone="secondary">Tell us who is using the app.</AppText>
        </View>

        {isAdmin ? null : (
          <View style={styles.section}>
            <ChoiceList options={ROLE_OPTIONS} value={role} onChange={setRole} testID="role-picker" />
          </View>
        )}

        {isParent ? (
          <View style={styles.section}>
            <AppText variant="subtitle">App language</AppText>
            <ChoiceList options={APP_LANGUAGE_OPTIONS} value={medium} onChange={setMedium} testID="language-picker" />
            <AppText variant="caption" tone="secondary">
              Next, you will enter the code your child shares from their app.
            </AppText>
          </View>
        ) : (
          <>
            <View style={styles.section}>
              <AppText variant="subtitle">Your board</AppText>
              <ChoiceList options={boardOptions} value={selectedBoardId} onChange={setBoardId} testID="board-picker" />
            </View>
            <View style={styles.section}>
              <AppText variant="subtitle">Your medium</AppText>
              <ChoiceList options={MEDIUM_OPTIONS} value={medium} onChange={setMedium} testID="medium-picker" />
            </View>
            {isAdmin ? null : (
              <View style={styles.section}>
                <AppText variant="subtitle">School or teacher code (optional)</AppText>
                <TextInput
                  label="Code"
                  mode="outlined"
                  autoCapitalize="characters"
                  maxLength={30}
                  value={schoolCode}
                  onChangeText={setSchoolCode}
                  outlineColor={palette.locked}
                  activeOutlineColor={palette.primary}
                  testID="school-code"
                />
              </View>
            )}
          </>
        )}

        <HelperText type="error" visible={error !== null}>
          {error ?? ''}
        </HelperText>

        <PrimaryButton
          label={isParent ? 'Continue' : 'Start learning'}
          onPress={() => void handleSave()}
          disabled={!canSave}
          loading={saving}
          testID="onboarding-save"
        />
        <PrimaryButton
          label="Sign out"
          mode="text"
          onPress={() => void signOut()}
          disabled={saving}
          testID="onboarding-sign-out"
        />
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    flex: 1,
    gap: spacing.xl,
    paddingVertical: spacing.xl,
  },
  header: {
    gap: spacing.sm,
  },
  section: {
    gap: spacing.md,
  },
});
