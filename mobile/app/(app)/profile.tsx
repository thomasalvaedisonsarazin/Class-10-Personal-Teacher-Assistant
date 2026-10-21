import { useRouter } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { HelperText, TextInput } from 'react-native-paper';

import { useQuery } from '@tanstack/react-query';

import { ClassPicker } from '@/components/classes/ClassPicker';
import { SubjectPicker } from '@/components/classes/SubjectPicker';
import { AppHeader } from '@/components/layout/AppHeader';
import { ParentAccess } from '@/components/parent/ParentAccess';
import { SchoolCodeEntry } from '@/components/partner/SchoolCodeEntry';
import { AppText, ChoiceList, PrimaryButton, Screen } from '@/components/ui';
import type { ChoiceOption } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { SUBJECTS_TO_CHOOSE } from '@/lib/classes';
import { getApiErrorMessage } from '@/services/api';
import { authService } from '@/services/authService';
import { palette, spacing } from '@/theme';
import type { LessonLanguage, Medium } from '@/types/api';

const MEDIUM_OPTIONS: readonly ChoiceOption<Medium>[] = [
  { value: 'en', label: 'English medium' },
  { value: 'ta', label: 'தமிழ் வழி (Tamil medium)' },
];

const LESSON_LANGUAGE_OPTIONS: readonly ChoiceOption<LessonLanguage>[] = [
  { value: 'en', label: 'English' },
  { value: 'ta', label: 'தமிழ் (Tamil)' },
  { value: 'tanglish', label: 'Tanglish (Tamil with English words)' },
];

const MAX_NAME_LENGTH = 100;

