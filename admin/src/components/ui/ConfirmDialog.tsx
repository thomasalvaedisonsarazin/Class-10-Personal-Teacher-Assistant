import { Button, Dialog, Portal, Text } from '@chakra-ui/react';

import { PrimaryButton } from '@/components/ui/PrimaryButton';

export interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Styles the confirm button for destructive actions (delete, deactivate). */
  destructive?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  destructive = false,
  loading = false,
  onConfirm,
  onClose,
}: ConfirmDialogProps) {
  return (
    <Dialog.Root
      role="alertdialog"
      open={open}
      placement="center"
      onOpenChange={(details) => {
        if (!details.open && !loading) onClose();
      }}
    >
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content bg="surface" borderRadius="lg" mx={4}>
            <Dialog.Header>
              <Dialog.Title color="fg">{title}</Dialog.Title>
            </Dialog.Header>
            {description && (
              <Dialog.Body>
                <Text color="fgMuted">{description}</Text>
              </Dialog.Body>
            )}
            <Dialog.Footer gap={2}>
              <Button variant="ghost" color="fg" onClick={onClose} disabled={loading}>
                {cancelLabel}
              </Button>
              <PrimaryButton
                onClick={onConfirm}
                loading={loading}
                bg={destructive ? 'danger' : 'primary'}
                _hover={{ bg: destructive ? 'danger' : 'primary.hover', opacity: destructive ? 0.9 : 1 }}
              >
                {confirmLabel}
              </PrimaryButton>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}
