import { Redirect, useRouter } from 'expo-router';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Appbar } from 'react-native-paper';

import { SubjectTile } from '@/components/curriculum/SubjectTile';
import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, EmptyState, ErrorState, LoadingView, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { useStreak, useSubjects } from '@/hooks/useCurriculum';
import { StreakBadge } from '@/components/curriculum/StreakBadge';
import { getApiErrorMessage } from '@/services/api';
import { palette, safeTileColor, spacing } from '@/theme';

const COLUMNS = 2;

export default function HomeScreen() {
  const { user } = useAuth();
  if (user?.role === 'parent') {
    return <Redirect href="/parent" />;
  }
  if (user?.role === 'partner') {
    return <Redirect href="/partner" />;
  }
  return <StudentHome />;
}

function StudentHome() {
  const router = useRouter();
  const { user } = useAuth();
  const subjectsQuery = useSubjects();
  const streakQuery = useStreak();
  const firstName = user?.fullName?.split(' ')[0];

  const header = (
    <AppHeader
      title="Home"
      actions={
        <>
          <Appbar.Action
            icon="download-circle-outline"
            accessibilityLabel="Downloads"
            onPress={() => router.push('/downloads')}
            testID="open-downloads"
          />
          <Appbar.Action
            icon="account-circle-outline"
            accessibilityLabel="Profile"
            onPress={() => router.push('/profile')}
            testID="open-profile"
          />
        </>
      }
    />
  );

  if (subjectsQuery.isPending) {
    return (
      <Screen padded={false}>
        {header}
        <LoadingView message="Loading your subjects" />
      </Screen>
    );
  }

  if (subjectsQuery.isError) {
    return (
      <Screen padded={false}>
        {header}
        <ErrorState
          message={getApiErrorMessage(subjectsQuery.error)}
          onRetry={() => void subjectsQuery.refetch()}
          retrying={subjectsQuery.isFetching}
        />
      </Screen>
    );
  }

  return (
    <Screen testID="home-screen" padded={false}>
      {header}
      <FlatList
        data={subjectsQuery.data}
        keyExtractor={(subject) => String(subject.id)}
        numColumns={COLUMNS}
        columnWrapperStyle={styles.row}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={subjectsQuery.isRefetching}
            onRefresh={() => {
              void subjectsQuery.refetch();
              void streakQuery.refetch();
            }}
            colors={[palette.primary]}
          />
        }
        ListHeaderComponent={
          <View style={styles.intro}>
            <AppText variant="title">{firstName ? `Hi, ${firstName}` : 'Welcome'}</AppText>
            {streakQuery.data ? <StreakBadge streak={streakQuery.data} /> : null}
            <AppText tone="secondary">
              Pick a subject. Pass each topic&apos;s test with 60% to unlock the next one.
            </AppText>
          </View>
        }
        ListEmptyComponent={<EmptyState title="No subjects yet" message="Your subjects will appear here soon." />}
        renderItem={({ item, index }) => (
          <View style={styles.cell}>
            <SubjectTile
              subject={item}
              color={safeTileColor(item.tileColor, index)}
              onPress={() =>
                router.push({
                  pathname: '/subject/[id]',
                  params: { id: String(item.id) },
                })
              }
            />
          </View>
        )}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  row: {
    gap: spacing.md,
  },
  cell: {
    flex: 1 / COLUMNS,
  },
  intro: {
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
});
