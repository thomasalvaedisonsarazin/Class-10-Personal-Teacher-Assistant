import type { Streak, SubjectDetail, SubjectSummary, TopicDetail, TopicItem } from '@/types/curriculum';

import { api } from './api';

export const curriculumService = {
  async getSubjects(): Promise<SubjectSummary[]> {
    const { data } = await api.get<SubjectSummary[]>('/subjects');
    return data;
  },

  async getSubject(subjectId: number): Promise<SubjectDetail> {
    const { data } = await api.get<SubjectDetail>(`/subjects/${subjectId}`);
    return data;
  },

  /** Rejects with 403 `topic_locked` when the previous topic is not passed yet. */
  async getTopic(topicId: number): Promise<TopicDetail> {
    const { data } = await api.get<TopicDetail>(`/topics/${topicId}`);
    return data;
  },

  async getStreak(): Promise<Streak> {
    const { data } = await api.get<Streak>('/streak');
    return data;
  },

  async startTopic(topicId: number): Promise<TopicItem> {
    const { data } = await api.post<TopicItem>(`/topics/${topicId}/start`);
    return data;
  },
};
