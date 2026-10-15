import { Flex, Heading, Icon, Text } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import type { IconType } from 'react-icons';
import { FiInbox } from 'react-icons/fi';

export interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: IconType;
  action?: ReactNode;
}

export function EmptyState({ title, description, icon = FiInbox, action }: EmptyStateProps) {
  return (
    <Flex direction="column" align="center" textAlign="center" gap={3} py={12} px={4}>
      <Flex align="center" justify="center" boxSize={12} borderRadius="full" bg="primary.subtle">
        <Icon as={icon} boxSize={6} color="primary" />
      </Flex>
      <Heading as="h2" size="md" color="fg">
        {title}
      </Heading>
      {description && (
        <Text color="fgMuted" maxW="md">
          {description}
        </Text>
      )}
      {action}
    </Flex>
  );
}
