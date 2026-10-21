import { Badge, Box, Button, Field, HStack, Input, NativeSelect, Stack, Text, Textarea } from '@chakra-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FiHelpCircle, FiPlus } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormDialog } from '@/components/ui/FormDialog';
import { LoadingState } from '@/components/ui/LoadingState';
import { BoardSwitcher } from '@/components/curriculum/BoardSwitcher';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { topicOptions, useCurriculumTree } from '@/hooks/useCurriculumTree';
import { adminService } from '@/services/adminService';
import { getApiErrorMessage } from '@/services/api';
import type { Medium } from '@/types/api';
import type { QuestionInput } from '@/types/admin';

const PAGE_SIZE = 20;
type Filter = 'all' | 'flagged' | 'unapproved';

interface NewQuestion {
  topicId: number | null;
  medium: Medium;
  stem: string;
  options: [string, string, string, string];
  correctIndex: number;
  explanation: string;
  difficulty: number;
}

const EMPTY: NewQuestion = {
  topicId: null,
  medium: 'en',
  stem: '',
  options: ['', '', '', ''],
  correctIndex: 0,
  explanation: '',
  difficulty: 2,
};

const DIFFICULTY = ['', 'Easy', 'Medium', 'Hard'];

export default function QuestionsPage() {
  const queryClient = useQueryClient();
  const { boards, board, tree, setBoardId } = useCurriculumTree();
  const topics = topicOptions(tree.data);
  const [filter, setFilter] = useState<Filter>('all');
  const [topicFilter, setTopicFilter] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [createOpen, setCreateOpen] = useState(false);
  const [draft, setDraft] = useState<NewQuestion>(EMPTY);

  const questions = useQuery({
    queryKey: ['admin', 'questions', filter, topicFilter, page],
    queryFn: () =>
      adminService.questions({
        flagged: filter === 'flagged' ? true : undefined,
        approved: filter === 'unapproved' ? false : undefined,
        topicId: topicFilter ?? undefined,
        page,
        size: PAGE_SIZE,
      }),
  });

  const update = useMutation({
    mutationFn: ({ id, ...input }: { id: number; isApproved?: boolean; isFlagged?: boolean }) =>
      adminService.updateQuestion(id, input),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  });

  const create = useMutation({
    mutationFn: () => {
      if (draft.topicId === null) throw new Error('Choose a topic');
      const options = draft.options.map((o) => o.trim());
      const input: QuestionInput = {
        topicId: draft.topicId,
        medium: draft.medium,
        type: 'mcq',
        stem: draft.stem.trim(),
        options,
        correctAnswer: options[draft.correctIndex] ?? '',
        explanation: draft.explanation.trim(),
        difficulty: draft.difficulty,
      };
      return adminService.createQuestion(input);
    },
    onSuccess: async () => {
      setCreateOpen(false);
      setDraft(EMPTY);
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
  });

  const topicLabel = (id: number): string => topics.find((t) => t.id === id)?.label ?? `Topic ${id}`;
  const totalPages = questions.data ? Math.max(1, Math.ceil(questions.data.total / PAGE_SIZE)) : 1;

  return (
    <PageWrapper
      title="Questions"
      description="Check AI questions. Flagged questions are never served to students."
      actions={
        <HStack gap={2}>
          <BoardSwitcher boards={boards.data} value={board?.id} onChange={setBoardId} />
          <Button
            bg="primary"
            color="primary.contrast"
            _hover={{ bg: 'primary.hover' }}
            onClick={() => {
              create.reset();
              setCreateOpen(true);
            }}
          >
            <FiPlus /> Write a question
          </Button>
        </HStack>
      }
    >
      <Stack gap={4}>
        <HStack wrap="wrap" gap={2}>
          {(['all', 'flagged', 'unapproved'] as const).map((value) => (
            <Button
              key={value}
              size="sm"
              variant={filter === value ? 'solid' : 'outline'}
              bg={filter === value ? 'primary' : undefined}
              color={filter === value ? 'primary.contrast' : 'fg'}
              onClick={() => {
                setFilter(value);
                setPage(1);
              }}
            >
              {value === 'all' ? 'All' : value === 'flagged' ? 'Flagged' : 'Not approved'}
            </Button>
          ))}
          <NativeSelect.Root size="sm" maxW="420px">
            <NativeSelect.Field
              value={topicFilter ?? ''}
              onChange={(e) => {
                setTopicFilter(e.target.value ? Number(e.target.value) : null);
                setPage(1);
              }}
            >
              <option value="">All topics</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
        </HStack>

        {questions.isPending && <LoadingState />}
        {questions.isError && (
          <ErrorState message={getApiErrorMessage(questions.error)} onRetry={() => void questions.refetch()} />
        )}
        {questions.data && questions.data.items.length === 0 && (
          <Card>
            <EmptyState icon={FiHelpCircle} title="No questions here" description="AI questions appear when students take tests." />
          </Card>
        )}

        {questions.data?.items.map((q) => (
          <Card key={q.id} opacity={q.isFlagged ? 0.65 : 1}>
            <Stack gap={2}>
              <HStack justify="space-between" align="flex-start" wrap="wrap">
                <Text fontSize="xs" color="fgMuted">
                  {topicLabel(q.topicId)} · {q.medium === 'ta' ? 'Tamil' : 'English'} · {DIFFICULTY[q.difficulty]} ·{' '}
                  {q.source === 'ai' ? 'AI' : 'Admin'}
                </Text>
                <HStack gap={1}>
                  {q.isFlagged && (
                    <Badge colorPalette="orange" variant="subtle">
                      Flagged
                    </Badge>
                  )}
                  {!q.isApproved && (
                    <Badge colorPalette="gray" variant="subtle">
                      Not approved
                    </Badge>
                  )}
                </HStack>
              </HStack>
              <Text color="fg" fontWeight="medium">
                {q.stem}
              </Text>
              <Box as="ul" pl={5} fontSize="sm">
                {(q.options ?? []).map((option) => (
                  <li key={option}>
                    <Text as="span" color={option === q.correctAnswer ? 'success' : 'fg'} fontWeight={option === q.correctAnswer ? 'semibold' : 'normal'}>
                      {option}
                      {option === q.correctAnswer ? '  ✓' : ''}
                    </Text>
                  </li>
                ))}
              </Box>
              <Text fontSize="sm" color="fgMuted">
                {q.explanation}
              </Text>
              <HStack gap={2}>
                <Button
                  size="xs"
                  variant="outline"
                  loading={update.isPending && update.variables?.id === q.id}
                  onClick={() => update.mutate({ id: q.id, isFlagged: !q.isFlagged })}
                >
                  {q.isFlagged ? 'Unflag' : 'Flag as wrong'}
                </Button>
                {!q.isApproved && (
                  <Button size="xs" variant="outline" onClick={() => update.mutate({ id: q.id, isApproved: true })}>
                    Approve
                  </Button>
                )}
              </HStack>
            </Stack>
          </Card>
        ))}

        {questions.data && totalPages > 1 && (
          <HStack justify="center">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Text fontSize="sm" color="fgMuted">
              Page {page} of {totalPages}
            </Text>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </HStack>
        )}
      </Stack>

      <FormDialog
        open={createOpen}
        title="Write a multiple-choice question"
        loading={create.isPending}
        error={create.error ? getApiErrorMessage(create.error) : null}
        size="lg"
        onSubmit={() => create.mutate()}
        onClose={() => setCreateOpen(false)}
      >
        <Field.Root required>
          <Field.Label>Topic</Field.Label>
          <NativeSelect.Root>
            <NativeSelect.Field
              value={draft.topicId ?? ''}
              onChange={(e) => setDraft({ ...draft, topicId: e.target.value ? Number(e.target.value) : null })}
            >
              <option value="">Choose a topic…</option>
              {topics.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.label}
                </option>
              ))}
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
        </Field.Root>
        <HStack gap={4}>
          <Field.Root>
            <Field.Label>Medium</Field.Label>
            <NativeSelect.Root>
              <NativeSelect.Field
                value={draft.medium}
                onChange={(e) => setDraft({ ...draft, medium: e.target.value === 'ta' ? 'ta' : 'en' })}
              >
                <option value="en">English</option>
                <option value="ta">Tamil</option>
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </Field.Root>
          <Field.Root>
            <Field.Label>Difficulty</Field.Label>
            <NativeSelect.Root>
              <NativeSelect.Field
                value={draft.difficulty}
                onChange={(e) => setDraft({ ...draft, difficulty: Number(e.target.value) })}
              >
                <option value={1}>Easy</option>
                <option value={2}>Medium</option>
                <option value={3}>Hard</option>
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </Field.Root>
        </HStack>
        <Field.Root required>
          <Field.Label>Question</Field.Label>
          <Textarea rows={2} value={draft.stem} onChange={(e) => setDraft({ ...draft, stem: e.target.value })} />
        </Field.Root>
        {draft.options.map((option, i) => (
          <Field.Root key={i} required>
            <Field.Label>
              Option {i + 1}
              {i === draft.correctIndex ? ' (correct)' : ''}
            </Field.Label>
            <HStack w="full">
              <Input
                value={option}
                onChange={(e) => {
                  const options = [...draft.options] as NewQuestion['options'];
                  options[i] = e.target.value;
                  setDraft({ ...draft, options });
                }}
              />
              <Button
                size="sm"
                variant={i === draft.correctIndex ? 'solid' : 'outline'}
                bg={i === draft.correctIndex ? 'success' : undefined}
                color={i === draft.correctIndex ? 'white' : 'fg'}
                onClick={() => setDraft({ ...draft, correctIndex: i })}
              >
                Correct
              </Button>
            </HStack>
          </Field.Root>
        ))}
        <Field.Root required>
          <Field.Label>Explanation (shown after the test)</Field.Label>
          <Textarea rows={2} value={draft.explanation} onChange={(e) => setDraft({ ...draft, explanation: e.target.value })} />
        </Field.Root>
      </FormDialog>
    </PageWrapper>
  );
}
