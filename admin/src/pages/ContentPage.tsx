import { FiFilm } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageWrapper } from '@/components/ui/PageWrapper';

export default function ContentPage() {
  return (
    <PageWrapper title="Content" description="Uploaded and generated lessons, including flagged ones.">
      <Card>
        <EmptyState
          icon={FiFilm}
          title="No lessons yet"
          description="Lesson uploads and the flagged-content review will show here."
        />
      </Card>
    </PageWrapper>
  );
}
