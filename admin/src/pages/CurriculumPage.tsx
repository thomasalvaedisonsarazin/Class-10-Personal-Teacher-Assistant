import { FiBookOpen } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageWrapper } from '@/components/ui/PageWrapper';

export default function CurriculumPage() {
  return (
    <PageWrapper title="Curriculum" description="Boards, subjects, chapters and topics in English and Tamil.">
      <Card>
        <EmptyState
          icon={FiBookOpen}
          title="No curriculum loaded"
          description="The syllabus tree and topic editor will show here."
        />
      </Card>
    </PageWrapper>
  );
}
