import { Flex, Spinner, Text } from '@chakra-ui/react';

export interface LoadingStateProps {
  label?: string;
  /** Fill the viewport (used for route-level loading). */
  fullPage?: boolean;
}

export function LoadingState({ label = 'Loading...', fullPage = false }: LoadingStateProps) {
  return (
    <Flex
      role="status"
      aria-live="polite"
      direction="column"
      align="center"
      justify="center"
      gap={3}
      py={12}
      minH={fullPage ? '100vh' : undefined}
    >
      <Spinner color="primary" size="lg" borderWidth="3px" />
      <Text color="fgMuted">{label}</Text>
    </Flex>
  );
}
