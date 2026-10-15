import { Badge, Button, Field, HStack, Input, Link, NativeSelect, Stack, Table, Text } from '@chakra-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FiFilm, FiUpload } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormDialog } from '@/components/ui/FormDialog';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { topicOptions, useCurriculumTree } from '@/hooks/useCurriculumTree';
import { adminService } from '@/services/adminService';
import { getApiErrorMessage } from '@/services/api';
import type { Medium } from '@/types/api';
import type { LessonLanguage, LessonStyle } from '@/types/admin';

const PAGE_SIZE = 20;
const STYLES: { value: LessonStyle; label: string }[] = [
  { value: 'story', label: 'Story (shown first)' },
  { value: 'base', label: 'Standard explanation' },
  { value: 'analogy', label: 'Analogy' },
  { value: 'step_by_step', label: 'Step by step' },
  { value: 'real_life', label: 'Real-life examples' },
  { value: 'worked_example', label: 'Worked examples' },
  { value: 'visual', label: 'Visual' },
];

const LANGUAGES: { value: LessonLanguage; label: string }[] = [
  { value: 'en', label: 'English' },
  { value: 'ta', label: 'Tamil' },
  { value: 'tanglish', label: 'Tanglish' },
];

type Filter = 'all' | 'flagged';

export default function ContentPage() {
  const queryClient = useQueryClient();
  const { tree } = useCurriculumTree();
  const topics = topicOptions(tree.data);
  const [filter, setFilter] = useState<Filter>('all');
  const [page, setPage] = useState(1);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [topicId, setTopicId] = useState<number | null>(null);
  const [medium, setMedium] = useState<Medium>('en');
  const [language, setLanguage] = useState<LessonLanguage>('en');
  const [style, setStyle] = useState<LessonStyle>('story');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const lessons = useQuery({
    queryKey: ['admin', 'lessons', filter, page],
    queryFn: () => adminService.lessons({ flagged: filter === 'flagged' ? true : undefined, page, size: PAGE_SIZE }),
  });

  const flag = useMutation({
    mutationFn: ({ id, isFlagged }: { id: number; isFlagged: boolean }) => adminService.flagLesson(id, isFlagged),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin'] }),
  });

  const upload = useMutation({
    mutationFn: () => {
      if (topicId === null || !file) throw new Error('Choose a topic and a file');
      return adminService.uploadLesson({ topicId, medium, language, style, title, file });
    },
    onSuccess: async () => {
      setUploadOpen(false);
      setFile(null);
      setTitle('');
      await queryClient.invalidateQueries({ queryKey: ['admin'] });
    },
    onError: (err) => setFormError(getApiErrorMessage(err)),
  });

  const submitUpload = (): void => {
    setFormError(null);
    if (topicId === null || !file) {
      setFormError('Choose a topic and an MP4 or MP3 file.');
      return;
    }
    upload.mutate();
  };

  const totalPages = lessons.data ? Math.max(1, Math.ceil(lessons.data.total / PAGE_SIZE)) : 1;

  return (
    <PageWrapper
      title="Content"
      description="Lessons students watch. Your uploaded lessons are shown before AI lessons of the same style."
      actions={
        <Button bg="primary" color="primary.contrast" _hover={{ bg: 'primary.hover' }} onClick={() => setUploadOpen(true)}>
          <FiUpload /> Upload lesson
        </Button>
      }
    >
      <Stack gap={4}>
        <HStack>
          {(['all', 'flagged'] as const).map((value) => (
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
              {value === 'all' ? 'All lessons' : 'Flagged'}
            </Button>
          ))}
        </HStack>

        {lessons.isPending && <LoadingState />}
        {lessons.isError && <ErrorState message={getApiErrorMessage(lessons.error)} onRetry={() => void lessons.refetch()} />}
        {lessons.data && lessons.data.items.length === 0 && (
          <Card>
            <EmptyState icon={FiFilm} title="No lessons yet" description="Lessons appear here when students open topics or you upload one." />
          </Card>
        )}
        {lessons.data && lessons.data.items.length > 0 && (
          <Card p={0}>
            <Table.ScrollArea>
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row bg="bg">
                    <Table.ColumnHeader>Topic</Table.ColumnHeader>
                    <Table.ColumnHeader>Lesson</Table.ColumnHeader>
                    <Table.ColumnHeader>Style</Table.ColumnHeader>
                    <Table.ColumnHeader>Source</Table.ColumnHeader>
                    <Table.ColumnHeader>Status</Table.ColumnHeader>
                    <Table.ColumnHeader>Media</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Action</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {lessons.data.items.map((lesson) => (
                    <Table.Row key={lesson.id} opacity={lesson.isFlagged ? 0.6 : 1}>
                      <Table.Cell maxW="220px">
                        <Text truncate>{lesson.topicTitle}</Text>
                        <Text fontSize="xs" color="fgMuted">
                          {LANGUAGES.find((l) => l.value === lesson.language)?.label ?? lesson.language}
                        </Text>
                      </Table.Cell>
                      <Table.Cell maxW="260px">
                        <Text truncate>{lesson.title ?? '—'}</Text>
                      </Table.Cell>
                      <Table.Cell>{STYLES.find((s) => s.value === lesson.style)?.label ?? lesson.style}</Table.Cell>
                      <Table.Cell>{lesson.source === 'uploaded' ? 'Uploaded' : 'AI'}</Table.Cell>
                      <Table.Cell>
                        <Badge
                          variant="subtle"
                          colorPalette={lesson.isFlagged ? 'orange' : lesson.status === 'failed' ? 'red' : lesson.status === 'ready' ? 'green' : 'gray'}
                        >
                          {lesson.isFlagged ? 'Flagged' : lesson.status.replace('_', ' ')}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell>
                        <HStack gap={2}>
                          {lesson.videoUrl && (
                            <Link href={lesson.videoUrl} target="_blank" rel="noreferrer" color="primary">
                              Video
                            </Link>
                          )}
                          {lesson.audioUrl && (
                            <Link href={lesson.audioUrl} target="_blank" rel="noreferrer" color="primary">
                              Audio
                            </Link>
                          )}
                        </HStack>
                      </Table.Cell>
                      <Table.Cell textAlign="end">
                        <Button
                          size="xs"
                          variant="outline"
                          loading={flag.isPending && flag.variables?.id === lesson.id}
                          onClick={() => flag.mutate({ id: lesson.id, isFlagged: !lesson.isFlagged })}
                        >
                          {lesson.isFlagged ? 'Restore' : 'Flag'}
                        </Button>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
          </Card>
        )}
        {lessons.data && totalPages > 1 && (
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
        open={uploadOpen}
        title="Upload a lesson"
        submitLabel="Upload"
        loading={upload.isPending}
        error={formError}
        size="lg"
        onSubmit={submitUpload}
        onClose={() => setUploadOpen(false)}
      >
        <Field.Root required>
          <Field.Label>Topic</Field.Label>
          <NativeSelect.Root>
            <NativeSelect.Field
              value={topicId ?? ''}
              onChange={(e) => setTopicId(e.target.value ? Number(e.target.value) : null)}
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
        <HStack gap={4} align="flex-start">
          <Field.Root>
            <Field.Label>Medium</Field.Label>
            <NativeSelect.Root>
              <NativeSelect.Field value={medium} onChange={(e) => setMedium(e.target.value === 'ta' ? 'ta' : 'en')}>
                <option value="en">English</option>
                <option value="ta">Tamil</option>
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </Field.Root>
          <Field.Root>
            <Field.Label>Explained in</Field.Label>
            <NativeSelect.Root>
              <NativeSelect.Field
                value={language}
                onChange={(e) => setLanguage(LANGUAGES.find((l) => l.value === e.target.value)?.value ?? 'en')}
              >
                {LANGUAGES.map((l) => (
                  <option key={l.value} value={l.value}>
                    {l.label}
                  </option>
                ))}
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </Field.Root>
          <Field.Root>
            <Field.Label>Style</Field.Label>
            <NativeSelect.Root>
              <NativeSelect.Field
                value={style}
                onChange={(e) => setStyle(STYLES.find((s) => s.value === e.target.value)?.value ?? 'story')}
              >
                {STYLES.map((s) => (
                  <option key={s.value} value={s.value}>
                    {s.label}
                  </option>
                ))}
              </NativeSelect.Field>
              <NativeSelect.Indicator />
            </NativeSelect.Root>
          </Field.Root>
        </HStack>
        <Field.Root>
          <Field.Label>Lesson title</Field.Label>
          <Input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Defaults to the topic title" />
        </Field.Root>
        <Field.Root required>
          <Field.Label>File (MP4 video or MP3 audio, up to 150 MB)</Field.Label>
          <Input
            type="file"
            accept="video/mp4,audio/mpeg"
            p={1}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </Field.Root>
      </FormDialog>
    </PageWrapper>
  );
}
