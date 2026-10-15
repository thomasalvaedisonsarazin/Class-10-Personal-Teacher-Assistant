import { FiGrid } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageWrapper } from '@/components/ui/PageWrapper';

export default function DashboardPage() {
  return (
    <PageWrapper title="Dashboard" description="Students, pass rates and content health at a glance.">
      <Card>
        <EmptyState
          icon={FiGrid}
          title="No stats yet"
          description="Student counts, pass rates and not-clear hotspots will show here."
        />
      </Card>
    </PageWrapper>
  );
}
