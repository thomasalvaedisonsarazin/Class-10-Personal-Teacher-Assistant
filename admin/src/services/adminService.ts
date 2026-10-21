import api from '@/services/api';
import type { Medium, UserRole } from '@/types/api';
import type {
  AdminBoard,
  AdminLesson,
  AdminPage,
  AdminPartner,
  AdminPayout,
  AdminQuestion,
  AdminStats,
  AdminUser,
  AdminUserUpdate,
  CurriculumTree,
  ImportResult,
  LessonLanguage,
  LessonStyle,
  PayoutStatus,
  QuestionInput,
  TopicInput,
} from '@/types/admin';

export interface PageQuery {
  page?: number;
  size?: number;
}

export const adminService = {
  async partners(): Promise<AdminPartner[]> {
    return (await api.get<AdminPartner[]>('/admin/partners')).data;
  },

  async createPartner(input: { name: string; email: string; commissionPct?: number }): Promise<AdminPartner> {
    return (await api.post<AdminPartner>('/admin/partners', input)).data;
  },

  async updatePartner(id: number, input: { name?: string; commissionPct?: number; isActive?: boolean }): Promise<AdminPartner> {
    return (await api.patch<AdminPartner>(`/admin/partners/${id}`, input)).data;
  },

  async payouts(status?: PayoutStatus): Promise<AdminPayout[]> {
    return (await api.get<AdminPayout[]>('/admin/payouts', { params: status ? { status } : undefined })).data;
  },

  async decidePayout(
    id: number,
    action: 'approve' | 'paid' | 'reject',
    input: { reference?: string; note?: string } = {},
  ): Promise<AdminPayout> {
    return (await api.post<AdminPayout>(`/admin/payouts/${id}/${action}`, input)).data;
  },

  async stats(): Promise<AdminStats> {
    return (await api.get<AdminStats>('/admin/stats')).data;
  },

  async boards(): Promise<AdminBoard[]> {
    return (await api.get<AdminBoard[]>('/admin/boards')).data;
  },

  /** Show / hide a class to students, or rename it. */
  async updateBoard(boardId: number, input: { isActive?: boolean; name?: string }): Promise<AdminBoard> {
    return (await api.patch<AdminBoard>(`/admin/boards/${boardId}`, input)).data;
  },

  async curriculum(boardId: number): Promise<CurriculumTree> {
    return (await api.get<CurriculumTree>(`/admin/boards/${boardId}/curriculum`)).data;
  },

  async importCurriculum(payload: unknown): Promise<ImportResult> {
    return (await api.post<ImportResult>('/admin/curriculum/import', payload)).data;
  },

  async createSubject(input: { boardId: number; name: string; nameTa?: string; tileColor: string; icon: string }): Promise<void> {
    await api.post('/admin/subjects', input);
  },

  async createChapter(input: { subjectId: number; title: string; titleTa?: string }): Promise<void> {
    await api.post('/admin/chapters', input);
  },

  async createTopic(input: TopicInput & { chapterId: number; title: string }): Promise<void> {
    await api.post('/admin/topics', input);
  },

  async updateTopic(topicId: number, input: TopicInput): Promise<void> {
    await api.patch(`/admin/topics/${topicId}`, input);
  },

  async lessons(query: PageQuery & { topicId?: number; flagged?: boolean }): Promise<AdminPage<AdminLesson>> {
    return (await api.get<AdminPage<AdminLesson>>('/admin/lessons', { params: query })).data;
  },

  async flagLesson(lessonId: number, isFlagged: boolean): Promise<AdminLesson> {
    return (await api.patch<AdminLesson>(`/admin/lessons/${lessonId}`, { isFlagged })).data;
  },

  async uploadLesson(input: {
    topicId: number;
    medium: Medium;
    language: LessonLanguage;
    style: LessonStyle;
    title: string;
    file: File;
  }): Promise<AdminLesson> {
    const form = new FormData();
    form.append('file', input.file);
    form.append('medium', input.medium);
    form.append('language', input.language);
    form.append('style', input.style);
    form.append('title', input.title);
    const { data } = await api.post<AdminLesson>(`/admin/topics/${input.topicId}/lessons`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300_000,
    });
    return data;
  },

  async questions(
    query: PageQuery & { topicId?: number; medium?: Medium; flagged?: boolean; approved?: boolean },
  ): Promise<AdminPage<AdminQuestion>> {
    return (await api.get<AdminPage<AdminQuestion>>('/admin/questions', { params: query })).data;
  },

  async createQuestion(input: QuestionInput): Promise<AdminQuestion> {
    return (await api.post<AdminQuestion>('/admin/questions', input)).data;
  },

  async updateQuestion(
    questionId: number,
    input: Partial<Pick<AdminQuestion, 'isApproved' | 'isFlagged' | 'stem' | 'correctAnswer' | 'explanation'>>,
  ): Promise<AdminQuestion> {
    return (await api.patch<AdminQuestion>(`/admin/questions/${questionId}`, input)).data;
  },

  async users(query: PageQuery & { role?: UserRole; q?: string }): Promise<AdminPage<AdminUser>> {
    return (await api.get<AdminPage<AdminUser>>('/admin/users', { params: query })).data;
  },

  async updateUser(userId: number, input: AdminUserUpdate): Promise<AdminUser> {
    return (await api.patch<AdminUser>(`/admin/users/${userId}`, input)).data;
  },
};
