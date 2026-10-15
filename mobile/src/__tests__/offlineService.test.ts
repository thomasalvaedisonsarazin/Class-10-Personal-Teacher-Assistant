import { beforeEach, describe, expect, it, jest } from '@jest/globals';

import type { Lesson } from '@/types/lessons';

/** In-memory stand-in for the phone's file system (expo-file-system). */
const mockDisk = new Map<string, string>();
const mockFailing = new Set<string>();

function mockJoin(parts: (string | { uri: string })[]): string {
  return parts.map((p) => (typeof p === 'string' ? p : p.uri)).join('/');
}

jest.mock('expo-file-system', () => {
  class Directory {
    uri: string;
    constructor(...parts: (string | { uri: string })[]) {
      this.uri = mockJoin(parts);
    }
    get exists(): boolean {
      return mockDisk.has(`${this.uri}/`) || [...mockDisk.keys()].some((k) => k.startsWith(`${this.uri}/`));
    }
    create(): void {
      mockDisk.set(`${this.uri}/`, '');
    }
    delete(): void {
      for (const key of [...mockDisk.keys()]) if (key.startsWith(`${this.uri}/`)) mockDisk.delete(key);
    }
    list(): Directory[] {
      const names = new Set<string>();
      for (const key of mockDisk.keys()) {
        if (key.startsWith(`${this.uri}/`)) {
          const rest = key.slice(this.uri.length + 1).split('/');
          if (rest.length > 1 && rest[0]) names.add(rest[0]);
        }
      }
      return [...names].map((n) => new Directory(this.uri, n));
    }
  }
  class File {
    uri: string;
    constructor(...parts: (string | { uri: string })[]) {
      this.uri = mockJoin(parts);
    }
    get exists(): boolean {
      return mockDisk.has(this.uri);
    }
    get size(): number {
      return (mockDisk.get(this.uri) ?? '').length;
    }
    write(content: string): void {
      mockDisk.set(this.uri, content);
    }
    async text(): Promise<string> {
      return mockDisk.get(this.uri) ?? '';
    }
    delete(): void {
      mockDisk.delete(this.uri);
    }
    static async downloadFileAsync(url: string, destination: File): Promise<File> {
      if (mockFailing.has(url)) throw new Error('network');
      destination.write(`bytes-of-${url}`);
      return destination;
    }
  }
  return { Directory, File, Paths: { document: { uri: 'file:///docs' } } };
});

// Imported after the mocks.
// eslint-disable-next-line import/first
import { deleteDownload, downloadForTopic, downloadLesson, listDownloads } from '@/services/offlineService';

function lesson(id: number, topicId: number): Lesson {
  return {
    id,
    topicId,
    medium: 'en',
    language: 'en',
    style: 'story',
    styleLabel: 'Story',
    title: 'Inertia',
    summary: '',
    slides: [
      { heading: 'Bus', bullets: ['a'], narration: 'n', emoji: '🚌', imageUrl: 'https://x/scene-1.jpg', startSec: 0 },
      { heading: 'Ball', bullets: ['b'], narration: 'n', emoji: '⚽', imageUrl: 'https://x/scene-2.jpg', startSec: 5 },
    ],
    audioUrl: 'https://x/audio.mp3',
    videoUrl: 'https://x/video.mp4',
    durationSec: 10,
    status: 'ready',
  };
}

describe('offline downloads', () => {
  beforeEach(() => {
    mockDisk.clear();
    mockFailing.clear();
  });

  it('saves audio and pictures and points the lesson at local files', async () => {
    const saved = await downloadLesson(lesson(5, 7), 'Inertia', 'Science');
    expect(saved.lesson.audioUrl).toBe('file:///docs/offline-lessons/5/audio.mp3');
    expect(saved.lesson.slides.map((s) => s.imageUrl)).toEqual([
      'file:///docs/offline-lessons/5/scene-1.jpg',
      'file:///docs/offline-lessons/5/scene-2.jpg',
    ]);
    expect(saved.lesson.videoUrl).toBeNull(); // video is not downloaded (saves space)
    expect(saved.sizeBytes).toBeGreaterThan(0);
  });

  it('keeps going when one picture fails, and lists/finds/deletes downloads', async () => {
    mockFailing.add('https://x/scene-2.jpg');
    await downloadLesson(lesson(5, 7), 'Inertia', 'Science');
    await downloadLesson(lesson(9, 8), 'Velocity', 'Science');

    const all = await listDownloads();
    expect(all.map((d) => d.lesson.id).sort()).toEqual([5, 9]);
    const forTopic = await downloadForTopic(7);
    expect(forTopic?.lesson.slides[1].imageUrl).toBeNull();

    deleteDownload(5);
    expect((await listDownloads()).map((d) => d.lesson.id)).toEqual([9]);
  });

  it('cleans up when the audio download fails', async () => {
    mockFailing.add('https://x/audio.mp3');
    await expect(downloadLesson(lesson(5, 7), 'Inertia', 'Science')).rejects.toThrow();
    expect(await listDownloads()).toEqual([]);
  });
});
