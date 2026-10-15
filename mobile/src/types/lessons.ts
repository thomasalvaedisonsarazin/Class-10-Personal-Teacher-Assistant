/** Lesson + AI generation job types (API JSON is camelCase). */
import type { LessonLanguage, Medium } from './api';

export type LessonStyle =
  | 'base'
  | 'analogy'
  | 'step_by_step'
  | 'story'
  | 'real_life'
  | 'worked_example'
  | 'visual';

export type LessonStatus = 'pending' | 'generating' | 'audio_ready' | 'ready' | 'failed';

export type JobStatus = 'queued' | 'running' | 'done' | 'failed';

export interface Slide {
  heading: string;
  bullets: string[];
  narration: string;
  /** A single emoji that pictures the scene (may be empty). */
  emoji: string;
  /** Storybook illustration for this scene (null if none). */
  imageUrl: string | null;
  /** When this slide starts in the lesson audio (seconds). */
  startSec: number;
}

export interface Lesson {
  id: number;
  topicId: number;
  medium: Medium;
  language: LessonLanguage;
  style: LessonStyle;
  styleLabel: string;
  title: string;
  summary: string;
  slides: Slide[];
  audioUrl: string | null;
  videoUrl: string | null;
  durationSec: number | null;
  status: LessonStatus;
}

export interface GenerationJob {
  id: number;
  status: JobStatus;
  style: LessonStyle | null;
  styleLabel: string | null;
  /** Friendly message when the job failed. */
  error: string | null;
  /** Present once the audio is ready. */
  lesson: Lesson | null;
}

/** 200 → `ready` with a lesson; 202 → `generating` with a job to poll. */
export interface LessonResponse {
  state: 'ready' | 'generating';
  lesson: Lesson | null;
  job: GenerationJob | null;
}
