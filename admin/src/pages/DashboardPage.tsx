import { SimpleGrid, Stack, Text } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';

import { Card } from '@/components/ui/Card';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { adminService } from '@/services/adminService';
import { getApiErrorMessage } from '@/services/api';

interface StatCardProps {
  label: string;
  value: string | number;
  hint?: string;
  tone?: 'default' | 'warning';
}

function StatCard({ label, value, hint, tone = 'default' }: StatCardProps) {
  return (
    <Card>
      <Stack gap={1}>
        <Text fontSize="sm" color="fgMuted">
          {label}
        </Text>
        <Text fontSize="3xl" fontWeight="semibold" color={tone === 'warning' ? 'warning' : 'fg'}>
          {value}
        </Text>
        {hint && (
          <Text fontSize="xs" color="fgMuted">
            {hint}
          </Text>
        )}
      </Stack>
    </Card>
  );
}

export default function DashboardPage() {
  const stats = useQuery({ queryKey: ['admin', 'stats'], queryFn: adminService.stats, refetchInterval: 60_000 });

  return (
    <PageWrapper title="Dashboard" description="How students are learning this week.">
      {stats.isPending && <LoadingState />}
      {stats.isError && <ErrorState message={getApiErrorMessage(stats.error)} onRetry={() => void stats.refetch()} />}
      {stats.data && (
        <SimpleGrid columns={{ base: 1, sm: 2, lg: 4 }} gap={4}>
          <StatCard label="Students" value={stats.data.students} hint={`${stats.data.activeStudentsWeek} active this week`} />
          <StatCard
            label="Tests this week"
            value={stats.data.quizAttemptsWeek}
            hint={stats.data.passRateWeek === null ? 'No tests yet' : `${stats.data.passRateWeek}% passed`}
          />
          <StatCard label="Published topics" value={stats.data.topicsPublished} hint={`${stats.data.subjects} subjects`} />
          <StatCard label="AI explanations today" value={stats.data.generationsToday} />
          <StatCard label="Lessons ready" value={stats.data.lessonsReady} />
          <StatCard
            label="Flagged lessons"
            value={stats.data.lessonsFlagged}
            tone={stats.data.lessonsFlagged ? 'warning' : 'default'}
          />
          <StatCard label="Approved questions" value={stats.data.questionsApproved} />
          <StatCard
            label="Failed AI jobs (7 days)"
            value={stats.data.failedJobsWeek}
            tone={stats.data.failedJobsWeek ? 'warning' : 'default'}
          />
        </SimpleGrid>
      )}
    </PageWrapper>
  );
}
