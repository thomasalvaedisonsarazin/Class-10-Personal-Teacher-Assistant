import { Button, Flex, Heading, Icon, Text } from '@chakra-ui/react';
import { FiAlertCircle } from 'react-icons/fi';

export interface ErrorStateProps {
  title?: string;
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ title = 'Something went wrong', message, onRetry }: ErrorStateProps) {
  return (
    <Flex
      role="alert"
      direction="column"
      align="center"
      textAlign="center"
      gap={3}
      py={12}
      px={4}
    >
      <Flex align="center" justify="center" boxSize={12} borderRadius="full" bg="danger.subtle">
        <Icon as={FiAlertCircle} boxSize={6} color="danger" />
      </Flex>
      <Heading as="h2" size="md" color="fg">
        {title}
      </Heading>
      <Text color="fgMuted" maxW="md">
        {message}
      </Text>
      {onRetry && (
        <Button variant="outline" borderColor="border" color="fg" onClick={onRetry}>
          Try again
        </Button>
      )}
    </Flex>
  );
}
