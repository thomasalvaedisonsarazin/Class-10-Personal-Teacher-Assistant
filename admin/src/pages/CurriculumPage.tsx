import { Badge, Box, Button, Field, HStack, Input, Stack, Table, Text, Textarea } from '@chakra-ui/react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FiBookOpen, FiEdit2, FiPlus, FiUpload } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormDialog } from '@/components/ui/FormDialog';
import { LoadingState } from '@/components/ui/LoadingState';
import { BoardSwitcher } from '@/components/curriculum/BoardSwitcher';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { PrimaryButton } from '@/components/ui/PrimaryButton';
import { useCurriculumTree } from '@/hooks/useCurriculumTree';
import { adminService } from '@/services/adminService';
import { getApiErrorMessage } from '@/services/api';
import type { AdminTopic, TopicInput } from '@/types/admin';

const IMPORT_EXAMPLE = `{
  "boardCode": "TN_SSLC", "boardName": "Tamil Nadu State Board – Class 10", "grade": 10,
  "subjects": [
    {
      "name": "Mathematics", "nameTa": "கணிதம்", "tileColor": "#3B6EA5",
      "icon": "calculator-variant", "displayOrder": 1,
      "chapters": [
        { "title": "Relations and Functions", "titleTa": "உறவுகளும் சார்புகளும்", "displayOrder": 1,
          "topics": [
            { "title": "Ordered pairs", "titleTa": "வரிசைச் சோடிகள்",
              "learningObjectives": "Define an ordered pair; ...", "displayOrder": 1 }
          ] }
      ]
    }
  ]
}`;

type TopicDialog = { mode: 'edit'; topic: AdminTopic } | { mode: 'create'; chapterId: number; chapterTitle: string };

interface TopicForm {
  title: string;
  titleTa: string;
  learningObjectives: string;
  learningObjectivesTa: string;
}

const EMPTY_FORM: TopicForm = { title: '', titleTa: '', learningObjectives: '', learningObjectivesTa: '' };

