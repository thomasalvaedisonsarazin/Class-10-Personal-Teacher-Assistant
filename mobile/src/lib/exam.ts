import type { ExamOverview, ModelPaperSummary, PaperStatus } from '@/types/exam';

/** Statuses after the answers were submitted (the answer key is open). */
const SUBMITTED: readonly PaperStatus[] = ['grading', 'graded', 'grading_failed'];

/** "3 hours", "1 hour 30 minutes". */
export function durationLabel(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  const parts: string[] = [];
  if (hours) parts.push(`${hours} hour${hours === 1 ? '' : 's'}`);
  if (rest) parts.push(`${rest} minutes`);
  return parts.join(' ');
}

export function isSubmitted(status: PaperStatus): boolean {
  return SUBMITTED.includes(status);
}

/** The paper is being written or marked: keep checking the server. */
export function isWorking(status: PaperStatus): boolean {
  return status === 'generating' || status === 'grading';
}

/** Photos can be uploaded for a ready paper, or again after a failed marking. */
export function canUploadAnswers(status: PaperStatus): boolean {
  return status === 'ready' || status === 'grading_failed';
}

/** A full-subject test needs a plan and enough passed topics. */
export function subjectTestBlocker(overview: ExamOverview): string | null {
  if (overview.planRequired) return 'Get a plan to take full-subject tests.';
  const missing = overview.minTopics - overview.completedTopics;
  if (missing > 0) {
    return `Pass ${missing} more topic test${missing === 1 ? '' : 's'} in this subject to unlock it.`;
  }
  return null;
}

export function paperStatusLabel(paper: ModelPaperSummary): string {
  switch (paper.status) {
    case 'generating':
      return 'Being written…';
    case 'ready':
      return 'Ready to write';
    case 'grading':
      return 'Being marked…';
    case 'graded':
      return `${formatMarks(paper.score ?? 0)} / ${paper.totalMarks} marks`;
    case 'generation_failed':
      return 'Could not be written';
    case 'grading_failed':
      return 'Upload photos again';
  }
}

/** 7 → "7", 7.5 → "7.5". */
export function formatMarks(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/** Safe file name for a shared PDF (keeps Tamil letters). */
export function pdfFileName(name: string): string {
  const cleaned = name.replace(/[^\w\-.஀-௿]+/g, '-').replace(/-+/g, '-');
  return cleaned.toLowerCase().endsWith('.pdf') ? cleaned : `${cleaned}.pdf`;
}
