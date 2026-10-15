import type { ChildReport, ChildSummary, Invite, StudentLinks } from '@/types/parent';

import { api } from './api';

export const parentService = {
  /** Student: get a code to share with a parent. */
  async createInvite(): Promise<Invite> {
    const { data } = await api.post<Invite>('/parent-links/invite');
    return data;
  },

  /** Student: parents who can see my progress. */
  async myParents(): Promise<StudentLinks> {
    const { data } = await api.get<StudentLinks>('/parent-links');
    return data;
  },

  /** Student: remove a parent's access. */
  async removeParent(linkId: number): Promise<void> {
    await api.delete(`/parent-links/${linkId}`);
  },

  /** Parent: link to a child with their code. */
  async linkChild(code: string): Promise<ChildSummary> {
    const { data } = await api.post<ChildSummary>('/parent/links', { code });
    return data;
  },

  async children(): Promise<ChildSummary[]> {
    const { data } = await api.get<ChildSummary[]>('/parent/children');
    return data;
  },

  async childReport(studentId: number): Promise<ChildReport> {
    const { data } = await api.get<ChildReport>(`/parent/children/${studentId}`);
    return data;
  },
};
