import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { Appbar, HelperText, TextInput } from 'react-native-paper';

import { AppHeader } from '@/components/layout/AppHeader';
import { ProgressBar } from '@/components/parent/ProgressBar';
import { AppText, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { relativeDay } from '@/lib/time';
import { getApiErrorMessage } from '@/services/api';
import { parentService } from '@/services/parentService';
import { palette, radius, safeTileColor, spacing } from '@/theme';
import type { ChildSummary } from '@/types/parent';

const CODE_LENGTH = 8;

interface ChildCardProps {
  child: ChildSummary;
  onPress: () => void;
}

function ChildCard({ child, onPress }: ChildCardProps) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${child.name ?? 'Your child'}: ${child.topicsCompleted} of ${child.topicsTotal} topics passed`}
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
      testID={`child-${child.studentId}`}
    >
      <AppText variant="title">{child.name ?? 'Your child'}</AppText>
      <AppText tone="secondary">
        {child.topicsCompleted} of {child.topicsTotal} topics passed · active {relativeDay(child.lastActiveAt)}
      </AppText>
      <ProgressBar value={child.topicsCompleted} total={child.topicsTotal} color={palette.success} />
      <View style={styles.subjects}>
        {child.subjects.map((s, i) => (
          <View key={s.subjectId} style={styles.subjectRow}>
            <View style={[styles.dot, { backgroundColor: safeTileColor(s.tileColor, i) }]} />
            <AppText variant="bodySmall" style={styles.subjectName}>
              {s.name}
            </AppText>
            <AppText variant="bodySmall" tone="secondary">
              {s.completed}/{s.total}
            </AppText>
          </View>
        ))}
      </View>
      <AppText variant="caption" tone="secondary">
        Tests this week: {child.testsThisWeek}
        {child.averageScoreThisWeek !== null ? ` · average ${Math.round(child.averageScoreThisWeek)}%` : ''}
      </AppText>
    </Pressable>
  );
}

export default function ParentHomeScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [code, setCode] = useState('');

  const children = useQuery({ queryKey: ['parent', 'children'], queryFn: parentService.children });
  const link = useMutation({
    mutationFn: (value: string) => parentService.linkChild(value),
    onSuccess: async () => {
      setCode('');
      await queryClient.invalidateQueries({ queryKey: ['parent', 'children'] });
    },
  });

  const cleaned = code.toUpperCase().replace(/[^A-Z0-9]/g, '');
  const header = (
    <AppHeader
      title={user?.fullName ? `Hello, ${user.fullName.split(' ')[0]}` : 'Parent'}
      actions={
        <Appbar.Action
          icon="account-circle-outline"
          accessibilityLabel="Profile"
          onPress={() => router.push('/profile')}
        />
      }
    />
  );

  if (children.isPending) {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView />
      </Screen>
    );
  }
  if (children.isError) {
    return (
      <Screen padded={false}>
        {header}
        <ErrorState message={getApiErrorMessage(children.error)} onRetry={() => void children.refetch()} />
      </Screen>
    );
  }

  return (
    <Screen padded={false} testID="parent-home">
      {header}
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
        refreshControl={
          <RefreshControl
            refreshing={children.isRefetching}
            onRefresh={() => void children.refetch()}
            colors={[palette.primary]}
          />
        }
      >
        {children.data.length === 0 ? (
          <AppText tone="secondary">
            Ask your child to open the app → Profile → “Invite a parent”, then enter their code below.
          </AppText>
        ) : (
          children.data.map((child) => (
            <ChildCard
              key={child.studentId}
              child={child}
              onPress={() =>
                router.push({ pathname: '/parent/[studentId]', params: { studentId: String(child.studentId) } })
              }
            />
          ))
        )}

        <View style={styles.card}>
          <AppText variant="subtitle">Link a child</AppText>
          <TextInput
            mode="outlined"
            label="8-character code"
            value={code}
            onChangeText={setCode}
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={CODE_LENGTH + 2}
            outlineColor={palette.locked}
            activeOutlineColor={palette.primary}
            testID="link-code"
          />
          <HelperText type="error" visible={link.isError}>
            {link.isError ? getApiErrorMessage(link.error) : ''}
          </HelperText>
          <PrimaryButton
            label="Link child"
            icon="link-variant"
            onPress={() => link.mutate(cleaned)}
            disabled={cleaned.length !== CODE_LENGTH}
            loading={link.isPending}
            testID="link-submit"
          />
        </View>
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  card: {
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.lg,
    backgroundColor: palette.surface,
  },
  pressed: {
    opacity: 0.88,
  },
  subjects: {
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  subjectRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: radius.pill,
  },
  subjectName: {
    flex: 1,
  },
});
