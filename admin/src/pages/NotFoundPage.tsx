import { Flex } from '@chakra-ui/react';
import { FiCompass } from 'react-icons/fi';
import { Link as RouterLink } from 'react-router-dom';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { PrimaryButton } from '@/components/ui/PrimaryButton';

export default function NotFoundPage() {
  return (
    <Flex minH="100vh" align="center" justify="center" bg="bg" px={4}>
      <PageWrapper>
        <Card maxW="md" mx="auto">
          <EmptyState
            icon={FiCompass}
            title="Page not found"
            description="The page you are looking for does not exist."
            action={
              <PrimaryButton asChild>
                <RouterLink to="/admin">Go to dashboard</RouterLink>
              </PrimaryButton>
            }
          />
        </Card>
      </PageWrapper>
    </Flex>
  );
}
