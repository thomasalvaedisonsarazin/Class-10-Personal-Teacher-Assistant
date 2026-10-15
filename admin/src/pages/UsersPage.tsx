import { FiUsers } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageWrapper } from '@/components/ui/PageWrapper';

export default function UsersPage() {
  return (
    <PageWrapper title="Users" description="Students, parents and admins.">
      <Card>
        <EmptyState
          icon={FiUsers}
          title="No users to show"
          description="The user list with activate and deactivate controls will show here."
        />
      </Card>
    </PageWrapper>
  );
}
