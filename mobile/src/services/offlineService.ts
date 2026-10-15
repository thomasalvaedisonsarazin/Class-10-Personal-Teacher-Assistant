import { Directory, File, Paths } from 'expo-file-system';
import { Platform } from 'react-native';

import type { Lesson } from '@/types/lessons';

/** A lesson saved on the phone; its URLs point at local files. */
export interface DownloadedLesson {
  lesson: Lesson;
  topicTitle: string;
  subjectName: string;
  downloadedAt: string;
  sizeBytes: number;
}

/** Downloads need a real file system (Android/iOS), not the web preview. */
export const offlineSupported = Platform.OS !== 'web';

const ROOT_NAME = 'offline-lessons';
const META = 'meta.json';

function root(): Directory {
  return new Directory(Paths.document, ROOT_NAME);
}

function lessonDir(lessonId: number): Directory {
  return new Directory(root(), String(lessonId));
}

function sizeOf(file: File): number {
  return file.exists ? (file.size ?? 0) : 0;
}

/**
 * Save a lesson's audio, pictures and slides for offline use (no video, to save space).
 * Replaces an earlier copy of the same lesson.
 */
export async function downloadLesson(
  lesson: Lesson,
  topicTitle: string,
  subjectName: string,
): Promise<DownloadedLesson> {
  if (!offlineSupported) throw new Error('Downloads work in the phone app, not in the browser.');
  if (!lesson.audioUrl) throw new Error('This lesson has no audio to download yet.');

  const dir = lessonDir(lesson.id);
  if (dir.exists) dir.delete();
  dir.create({ intermediates: true, idempotent: true });
  try {
    const audio = await File.downloadFileAsync(lesson.audioUrl, new File(dir, 'audio.mp3'), { idempotent: true });
    let size = sizeOf(audio);
    const slides = [];
    for (const [i, slide] of lesson.slides.entries()) {
      let imageUrl: string | null = null;
      if (slide.imageUrl) {
        try {
          const picture = await File.downloadFileAsync(slide.imageUrl, new File(dir, `scene-${i + 1}.jpg`), {
            idempotent: true,
          });
          imageUrl = picture.uri;
          size += sizeOf(picture);
        } catch {
          imageUrl = null; // a missing picture must not fail the whole download
        }
      }
      slides.push({ ...slide, imageUrl });
    }
    const saved: DownloadedLesson = {
      lesson: { ...lesson, audioUrl: audio.uri, videoUrl: null, slides },
      topicTitle,
      subjectName,
      downloadedAt: new Date().toISOString(),
      sizeBytes: size,
    };
    new File(dir, META).write(JSON.stringify(saved));
    return saved;
  } catch (err) {
    if (dir.exists) dir.delete();
    throw err instanceof Error ? err : new Error('Download failed. Check your connection and try again.');
  }
}

async function readMeta(dir: Directory): Promise<DownloadedLesson | null> {
  const meta = new File(dir, META);
  if (!meta.exists) return null;
  try {
    return JSON.parse(await meta.text()) as DownloadedLesson;
  } catch {
    return null;
  }
}

/** Every saved lesson, newest first. */
export async function listDownloads(): Promise<DownloadedLesson[]> {
  if (!offlineSupported || !root().exists) return [];
  const items: DownloadedLesson[] = [];
  for (const entry of root().list()) {
    if (entry instanceof Directory) {
      const meta = await readMeta(entry);
      if (meta) items.push(meta);
    }
  }
  return items.sort((a, b) => b.downloadedAt.localeCompare(a.downloadedAt));
}

/** The most recent saved lesson for a topic (used when the phone is offline). */
export async function downloadForTopic(topicId: number): Promise<DownloadedLesson | null> {
  const all = await listDownloads();
  return all.find((d) => d.lesson.topicId === topicId) ?? null;
}

export async function getDownload(lessonId: number): Promise<DownloadedLesson | null> {
  if (!offlineSupported) return null;
  const dir = lessonDir(lessonId);
  return dir.exists ? readMeta(dir) : null;
}

export function deleteDownload(lessonId: number): void {
  if (!offlineSupported) return;
  const dir = lessonDir(lessonId);
  if (dir.exists) dir.delete();
}

/** "3.4 MB" style size label. */
export function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
