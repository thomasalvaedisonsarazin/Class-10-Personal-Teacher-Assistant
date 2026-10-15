import { Button, type ButtonProps } from '@chakra-ui/react';
import { forwardRef } from 'react';

export type PrimaryButtonProps = ButtonProps;

/** Solid primary action button. Flat colour with a subtle hover and press. */
export const PrimaryButton = forwardRef<HTMLButtonElement, PrimaryButtonProps>(
  function PrimaryButton({ children, ...rest }, ref) {
    return (
      <Button
        ref={ref}
        bg="primary"
        color="primary.contrast"
        borderRadius="md"
        fontWeight="semibold"
        transition="background-color 0.15s ease, transform 0.1s ease"
        _hover={{ bg: 'primary.hover' }}
        _active={{ transform: 'translateY(1px)' }}
        _focusVisible={{ outline: '2px solid', outlineColor: 'primary', outlineOffset: '2px' }}
        {...rest}
      >
        {children}
      </Button>
    );
  },
);
