import { Box, Flex, Heading, Stack, Text } from '@chakra-ui/react';
import { motion, useReducedMotion } from 'framer-motion';
import type { ReactNode } from 'react';

export interface PageWrapperProps {
  title?: string;
  description?: string;
  /** Buttons shown to the right of the title. */
  actions?: ReactNode;
  children?: ReactNode;
}

/** Every page sits in this wrapper: a subtle fade-in plus a consistent header. */
export function PageWrapper({ title, description, actions, children }: PageWrapperProps) {
  const reduceMotion = useReducedMotion();

  return (
    <Box asChild w="full">
      <motion.div
        initial={reduceMotion ? false : { opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
      >
        {(title || actions) && (
          <Flex
            mb={6}
            gap={4}
            align={{ base: 'flex-start', md: 'center' }}
            justify="space-between"
            direction={{ base: 'column', md: 'row' }}
          >
            <Stack gap={1}>
              {title && (
                <Heading as="h1" size="xl" color="fg">
                  {title}
                </Heading>
              )}
              {description && <Text color="fgMuted">{description}</Text>}
            </Stack>
            {actions && <Flex gap={2}>{actions}</Flex>}
          </Flex>
        )}
        {children}
      </motion.div>
    </Box>
  );
}
