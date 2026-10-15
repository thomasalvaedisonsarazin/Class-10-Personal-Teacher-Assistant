import { useQuery } from '@tanstack/react-query';

import { adminService } from '@/services/adminService';
import type { AdminBoard, CurriculumTree } from '@/types/admin';

export interface TopicOption {
  id: number;
  label: string;
}

/** The first active board and its full syllabus tree. */
export function useCurriculumTree() {
  const boards = useQuery({ queryKey: ['admin', 'boards'], queryFn: adminService.boards });
  const board: AdminBoard | undefined = boards.data?.find((b) => b.isActive) ?? boards.data?.[0];
  const tree = useQuery({
    queryKey: ['admin', 'curriculum', board?.id],
    queryFn: () => adminService.curriculum(board?.id ?? 0),
    enabled: board !== undefined,
  });
  return { boards, board, tree };
}

/** "Maths › Sets › What is a set" options for topic pickers. */
export function topicOptions(tree: CurriculumTree | undefined): TopicOption[] {
  if (!tree) return [];
  return tree.subjects.flatMap((s) =>
    s.chapters.flatMap((c) => c.topics.map((t) => ({ id: t.id, label: `${s.name} › ${c.title} › ${t.title}` }))),
  );
}
