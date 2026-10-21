import { Checkbox, NativeSelect, SimpleGrid, Text } from '@chakra-ui/react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { FormDialog } from '@/components/ui/FormDialog';
import { adminService } from '@/services/adminService';
import type { AdminUser, AdminUserUpdate } from '@/types/admin';

/** 11th / 12th: language + English + 4 group subjects (the API checks the same). */
const SUBJECTS_TO_CHOOSE = 6;

interface StudentClassDialogProps {
  student: AdminUser | null;
  loading: boolean;
  error: string | null;
  onSave: (input: AdminUserUpdate) => void;
  onClose: () => void;
}

/** Change a student's class and 11th / 12th subjects (students can't once they have paid). */
export function StudentClassDialog({ student, loading, error, onSave, onClose }: StudentClassDialogProps) {
  const [boardId, setBoardId] = useState<number | null>(student?.boardId ?? null);
  const [subjectIds, setSubjectIds] = useState<number[]>(student?.subjectIds ?? []);
  const boards = useQuery({ queryKey: ['admin', 'boards'], queryFn: adminService.boards, enabled: student !== null });
  const board = boards.data?.find((b) => b.id === boardId);
  const tree = useQuery({
    queryKey: ['admin', 'curriculum', boardId],
    queryFn: () => adminService.curriculum(boardId ?? 0),
    enabled: student !== null && board?.chooseSubjects === true,
  });
  const needsSubjects = board?.chooseSubjects === true;
  const canSave = boardId !== null && (!needsSubjects || subjectIds.length === SUBJECTS_TO_CHOOSE);

  const toggle = (id: number): void => {
    setSubjectIds((current) => (current.includes(id) ? current.filter((v) => v !== id) : [...current, id]));
  };

  return (
    <FormDialog
      open={student !== null}
      title={`Class of ${student?.fullName ?? student?.email ?? 'student'}`}
      loading={loading}
      error={error}
      size="lg"
      onSubmit={() => {
        if (canSave && boardId !== null) onSave({ boardId, subjectIds: needsSubjects ? subjectIds : [] });
      }}
      onClose={onClose}
    >
      <NativeSelect.Root>
        <NativeSelect.Field
          aria-label="Class"
          value={boardId ?? ''}
          onChange={(e) => {
            setBoardId(Number(e.target.value));
            setSubjectIds([]);
          }}
        >
          <option value="" disabled>
            Choose a class
          </option>
          {boards.data?.map((b) => (
            <option key={b.id} value={b.id}>
              {b.name}
              {b.isActive ? '' : ' (hidden)'}
            </option>
          ))}
        </NativeSelect.Field>
        <NativeSelect.Indicator />
      </NativeSelect.Root>

      {needsSubjects && (
        <>
          <Text fontSize="sm" color="fgMuted">
            Tick exactly {SUBJECTS_TO_CHOOSE} subjects ({subjectIds.length}/{SUBJECTS_TO_CHOOSE}).
          </Text>
          <SimpleGrid columns={{ base: 1, md: 2 }} gap={2}>
            {tree.data?.subjects.map((s) => {
              const checked = subjectIds.includes(s.id);
              return (
                <Checkbox.Root
                  key={s.id}
                  checked={checked}
                  disabled={!checked && subjectIds.length >= SUBJECTS_TO_CHOOSE}
                  onCheckedChange={() => toggle(s.id)}
                >
                  <Checkbox.HiddenInput />
                  <Checkbox.Control />
                  <Checkbox.Label>{s.name}</Checkbox.Label>
                </Checkbox.Root>
              );
            })}
          </SimpleGrid>
        </>
      )}
      <Text fontSize="xs" color="fgMuted">
        Their progress in other classes is kept.
      </Text>
    </FormDialog>
  );
}
