import { describe, expect, it } from '@jest/globals';

import {
  canUploadAnswers,
  durationLabel,
  formatMarks,
  isSubmitted,
  isWorking,
  paperStatusLabel,
  pdfFileName,
  subjectTestBlocker,
} from '@/lib/exam';
import type { ExamOverview, ModelPaperSummary } from '@/types/exam';

const overview = (fields: Partial<ExamOverview>): ExamOverview => ({
  subjectId: 1,
  planRequired: false,
  completedTopics: 3,
  minTopics: 3,
  recentTests: [],
  papers: [],
  papersLeftToday: 3,
  fullPattern: { totalMarks: 100, durationMinutes: 180 },
  unitPattern: { totalMarks: 50, durationMinutes: 90 },
  ...fields,
});

const paper = (fields: Partial<ModelPaperSummary>): ModelPaperSummary => ({
  id: 1,
  subjectId: 1,
  title: 'Maths · Full syllabus',
  scope: 'full',
  chapterIds: [],
  status: 'ready',
  totalMarks: 100,
  durationMinutes: 180,
  score: null,
  createdAt: '2026-10-22T10:00:00Z',
  ...fields,
});

describe('exam helpers', () => {
  it('describes exam time', () => {
    expect(durationLabel(180)).toBe('3 hours');
    expect(durationLabel(90)).toBe('1 hour 30 minutes');
    expect(durationLabel(45)).toBe('45 minutes');
  });

  it('opens the answer key only after submitting', () => {
    expect(isSubmitted('ready')).toBe(false);
    expect(isSubmitted('grading')).toBe(true);
    expect(isSubmitted('graded')).toBe(true);
    expect(isSubmitted('grading_failed')).toBe(true);
  });

  it('allows uploading for a ready paper or after a failed marking', () => {
    expect(canUploadAnswers('ready')).toBe(true);
    expect(canUploadAnswers('grading_failed')).toBe(true);
    expect(canUploadAnswers('graded')).toBe(false);
    expect(isWorking('generating')).toBe(true);
    expect(isWorking('graded')).toBe(false);
  });

  it('explains why a subject test is not open yet', () => {
    expect(subjectTestBlocker(overview({}))).toBeNull();
    expect(subjectTestBlocker(overview({ completedTopics: 2 }))).toContain('1 more topic test ');
    expect(subjectTestBlocker(overview({ completedTopics: 0 }))).toContain('3 more topic tests');
    expect(subjectTestBlocker(overview({ planRequired: true }))).toContain('plan');
  });

  it('labels papers by status', () => {
    expect(paperStatusLabel(paper({ status: 'graded', score: 72.5 }))).toBe('72.5 / 100 marks');
    expect(paperStatusLabel(paper({ status: 'generating' }))).toBe('Being written…');
    expect(formatMarks(36)).toBe('36');
  });

  it('makes safe PDF file names and keeps Tamil letters', () => {
    expect(pdfFileName('Maths model paper 3')).toBe('Maths-model-paper-3.pdf');
    expect(pdfFileName('கணிதம்-answer-key-4.pdf')).toBe('கணிதம்-answer-key-4.pdf');
    expect(pdfFileName('a/b:c')).toBe('a-b-c.pdf');
  });
});
