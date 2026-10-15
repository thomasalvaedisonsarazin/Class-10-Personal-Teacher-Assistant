import { useLocalSearchParams, useRouter } from 'expo-router';
import { RefreshControl, SectionList, StyleSheet, View } from 'react-native';

import { TopicRow } from '@/components/curriculum/TopicRow';
import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, Screen } from '@/components/ui';
import { parseIdParam, useSubject } from '@/hooks/useCurriculum';
import { getApiErrorMessage } from '@/services/api';
import { palette, radius, safeTileColor, spacing } from '@/theme';
import type { TopicItem } from '@/types/curriculum';

interface TopicSection {
  title: string;
  /** 1-based position of the section's first topic in the whole subject. */
  startIndex: number;
  data: TopicItem[];
}

export default function SubjectScreen() {
  const router = useRouter();
  const { id } = useLocalSearchParams<{ id: string }>();
  const subjectId = parseIdParam(id);
  const subjectQuery = useSubject(subjectId);
  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));

  if (subjectQuery.isPending) {
    return (
      <Screen padded={false}>
        <AppHeader title="Subject" onBack={goBack} />
        <LoadingView />
      </Screen>
    );
  }
  if (subjectQuery.isError) {
    return (
      <Screen padded={false}>
        <AppHeader title="Subject" onBack={goBack} />
        <ErrorState
          message={getApiErrorMessage(subjectQuery.error)}
          onRetry={() => void subjectQuery.refetch()}
          retrying={subjectQuery.isFetching}
        />
      </Screen>
    );
  }

  const subject = subjectQuery.data;
  const color = safeTileColor(subject.tileColor, subject.id - 1);
  const sections: TopicSection[] = subject.chapters.map((chapter, chapterIndex) => ({
    title: chapter.title,
    startIndex:
      1 + subject.chapters.slice(0, chapterIndex).reduce((sum, c) => sum + c.topics.length, 0),
    data: chapter.topics,
  }));

  return (
    <Screen padded={false} testID="subject-screen">
      <AppHeader title={subject.name} onBack={goBack} />
      <SectionList
        sections={sections}
        keyExtractor={(topic) => String(topic.id)}
        contentContainerStyle={styles.list}
        stickySectionHeadersEnabled={false}
        refreshControl={
          <RefreshControl
            refreshing={subjectQuery.isRefetching}
            onRefresh={() => void subjectQuery.refetch()}
            colors={[palette.primary]}
          />
        }
        ListHeaderComponent={
          <View style={[styles.banner, { backgroundColor: color }]}>
            <AppText variant="title" tone="inverse">
              {subject.completedTopics} of {subject.totalTopics} topics passed
            </AppText>
            <AppText variant="bodySmall" tone="inverse">
              Topics open one by one. Pass a topic&apos;s test with 60% or more to unlock the next.
            </AppText>
          </View>
        }
        renderSectionHeader={({ section }) => (
          <AppText variant="subtitle" style={styles.sectionTitle}>
            {section.title}
          </AppText>
        )}
        renderItem={({ item, index, section }) => (
          <TopicRow
            topic={item}
            index={section.startIndex + index}
            onPress={() =>
              router.push({ pathname: '/topic/[id]', params: { id: String(item.id) } })
            }
          />
        )}
        ItemSeparatorComponent={() => <View style={styles.separator} />}
      />
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: {
    padding: spacing.lg,
    paddingBottom: spacing.xxl,
  },
  banner: {
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  sectionTitle: {
    marginTop: spacing.xl,
    marginBottom: spacing.sm,
  },
  separator: {
    height: spacing.sm,
  },
});
