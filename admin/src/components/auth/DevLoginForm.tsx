import { Box, Field, Input, Stack, Text } from '@chakra-ui/react';
import { useState, type FormEvent } from 'react';

import { PrimaryButton } from '@/components/ui/PrimaryButton';

export interface DevLoginFormProps {
  onSubmit: (email: string) => void;
  loading: boolean;
}

/** Development builds only: sign in as an existing admin before Google OAuth is set up. */
export function DevLoginForm({ onSubmit, loading }: DevLoginFormProps) {
  const [email, setEmail] = useState('');
  const trimmed = email.trim();

  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    if (trimmed) onSubmit(trimmed);
  };

  return (
    <Box
      asChild
      borderWidth="1px"
      borderStyle="dashed"
      borderColor="border"
      borderRadius="md"
      p={4}
      data-testid="dev-login"
    >
      <form onSubmit={handleSubmit}>
        <Stack gap={3} textAlign="left">
          <Text fontSize="xs" color="fgMuted" textAlign="center">
            Developer sign-in (development builds only)
          </Text>
          <Field.Root required>
            <Field.Label fontSize="sm">Admin email</Field.Label>
            <Input
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="admin@example.com"
            />
          </Field.Root>
          <PrimaryButton type="submit" loading={loading} disabled={!trimmed}>
            Sign in (dev)
          </PrimaryButton>
        </Stack>
      </form>
    </Box>
  );
}
