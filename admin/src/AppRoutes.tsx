import { lazy, Suspense } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { AdminLayout } from '@/components/layout/AdminLayout';
import { LoadingState } from '@/components/ui/LoadingState';

const LoginPage = lazy(() => import('@/pages/LoginPage'));
const DashboardPage = lazy(() => import('@/pages/DashboardPage'));
const CurriculumPage = lazy(() => import('@/pages/CurriculumPage'));
const ContentPage = lazy(() => import('@/pages/ContentPage'));
const QuestionsPage = lazy(() => import('@/pages/QuestionsPage'));
const UsersPage = lazy(() => import('@/pages/UsersPage'));
const PartnersPage = lazy(() => import('@/pages/PartnersPage'));
const PayoutsPage = lazy(() => import('@/pages/PayoutsPage'));
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'));

export function AppRoutes() {
  return (
    <Suspense fallback={<LoadingState fullPage />}>
      <Routes>
        <Route path="/" element={<Navigate to="/admin" replace />} />
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedRoute />}>
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="curriculum" element={<CurriculumPage />} />
            <Route path="content" element={<ContentPage />} />
            <Route path="questions" element={<QuestionsPage />} />
            <Route path="users" element={<UsersPage />} />
            <Route path="partners" element={<PartnersPage />} />
            <Route path="payouts" element={<PayoutsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
