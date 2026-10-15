import { useRouter } from 'expo-router';
import { FlatList, StyleSheet, View } from 'react-native';
import { Button } from 'react-native-paper';

import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, EmptyState, LoadingView, Screen } from '@/components/ui';
import { useDeleteDownload, useDownloads } from '@/hooks/useDownloads';
import { formatSize, offlineSupported } from '@/services/offlineService';
import { palette, radius, spacing } from '@/theme';

/** Lessons saved on the phone: play without internet, or delete to free space. */
export default function DownloadsScreen() {
  const router = useRouter();
  const downloads = useDownloads();
  const remove = useDeleteDownload();
  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));
  const total = (downloads.data ?? []).reduce((sum, d) => sum + d.sizeBytes, 0);

  return (
    <Screen padded={false} testID="downloads-screen">
      <AppHeader title="Downloads" subtitle={total ? `${formatSize(total)} used` : undefined} onBack={goBack} />
      {!offlineSupported ? (
        <EmptyState
          title="Downloads work in the phone app"
          message="Install the Android app to save lessons and watch them without internet."
        />
      ) : downloads.isPending ? (
        <LoadingView />
      ) : (
        <FlatList
          data={downloads.data ?? []}
          keyExtractor={(d) => String(d.lesson.id)}
          contentContainerStyle={styles.list}
          ListHeaderComponent={
            <AppText variant="bodySmall" tone="secondary">
              Saved lessons play without internet. Tests still need internet, because every test
              has new questions.
            </AppText>
          }
          ListEmptyComponent={
            <EmptyState
              title="No downloads yet"
              message="Open a lesson and tap “Download for offline”."
            />
          }
          renderItem={({ item }) => (
            <View style={styles.row}>
              <View style={styles.text}>
                <AppText>{item.topicTitle}</AppText>
                <AppText variant="caption" tone="secondary">
                  {item.subjectName} · {item.lesson.styleLabel} · {formatSize(item.sizeBytes)}
                </AppText>
              </View>
              <Button
                mode="contained-tonal"
                icon="play"
                onPress={() =>
                  router.push({ pathname: '/offline/[lessonId]', params: { lessonId: String(item.lesson.id) } })
                }
              >
                Play
              </Button>
              <Button
                mode="text"
                textColor={palette.error}
                onPress={() => remove.mutate(item.lesson.id)}
                accessibilityLabel={`Delete ${item.topicTitle}`}
              >
                Delete
              </Button>
            </View>
          )}
        />
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    padding: spacing.lg,
    gap: spacing.md,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: palette.surface,
  },
  text: {
    flex: 1,
  },
});
