import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { adminService } from '@/services/adminService';
import type { AdminBoard, CurriculumTree } from '@/types/admin';

export interface TopicOption {
  id: number;
  label: string;
}

const STORAGE_KEY = 'pta-admin-board';

function storedBoardId(): number | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? Number(raw) : null;
  } catch {
    return null;
  }
}

/** The chosen class (remembered in this browser; default: first visible one) and its syllabus tree. */
export function useCurriculumTree() {
  const [boardId, setBoardIdState] = useState<number | null>(storedBoardId);
  const boards = useQuery({ queryKey: ['admin', 'boards'], queryFn: adminService.boards });
  const board: AdminBoard | undefined =
    boards.data?.find((b) => b.id === boardId) ?? boards.data?.find((b) => b.isActive) ?? boards.data?.[0];
  const tree = useQuery({
    queryKey: ['admin', 'curriculum', board?.id],
    queryFn: () => adminService.curriculum(board?.id ?? 0),
    enabled: board !== undefined,
  });
  const setBoardId = (id: number): void => {
    setBoardIdState(id);
    try {
      localStorage.setItem(STORAGE_KEY, String(id));
    } catch {
      // Private mode: the choice just isn't remembered.
    }
  };
  return { boards, board, tree, setBoardId };
}

/** "Maths › Sets › What is a set" options for topic pickers. */
export function topicOptions(tree: CurriculumTree | undefined): TopicOption[] {
  if (!tree) return [];
  return tree.subjects.flatMap((s) =>
    s.chapters.flatMap((c) => c.topics.map((t) => ({ id: t.id, label: `${s.name} › ${c.title} › ${t.title}` }))),
  );
}
