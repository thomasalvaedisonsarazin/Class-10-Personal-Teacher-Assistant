import { screen } from '@testing-library/react';
import { Route, Routes } from 'react-router-dom';
import { describe, expect, it } from 'vitest';

import { ProtectedRoute } from '@/components/auth/ProtectedRoute';
import { renderWithProviders } from '@/test/renderWithProviders';
import type { User } from '@/types/api';

function TestRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<p>Login screen</p>} />
      <Route element={<ProtectedRoute />}>
        <Route path="/admin" element={<p>Admin dashboard</p>} />
      </Route>
    </Routes>
  );
}

const baseUser: User = {
  id: 1,
  email: 'admin@example.com',
  fullName: 'Admin User',
  avatarUrl: null,
  role: 'admin',
  boardId: null,
  medium: 'en',
};

describe('ProtectedRoute', () => {
  it('redirects to /login when signed out', () => {
    renderWithProviders(<TestRoutes />, {
      route: '/admin',
      auth: { status: 'unauthenticated', user: null },
    });

    expect(screen.getByText('Login screen')).toBeInTheDocument();
    expect(screen.queryByText('Admin dashboard')).not.toBeInTheDocument();
  });

  it('redirects to /login when the user is not an admin', () => {
    renderWithProviders(<TestRoutes />, {
      route: '/admin',
      auth: { status: 'authenticated', user: { ...baseUser, role: 'student' } },
    });

    expect(screen.getByText('Login screen')).toBeInTheDocument();
  });

  it('renders the protected page for a signed-in admin', () => {
    renderWithProviders(<TestRoutes />, {
      route: '/admin',
      auth: { status: 'authenticated', user: baseUser },
    });

    expect(screen.getByText('Admin dashboard')).toBeInTheDocument();
  });
});
