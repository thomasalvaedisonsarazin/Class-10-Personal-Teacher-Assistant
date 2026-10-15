import { Badge, Button, HStack, Input, NativeSelect, Stack, Table, Text } from '@chakra-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FiUsers } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { useAuth } from '@/hooks/useAuth';
import { adminService } from '@/services/adminService';
import { getApiErrorMessage } from '@/services/api';
import type { UserRole } from '@/types/api';
import type { AdminUser } from '@/types/admin';

const PAGE_SIZE = 20;
const ROLES: UserRole[] = ['student', 'parent', 'admin'];

export default function UsersPage() {
  const queryClient = useQueryClient();
  const { user: me } = useAuth();
  const [search, setSearch] = useState('');
  const [query, setQuery] = useState('');
  const [role, setRole] = useState<UserRole | ''>('');
  const [page, setPage] = useState(1);
  const [confirm, setConfirm] = useState<AdminUser | null>(null);

  const users = useQuery({
    queryKey: ['admin', 'users', query, role, page],
    queryFn: () => adminService.users({ q: query || undefined, role: role || undefined, page, size: PAGE_SIZE }),
  });

  const update = useMutation({
    mutationFn: ({ id, ...input }: { id: number; role?: UserRole; isActive?: boolean }) => adminService.updateUser(id, input),
    onSuccess: async () => {
      setConfirm(null);
      await queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
  });

  const totalPages = users.data ? Math.max(1, Math.ceil(users.data.total / PAGE_SIZE)) : 1;

  return (
    <PageWrapper title="Users" description="Students, parents and admins.">
      <Stack gap={4}>
        <HStack
          as="form"
          gap={2}
          wrap="wrap"
          onSubmit={(e) => {
            e.preventDefault();
            setQuery(search.trim());
            setPage(1);
          }}
        >
          <Input maxW="320px" bg="surface" placeholder="Search name or email" value={search} onChange={(e) => setSearch(e.target.value)} />
          <NativeSelect.Root maxW="180px">
            <NativeSelect.Field
              bg="surface"
              value={role}
              onChange={(e) => {
                setRole(ROLES.find((r) => r === e.target.value) ?? '');
                setPage(1);
              }}
            >
              <option value="">All roles</option>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {r}
                </option>
              ))}
            </NativeSelect.Field>
            <NativeSelect.Indicator />
          </NativeSelect.Root>
          <Button type="submit" variant="outline">
            Search
          </Button>
        </HStack>

        {update.isError && (
          <Text role="alert" color="danger" fontSize="sm">
            {getApiErrorMessage(update.error)}
          </Text>
        )}
        {users.isPending && <LoadingState />}
        {users.isError && <ErrorState message={getApiErrorMessage(users.error)} onRetry={() => void users.refetch()} />}
        {users.data && users.data.items.length === 0 && (
          <Card>
            <EmptyState icon={FiUsers} title="No users found" />
          </Card>
        )}
        {users.data && users.data.items.length > 0 && (
          <Card p={0}>
            <Table.ScrollArea>
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row bg="bg">
                    <Table.ColumnHeader>Name</Table.ColumnHeader>
                    <Table.ColumnHeader>Email</Table.ColumnHeader>
                    <Table.ColumnHeader>Role</Table.ColumnHeader>
                    <Table.ColumnHeader>Medium</Table.ColumnHeader>
                    <Table.ColumnHeader>Status</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Action</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {users.data.items.map((u) => {
                    const isMe = u.id === me?.id;
                    return (
                      <Table.Row key={u.id}>
                        <Table.Cell>{u.fullName ?? '—'}</Table.Cell>
                        <Table.Cell>{u.email}</Table.Cell>
                        <Table.Cell>
                          <NativeSelect.Root size="xs" maxW="120px" disabled={isMe}>
                            <NativeSelect.Field
                              value={u.role}
                              onChange={(e) => {
                                const next = ROLES.find((r) => r === e.target.value);
                                if (next) update.mutate({ id: u.id, role: next });
                              }}
                            >
                              {ROLES.map((r) => (
                                <option key={r} value={r}>
                                  {r}
                                </option>
                              ))}
                            </NativeSelect.Field>
                            <NativeSelect.Indicator />
                          </NativeSelect.Root>
                        </Table.Cell>
                        <Table.Cell>{u.medium === 'ta' ? 'Tamil' : u.medium === 'en' ? 'English' : '—'}</Table.Cell>
                        <Table.Cell>
                          <Badge variant="subtle" colorPalette={u.isActive ? 'green' : 'gray'}>
                            {u.isActive ? 'Active' : 'Disabled'}
                          </Badge>
                        </Table.Cell>
                        <Table.Cell textAlign="end">
                          {isMe ? (
                            <Text fontSize="xs" color="fgMuted">
                              You
                            </Text>
                          ) : (
                            <Button
                              size="xs"
                              variant="outline"
                              onClick={() => (u.isActive ? setConfirm(u) : update.mutate({ id: u.id, isActive: true }))}
                            >
                              {u.isActive ? 'Disable' : 'Enable'}
                            </Button>
                          )}
                        </Table.Cell>
                      </Table.Row>
                    );
                  })}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
          </Card>
        )}
        {users.data && totalPages > 1 && (
          <HStack justify="center">
            <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              Previous
            </Button>
            <Text fontSize="sm" color="fgMuted">
              Page {page} of {totalPages}
            </Text>
            <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              Next
            </Button>
          </HStack>
        )}
      </Stack>

      <ConfirmDialog
        open={confirm !== null}
        title={`Disable ${confirm?.fullName ?? confirm?.email ?? 'this user'}?`}
        description="They will be signed out and cannot use the app until you enable them again."
        confirmLabel="Disable"
        destructive
        loading={update.isPending}
        onConfirm={() => confirm && update.mutate({ id: confirm.id, isActive: false })}
        onClose={() => setConfirm(null)}
      />
    </PageWrapper>
  );
}