export default function CurriculumPage() {
  const queryClient = useQueryClient();
  const { board, boards, tree, setBoardId } = useCurriculumTree();
  const [dialog, setDialog] = useState<TopicDialog | null>(null);
  const [form, setForm] = useState<TopicForm>(EMPTY_FORM);
  const [importOpen, setImportOpen] = useState(false);
  const [importText, setImportText] = useState('');
  const [importError, setImportError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refresh = (): Promise<void> => queryClient.invalidateQueries({ queryKey: ['admin'] });

  const saveTopic = useMutation({
    mutationFn: async (): Promise<void> => {
      if (!dialog) return;
      const input: TopicInput = {
        title: form.title.trim(),
        titleTa: form.titleTa.trim() || undefined,
        learningObjectives: form.learningObjectives.trim(),
        learningObjectivesTa: form.learningObjectivesTa.trim() || undefined,
      };
      if (dialog.mode === 'edit') {
        await adminService.updateTopic(dialog.topic.id, input);
      } else {
        await adminService.createTopic({ ...input, title: form.title.trim(), chapterId: dialog.chapterId });
      }
    },
    onSuccess: async () => {
      setDialog(null);
      await refresh();
    },
  });

  const togglePublish = useMutation({
    mutationFn: (topic: AdminTopic) => adminService.updateTopic(topic.id, { isPublished: !topic.isPublished }),
    onSuccess: refresh,
  });

  const runImport = useMutation({
    mutationFn: (payload: unknown) => adminService.importCurriculum(payload),
    onSuccess: async (result) => {
      setImportOpen(false);
      const count = (r: Record<string, number>): string =>
        Object.entries(r)
          .map(([k, v]) => `${v} ${k}`)
          .join(', ') || 'nothing';
      setNotice(`Import done. Created: ${count(result.created)}. Updated: ${count(result.updated)}.`);
      await refresh();
    },
    onError: (err) => setImportError(getApiErrorMessage(err)),
  });

  const openEdit = (topic: AdminTopic): void => {
    saveTopic.reset();
    setForm({
      title: topic.title,
      titleTa: topic.titleTa ?? '',
      learningObjectives: topic.learningObjectives,
      learningObjectivesTa: topic.learningObjectivesTa ?? '',
    });
    setDialog({ mode: 'edit', topic });
  };

  const openCreate = (chapterId: number, chapterTitle: string): void => {
    saveTopic.reset();
    setForm(EMPTY_FORM);
    setDialog({ mode: 'create', chapterId, chapterTitle });
  };

  const submitImport = (): void => {
    setImportError(null);
    try {
      runImport.mutate(JSON.parse(importText) as unknown);
    } catch {
      setImportError('That is not valid JSON. Check commas and quotes.');
    }
  };

  const toggleVisible = useMutation({
    mutationFn: () => adminService.updateBoard(board?.id ?? 0, { isActive: !board?.isActive }),
    onSuccess: async (updated) => {
      setNotice(updated.isActive ? `${updated.name} is now visible to students.` : `${updated.name} is now hidden from new students.`);
      await refresh();
    },
  });

  const error = boards.error ?? tree.error ?? toggleVisible.error;

  return (
    <PageWrapper
      title="Curriculum"
      description={
        board
          ? `${board.name} — ${board.isActive ? 'visible to students' : 'hidden from students'}. Subjects, chapters and topics in English and Tamil.`
          : undefined
      }
      actions={
        <HStack gap={2} wrap="wrap">
          <BoardSwitcher boards={boards.data} value={board?.id} onChange={setBoardId} />
          {board && (
            <Button variant="outline" onClick={() => toggleVisible.mutate()} loading={toggleVisible.isPending}>
              {board.isActive ? 'Hide from students' : 'Show to students'}
            </Button>
          )}
          <Button variant="outline" onClick={() => setImportOpen(true)} disabled={!board}>
            <FiUpload /> Import syllabus (JSON)
          </Button>
        </HStack>
      }
    >
      <Stack gap={4}>
        {notice && (
          <Text role="status" bg="success.subtle" color="fg" borderRadius="md" px={3} py={2} fontSize="sm">
            {notice}
          </Text>
        )}
        {(boards.isPending || tree.isPending) && !error && <LoadingState />}
        {error && <ErrorState message={getApiErrorMessage(error)} onRetry={() => void refresh()} />}
        {tree.data && tree.data.subjects.length === 0 && (
          <Card>
            <EmptyState icon={FiBookOpen} title="No subjects yet" description="Use “Import syllabus” to add the board's subjects." />
          </Card>
        )}

        {tree.data?.subjects.map((subject) => (
          <Card key={subject.id} borderLeftWidth="6px" borderLeftColor={subject.tileColor}>
            <Stack gap={4}>
              <HStack justify="space-between" wrap="wrap">
                <Text fontSize="lg" fontWeight="semibold" color="fg">
                  {subject.displayOrder}. {subject.name}
                  {subject.nameTa && (
                    <Text as="span" color="fgMuted" fontWeight="normal">
                      {' '}
                      · {subject.nameTa}
                    </Text>
                  )}
                </Text>
              </HStack>

              {subject.chapters.map((chapter) => (
                <Box key={chapter.id}>
                  <HStack justify="space-between" mb={2} wrap="wrap">
                    <Text fontWeight="medium" color="fg">
                      Chapter {chapter.displayOrder}: {chapter.title}
                      {chapter.titleTa && <Text as="span" color="fgMuted">{` · ${chapter.titleTa}`}</Text>}
                    </Text>
                    <Button size="xs" variant="ghost" color="primary" onClick={() => openCreate(chapter.id, chapter.title)}>
                      <FiPlus /> Add topic
                    </Button>
                  </HStack>
                  <Table.ScrollArea borderWidth="1px" borderColor="border" borderRadius="md">
                    <Table.Root size="sm">
                      <Table.Header>
                        <Table.Row bg="bg">
                          <Table.ColumnHeader w="48px">#</Table.ColumnHeader>
                          <Table.ColumnHeader>Topic</Table.ColumnHeader>
                          <Table.ColumnHeader>Lessons</Table.ColumnHeader>
                          <Table.ColumnHeader>Questions</Table.ColumnHeader>
                          <Table.ColumnHeader>Status</Table.ColumnHeader>
                          <Table.ColumnHeader textAlign="end">Actions</Table.ColumnHeader>
                        </Table.Row>
                      </Table.Header>
                      <Table.Body>
                        {chapter.topics.map((topic) => (
                          <Table.Row key={topic.id}>
                            <Table.Cell>{topic.displayOrder}</Table.Cell>
                            <Table.Cell>
                              <Text color="fg">{topic.title}</Text>
                              {topic.titleTa && (
                                <Text fontSize="xs" color="fgMuted">
                                  {topic.titleTa}
                                </Text>
                              )}
                            </Table.Cell>
                            <Table.Cell>{topic.lessonCount}</Table.Cell>
                            <Table.Cell>{topic.questionCount}</Table.Cell>
                            <Table.Cell>
                              <Badge colorPalette={topic.isPublished ? 'green' : 'gray'} variant="subtle">
                                {topic.isPublished ? 'Published' : 'Hidden'}
                              </Badge>
                            </Table.Cell>
                            <Table.Cell textAlign="end">
                              <HStack justify="flex-end" gap={1}>
                                <Button size="xs" variant="ghost" onClick={() => openEdit(topic)} aria-label={`Edit ${topic.title}`}>
                                  <FiEdit2 /> Edit
                                </Button>
                                <Button
                                  size="xs"
                                  variant="outline"
                                  onClick={() => togglePublish.mutate(topic)}
                                  loading={togglePublish.isPending && togglePublish.variables?.id === topic.id}
                                >
                                  {topic.isPublished ? 'Hide' : 'Publish'}
                                </Button>
                              </HStack>
                            </Table.Cell>
                          </Table.Row>
                        ))}
                      </Table.Body>
                    </Table.Root>
                  </Table.ScrollArea>
                </Box>
              ))}
            </Stack>
          </Card>
        ))}
      </Stack>

      <FormDialog
        open={dialog !== null}
        title={dialog?.mode === 'edit' ? 'Edit topic' : `New topic in “${dialog?.mode === 'create' ? dialog.chapterTitle : ''}”`}
        loading={saveTopic.isPending}
        error={saveTopic.error ? getApiErrorMessage(saveTopic.error) : null}
        size="lg"
        onSubmit={() => {
          if (form.title.trim()) saveTopic.mutate();
        }}
        onClose={() => setDialog(null)}
      >
        <Field.Root required>
          <Field.Label>Title (English)</Field.Label>
          <Input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
        </Field.Root>
        <Field.Root>
          <Field.Label>Title (Tamil)</Field.Label>
          <Input value={form.titleTa} onChange={(e) => setForm({ ...form, titleTa: e.target.value })} />
        </Field.Root>
        <Field.Root>
          <Field.Label>Learning objectives (English)</Field.Label>
          <Textarea
            rows={4}
            value={form.learningObjectives}
            onChange={(e) => setForm({ ...form, learningObjectives: e.target.value })}
          />
          <Field.HelperText>The AI uses these to stay within the syllabus. One per line.</Field.HelperText>
        </Field.Root>
        <Field.Root>
          <Field.Label>Learning objectives (Tamil)</Field.Label>
          <Textarea
            rows={3}
            value={form.learningObjectivesTa}
            onChange={(e) => setForm({ ...form, learningObjectivesTa: e.target.value })}
          />
        </Field.Root>
      </FormDialog>

      <FormDialog
        open={importOpen}
        title="Import syllabus (JSON)"
        submitLabel="Import"
        loading={runImport.isPending}
        error={importError}
        size="xl"
        onSubmit={submitImport}
        onClose={() => setImportOpen(false)}
      >
        <Text fontSize="sm" color="fgMuted">
          Items are matched by <b>displayOrder</b> inside their parent: existing ones are updated, new ones are
          created, nothing is deleted. Tile colours must come from the approved palette.
        </Text>
        <Textarea
          rows={14}
          fontFamily="mono"
          fontSize="xs"
          placeholder={IMPORT_EXAMPLE}
          value={importText}
          onChange={(e) => setImportText(e.target.value)}
        />
        <PrimaryButton type="button" variant="outline" bg="surface" color="primary" onClick={() => setImportText(IMPORT_EXAMPLE)}>
          Insert example
        </PrimaryButton>
      </FormDialog>
    </PageWrapper>
  );
}
