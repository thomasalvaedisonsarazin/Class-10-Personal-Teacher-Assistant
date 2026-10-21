import { Badge, Button, Field, HStack, Input, Stack, Table, Text } from '@chakra-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FiAward } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormDialog } from '@/components/ui/FormDialog';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { PrimaryButton } from '@/components/ui/PrimaryButton';
import { adminService } from '@/services/adminService';
import { getApiErrorMessage } from '@/services/api';
import type { AdminPartner } from '@/types/admin';

const rupees = (value: number): string => `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

interface PartnerForm {
  name: string;
  email: string;
  commissionPct: string;
}

const EMPTY_FORM: PartnerForm = { name: '', email: '', commissionPct: '2' };

/** Schools / teachers who bring students with a code, and their commission. */
export default function PartnersPage() {
  const queryClient = useQueryClient();
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<PartnerForm>(EMPTY_FORM);
  const [editing, setEditing] = useState<AdminPartner | null>(null);
  const [rate, setRate] = useState('');
  const [copied, setCopied] = useState<number | null>(null);

  const partners = useQuery({ queryKey: ['admin', 'partners'], queryFn: adminService.partners });
  const refresh = (): Promise<void> => queryClient.invalidateQueries({ queryKey: ['admin', 'partners'] });

  const create = useMutation({
    mutationFn: () =>
      adminService.createPartner({
        name: form.name.trim(),
        email: form.email.trim(),
        commissionPct: Number(form.commissionPct),
      }),
    onSuccess: async () => {
      setCreating(false);
      setForm(EMPTY_FORM);
      await refresh();
    },
  });

  const update = useMutation({
    mutationFn: ({ id, ...input }: { id: number; commissionPct?: number; isActive?: boolean }) =>
      adminService.updatePartner(id, input),
    onSuccess: async () => {
      setEditing(null);
      await refresh();
    },
  });

  const copyLink = async (partner: AdminPartner): Promise<void> => {
    try {
      await navigator.clipboard.writeText(`${partner.shareLink}  (code: ${partner.code})`);
      setCopied(partner.id);
    } catch {
      setCopied(null);
    }
  };

  return (
    <PageWrapper
      title="Partners"
      description="Schools and teachers who bring students with their code. They sign in to the app with the email you add here."
      actions={<PrimaryButton onClick={() => setCreating(true)}>Add partner</PrimaryButton>}
    >
      <Stack gap={4}>
        {update.isError && (
          <Text role="alert" color="danger" fontSize="sm">
            {getApiErrorMessage(update.error)}
          </Text>
        )}
        {partners.isPending && <LoadingState />}
        {partners.isError && (
          <ErrorState message={getApiErrorMessage(partners.error)} onRetry={() => void partners.refetch()} />
        )}
        {partners.data && partners.data.length === 0 && (
          <Card>
            <EmptyState icon={FiAward} title="No partners yet" description="Add a school or teacher to give them a code." />
          </Card>
        )}
        {partners.data && partners.data.length > 0 && (
          <Card p={0}>
            <Table.ScrollArea>
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row bg="bg">
                    <Table.ColumnHeader>Partner</Table.ColumnHeader>
                    <Table.ColumnHeader>Code</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Rate</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Students</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Paying</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Earned</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Paid out</Table.ColumnHeader>
                    <Table.ColumnHeader>Status</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Actions</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {partners.data.map((p) => (
                    <Table.Row key={p.id}>
                      <Table.Cell>
                        <Text fontWeight="medium">{p.name}</Text>
                        <Text fontSize="xs" color="fgMuted">
                          {p.email} {p.signedIn ? '· signed in' : '· not signed in yet'}
                        </Text>
                      </Table.Cell>
                      <Table.Cell fontFamily="mono">{p.code}</Table.Cell>
                      <Table.Cell textAlign="end">{p.commissionPct}%</Table.Cell>
                      <Table.Cell textAlign="end">{p.studentsJoined}</Table.Cell>
                      <Table.Cell textAlign="end">{p.payingStudents}</Table.Cell>
                      <Table.Cell textAlign="end">{rupees(p.earned)}</Table.Cell>
                      <Table.Cell textAlign="end">{rupees(p.paid)}</Table.Cell>
                      <Table.Cell>
                        <Badge variant="subtle" colorPalette={p.isActive ? 'green' : 'gray'}>
                          {p.isActive ? 'Active' : 'Paused'}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell textAlign="end">
                        <HStack justify="end" gap={1}>
                          <Button size="xs" variant="outline" onClick={() => void copyLink(p)}>
                            {copied === p.id ? 'Copied' : 'Copy link'}
                          </Button>
                          <Button
                            size="xs"
                            variant="outline"
                            onClick={() => {
                              setEditing(p);
                              setRate(String(p.commissionPct));
                            }}
                          >
                            Rate
                          </Button>
                          <Button
                            size="xs"
                            variant="outline"
                            onClick={() => update.mutate({ id: p.id, isActive: !p.isActive })}
                          >
                            {p.isActive ? 'Pause' : 'Resume'}
                          </Button>
                        </HStack>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table.Root>
            </Table.ScrollArea>
          </Card>
        )}
      </Stack>

      <FormDialog
        open={creating}
        title="Add partner"
        submitLabel="Create"
        loading={create.isPending}
        error={create.isError ? getApiErrorMessage(create.error) : null}
        onSubmit={() => create.mutate()}
        onClose={() => setCreating(false)}
      >
        <Field.Root required>
          <Field.Label>School or teacher name</Field.Label>
          <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="St Joseph Matric School" />
        </Field.Root>
        <Field.Root required>
          <Field.Label>Their email (they sign in with it)</Field.Label>
          <Input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          <Field.HelperText>Use an email that is not already a student or parent account.</Field.HelperText>
        </Field.Root>
        <Field.Root>
          <Field.Label>Commission %</Field.Label>
          <Input
            type="number"
            min={0}
            max={50}
            step={0.5}
            value={form.commissionPct}
            onChange={(e) => setForm({ ...form, commissionPct: e.target.value })}
          />
          <Field.HelperText>Of what we receive after Google&apos;s fee, on every payment.</Field.HelperText>
        </Field.Root>
      </FormDialog>

      <FormDialog
        open={editing !== null}
        title={`Commission for ${editing?.name ?? ''}`}
        loading={update.isPending}
        error={update.isError ? getApiErrorMessage(update.error) : null}
        onSubmit={() => editing && update.mutate({ id: editing.id, commissionPct: Number(rate) })}
        onClose={() => setEditing(null)}
      >
        <Field.Root>
          <Field.Label>Commission %</Field.Label>
          <Input type="number" min={0} max={50} step={0.5} value={rate} onChange={(e) => setRate(e.target.value)} />
          <Field.HelperText>Applies to new payments; earlier commission stays as it was.</Field.HelperText>
        </Field.Root>
      </FormDialog>
    </PageWrapper>
  );
}