export default function ProfileScreen() {
  const router = useRouter();
  const { user, refreshUser, signOut } = useAuth();
  const [fullName, setFullName] = useState(user?.fullName ?? '');
  const [medium, setMedium] = useState<Medium | null>(user?.medium ?? null);
  const initialLanguage: LessonLanguage | null = user?.lessonLanguage ?? user?.medium ?? null;
  const [lessonLanguage, setLessonLanguage] = useState<LessonLanguage | null>(initialLanguage);
  const [boardId, setBoardId] = useState<number | null>(user?.boardId ?? null);
  const initialSubjects = user?.subjectIds ?? [];
  const [subjectIds, setSubjectIds] = useState<number[]>(initialSubjects);
  const [saving, setSaving] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState<{
    type: 'error' | 'info';
    text: string;
  } | null>(null);

  const isParent = user?.role === 'parent';
  const classLocked = user?.classLocked === true;
  const boardsQuery = useQuery({ queryKey: ['boards'], queryFn: authService.getBoards, enabled: !isParent });
  const selectedBoard = boardsQuery.data?.find((board) => board.id === boardId);
  const needsSubjects = !isParent && selectedBoard?.chooseSubjects === true;
  const classChanged = boardId !== (user?.boardId ?? null);
  const subjectsChanged = [...subjectIds].sort().join(',') !== [...initialSubjects].sort().join(',');
  const trimmedName = fullName.trim();
  const changed =
    trimmedName !== (user?.fullName ?? '') ||
    medium !== (user?.medium ?? null) ||
    lessonLanguage !== initialLanguage ||
    classChanged ||
    subjectsChanged;

  const handleClassChange = (id: number): void => {
    setBoardId(id);
    setSubjectIds(id === user?.boardId ? initialSubjects : []);
  };

  const handleSave = async (): Promise<void> => {
    if (!trimmedName || medium === null) {
      setMessage({ type: 'error', text: 'Please enter your name.' });
      return;
    }
    if (needsSubjects && subjectIds.length !== SUBJECTS_TO_CHOOSE) {
      setMessage({ type: 'error', text: `Please tick exactly ${SUBJECTS_TO_CHOOSE} subjects.` });
      return;
    }
    setMessage(null);
    setSaving(true);
    try {
      await authService.updateMe({
        fullName: trimmedName,
        medium,
        lessonLanguage: lessonLanguage ?? undefined,
        boardId: classChanged && boardId !== null ? boardId : undefined,
        subjectIds: needsSubjects && (classChanged || subjectsChanged) ? subjectIds : undefined,
      });
      await refreshUser();
      setMessage({ type: 'info', text: 'Saved.' });
    } catch (err) {
      setMessage({ type: 'error', text: getApiErrorMessage(err) });
    } finally {
      setSaving(false);
    }
  };

  const handleSignOut = async (): Promise<void> => {
    setSigningOut(true);
    await signOut();
  };

  const handleDelete = async (): Promise<void> => {
    setMessage(null);
    setDeleting(true);
    try {
      await authService.deleteAccount();
      await signOut();
    } catch (err) {
      setMessage({ type: 'error', text: getApiErrorMessage(err) });
      setDeleting(false);
      setConfirmDelete(false);
    }
  };

  return (
    <Screen padded={false} testID="profile-screen">
      <AppHeader title="Profile" onBack={() => router.back()} />
      <Screen scroll edges={[]}>
        <View style={styles.content}>
          <AppText tone="secondary">{user?.email}</AppText>

          <TextInput
            label="Your name"
            mode="outlined"
            value={fullName}
            onChangeText={setFullName}
            maxLength={MAX_NAME_LENGTH}
            outlineColor={palette.locked}
            activeOutlineColor={palette.primary}
            testID="profile-name"
          />

          <View style={styles.section}>
            <AppText variant="subtitle">{isParent ? 'App language' : 'Textbook medium'}</AppText>
            <ChoiceList options={MEDIUM_OPTIONS} value={medium} onChange={setMedium} testID="profile-medium" />
          </View>

          {isParent ? null : (
            <View style={styles.section}>
              <AppText variant="subtitle">Explain lessons in</AppText>
              <AppText variant="caption" tone="secondary">
                Tests follow your textbook medium. Lessons can be in the language you understand best.
              </AppText>
              <ChoiceList
                options={LESSON_LANGUAGE_OPTIONS}
                value={lessonLanguage}
                onChange={setLessonLanguage}
                testID="profile-lesson-language"
              />
            </View>
          )}

          {!isParent && classLocked ? (
            <View style={styles.section} testID="profile-class-locked">
              <AppText variant="subtitle">Your class</AppText>
              <AppText>
                {selectedBoard?.name ?? ''}
              </AppText>
              <AppText variant="caption" tone="secondary">
                Your class and subjects are fixed after payment. To change them, please contact
                us.
              </AppText>
            </View>
          ) : null}

          {isParent || classLocked || !boardsQuery.data ? null : (
            <View style={styles.section}>
              <ClassPicker boards={boardsQuery.data} value={boardId} onChange={handleClassChange} />
              {classChanged ? (
                <AppText variant="caption" tone="secondary">
                  Your progress in your old class is kept. You can switch back any time.
                </AppText>
              ) : null}
              {needsSubjects && boardId !== null ? (
                <SubjectPicker boardId={boardId} value={subjectIds} onChange={setSubjectIds} />
              ) : null}
            </View>
          )}

          {isParent ? null : (
            <PrimaryButton
              label="Premium plan"
              icon="crown-outline"
              mode="outlined"
              onPress={() => router.push('/premium')}
              testID="profile-premium"
            />
          )}

          {isParent ? null : <ParentAccess />}

          {user?.role === 'student' && !user.referredByPartnerId ? <SchoolCodeEntry onLinked={refreshUser} /> : null}

          <HelperText type={message?.type ?? 'info'} visible={message !== null}>
            {message?.text ?? ''}
          </HelperText>

          <PrimaryButton
            label="Save changes"
            onPress={() => void handleSave()}
            disabled={!changed}
            loading={saving}
            testID="profile-save"
          />
          <PrimaryButton
            label="Sign out"
            mode="outlined"
            onPress={() => void handleSignOut()}
            loading={signingOut}
            testID="profile-sign-out"
          />

          {user?.role === 'admin' ? null : confirmDelete ? (
            <View style={styles.dangerBox} testID="profile-delete-confirm">
              <AppText variant="subtitle">Delete your account?</AppText>
              <AppText tone="secondary">
                {isParent
                  ? 'Your account and your links to your children are deleted forever. Your children keep their own accounts.'
                  : 'Your progress, test scores, streak and parent links are deleted forever. This cannot be undone.'}
              </AppText>
              <PrimaryButton
                label="Yes, delete forever"
                color={palette.error}
                onPress={() => void handleDelete()}
                loading={deleting}
                testID="profile-delete-yes"
              />
              <PrimaryButton
                label="Cancel"
                mode="text"
                onPress={() => setConfirmDelete(false)}
                disabled={deleting}
              />
            </View>
          ) : (
            <PrimaryButton
              label="Delete my account"
              mode="text"
              color={palette.error}
              onPress={() => setConfirmDelete(true)}
              disabled={signingOut}
              testID="profile-delete"
            />
          )}
        </View>
      </Screen>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.lg,
    paddingVertical: spacing.lg,
  },
  section: {
    gap: spacing.md,
  },
  dangerBox: {
    gap: spacing.sm,
    padding: spacing.md,
    borderWidth: 1,
    borderColor: palette.error,
    borderRadius: spacing.sm,
  },
});
