import { Button, Dialog, Portal, Stack, Text } from '@chakra-ui/react';
import type { FormEvent, ReactNode } from 'react';

import { PrimaryButton } from '@/components/ui/PrimaryButton';

export interface FormDialogProps {
  open: boolean;
  title: string;
  submitLabel?: string;
  loading?: boolean;
  error?: string | null;
  size?: 'md' | 'lg' | 'xl';
  onSubmit: () => void;
  onClose: () => void;
  children: ReactNode;
}

/** Modal with a form body, an inline error and Cancel / Save buttons. */
export function FormDialog({
  open,
  title,
  submitLabel = 'Save',
  loading = false,
  error,
  size = 'md',
  onSubmit,
  onClose,
  children,
}: FormDialogProps) {
  const handleSubmit = (event: FormEvent<HTMLFormElement>): void => {
    event.preventDefault();
    onSubmit();
  };

  return (
    <Dialog.Root
      open={open}
      size={size}
      placement="center"
      onOpenChange={(details) => {
        if (!details.open && !loading) onClose();
      }}
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content bg="surface" borderRadius="lg" mx={4}>
            <form onSubmit={handleSubmit}>
              <Dialog.Header>
                <Dialog.Title color="fg">{title}</Dialog.Title>
              </Dialog.Header>
              <Dialog.Body>
                <Stack gap={4}>
                  {children}
                  {error && (
                    <Text role="alert" fontSize="sm" color="danger">
                      {error}
                    </Text>
                  )}
                </Stack>
              </Dialog.Body>
              <Dialog.Footer gap={2}>
                <Button variant="ghost" color="fg" onClick={onClose} disabled={loading}>
                  Cancel
                </Button>
                <PrimaryButton type="submit" loading={loading}>
                  {submitLabel}
                </PrimaryButton>
              </Dialog.Footer>
            </form>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
