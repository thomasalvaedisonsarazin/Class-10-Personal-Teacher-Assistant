import { FiHelpCircle } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageWrapper } from '@/components/ui/PageWrapper';

export default function QuestionsPage() {
  return (
    <PageWrapper title="Questions" description="Review, edit and approve practice questions.">
      <Card>
        <EmptyState
          icon={FiHelpCircle}
          title="Review queue is empty"
          description="Questions waiting for approval will show here."
        />
      </Card>
    </PageWrapper>
  );
}
