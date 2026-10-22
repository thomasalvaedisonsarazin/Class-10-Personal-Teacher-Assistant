import { useQuery } from '@tanstack/react-query';

import { isWorking } from '@/lib/exam';
import { examService } from '@/services/examService';

/** While a paper is being written or marked, check again every few seconds. */
const POLL_MS = 4_000;

export const examKeys = {
  overview: (subjectId: number) => ['exam-practice', subjectId] as const,
  paper: (paperId: number) => ['model-paper', paperId] as const,
};

export function useExamOverview(subjectId: number) {
  return useQuery({
    queryKey: examKeys.overview(subjectId),
    queryFn: () => examService.overview(subjectId),
    enabled: Number.isInteger(subjectId) && subjectId > 0,
    refetchInterval: (query) => (query.state.data?.papers.some((p) => isWorking(p.status)) ? POLL_MS : false),
  });
}

export function useModelPaper(paperId: number) {
  return useQuery({
    queryKey: examKeys.paper(paperId),
    queryFn: () => examService.getPaper(paperId),
    enabled: Number.isInteger(paperId) && paperId > 0,
    refetchInterval: (query) => (query.state.data && isWorking(query.state.data.status) ? POLL_MS : false),
  });
}
