import { NativeSelect } from '@chakra-ui/react';

import type { AdminBoard } from '@/types/admin';

interface BoardSwitcherProps {
  boards: AdminBoard[] | undefined;
  value: number | undefined;
  onChange: (boardId: number) => void;
}

/** Pick which class (board + class) the page works on. */
export function BoardSwitcher({ boards, value, onChange }: BoardSwitcherProps) {
  if (!boards || boards.length < 2) return null;
  return (
    <NativeSelect.Root size="sm" width="auto">
      <NativeSelect.Field aria-label="Class" value={value ?? ''} onChange={(e) => onChange(Number(e.target.value))}>
        {boards.map((b) => (
          <option key={b.id} value={b.id}>
            {b.name}
            {b.isActive ? '' : ' (hidden)'}
          </option>
        ))}
      </NativeSelect.Field>
      <NativeSelect.Indicator />
    </NativeSelect.Root>
  );
}
