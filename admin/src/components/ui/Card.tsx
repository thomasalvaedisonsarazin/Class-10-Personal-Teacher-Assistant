import { Box, type BoxProps } from '@chakra-ui/react';

export interface CardProps extends BoxProps {
  /** Adds a gentle shadow lift on hover for clickable cards. */
  interactive?: boolean;
}

/** Flat, solid surface: white background, subtle border and shadow. */
export function Card({ interactive = false, children, ...rest }: CardProps) {
  return (
    <Box
      bg="surface"
      borderWidth="1px"
      borderColor="border"
      borderRadius="lg"
      boxShadow="xs"
      p={{ base: 4, md: 6 }}
      transition="box-shadow 0.15s ease, border-color 0.15s ease"
      cursor={interactive ? 'pointer' : undefined}
      _hover={interactive ? { boxShadow: 'sm', borderColor: 'muted' } : undefined}
      {...rest}
    >
      {children}
    </Box>
  );
}
