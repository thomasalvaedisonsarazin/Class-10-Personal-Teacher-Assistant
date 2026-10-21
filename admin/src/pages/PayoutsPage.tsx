import { Badge, Button, Field, HStack, Input, Stack, Table, Text } from '@chakra-ui/react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { FiDollarSign } from 'react-icons/fi';

import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { ErrorState } from '@/components/ui/ErrorState';
import { FormDialog } from '@/components/ui/FormDialog';
import { LoadingState } from '@/components/ui/LoadingState';
import { PageWrapper } from '@/components/ui/PageWrapper';
import { adminService } from '@/services/adminService';
import { getApiErrorMessage } from '@/services/api';
import type { AdminPayout, PayoutStatus } from '@/types/admin';

const FILTERS: { label: string; value: PayoutStatus | undefined }[] = [
  { label: 'Waiting', value: 'requested' },
  { label: 'Approved', value: 'approved' },
  { label: 'Paid', value: 'paid' },
  { label: 'Rejected', value: 'rejected' },
  { label: 'All', value: undefined },
];

const STATUS_COLOR: Record<PayoutStatus, string> = {
  requested: 'orange',
  approved: 'blue',
  paid: 'green',
  rejected: 'gray',
};

const rupees = (value: number): string => `₹${value.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

/** Where to send the money, shown in full only to the admin. */
function PayTo({ payout }: { payout: AdminPayout }) {
  const d = payout.payoutDetails;
  if (!d) return <Text color="danger">No payout details</Text>;
  return d.method === 'upi' ? (
    <Text fontFamily="mono">UPI: {d.upi}</Text>
  ) : (
    <Stack gap={0}>
      <Text>{d.holder}</Text>
      <Text fontFamily="mono" fontSize="sm">
        A/c {d.account} · IFSC {d.ifsc}
      </Text>
    </Stack>
  );
}

type Decision = { payout: AdminPayout; action: 'paid' | 'reject' };

/** Partner payout requests: approve, pay by UPI / bank, then record the reference. */
export default function PayoutsPage() {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<PayoutStatus | undefined>('requested');
  const [decision, setDecision] = useState<Decision | null>(null);
  const [text, setText] = useState('');

  const payouts = useQuery({
    queryKey: ['admin', 'payouts', status ?? 'all'],
    queryFn: () => adminService.payouts(status),
  });

  const decide = useMutation({
    mutationFn: ({ id, action, value }: { id: number; action: 'approve' | 'paid' | 'reject'; value?: string }) =>
      adminService.decidePayout(
        id,
        action,
        action === 'paid' ? { reference: value } : action === 'reject' ? { note: value } : {},
      ),
    onSuccess: async () => {
      setDecision(null);
      setText('');
      await queryClient.invalidateQueries({ queryKey: ['admin', 'payouts'] });
      await queryClient.invalidateQueries({ queryKey: ['admin', 'partners'] });
    },
  });

  return (
    <PageWrapper
      title="Payouts"
      description="Partners ask for their commission here. Send the money by UPI or bank transfer, then mark it paid with the transaction reference."
    >
      <Stack gap={4}>
        <HStack gap={2} wrap="wrap">
          {FILTERS.map((f) => (
            <Button
              key={f.label}
              size="sm"
              variant={status === f.value ? 'solid' : 'outline'}
              onClick={() => setStatus(f.value)}
            >
              {f.label}
            </Button>
          ))}
        </HStack>
        {decide.isError && decision === null && (
          <Text role="alert" color="danger" fontSize="sm">
            {getApiErrorMessage(decide.error)}
          </Text>
        )}
        {payouts.isPending && <LoadingState />}
        {payouts.isError && (
          <ErrorState message={getApiErrorMessage(payouts.error)} onRetry={() => void payouts.refetch()} />
        )}
        {payouts.data && payouts.data.length === 0 && (
          <Card>
            <EmptyState icon={FiDollarSign} title="Nothing here" />
          </Card>
        )}
        {payouts.data && payouts.data.length > 0 && (
          <Card p={0}>
            <Table.ScrollArea>
              <Table.Root size="sm">
                <Table.Header>
                  <Table.Row bg="bg">
                    <Table.ColumnHeader>Partner</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Amount</Table.ColumnHeader>
                    <Table.ColumnHeader>Pay to</Table.ColumnHeader>
                    <Table.ColumnHeader>PAN</Table.ColumnHeader>
                    <Table.ColumnHeader>Status</Table.ColumnHeader>
                    <Table.ColumnHeader textAlign="end">Actions</Table.ColumnHeader>
                  </Table.Row>
                </Table.Header>
                <Table.Body>
                  {payouts.data.map((p) => (
                    <Table.Row key={p.id}>
                      <Table.Cell>
                        <Text fontWeight="medium">{p.partnerName}</Text>
                        <Text fontSize="xs" color="fgMuted">
                          Requested {new Date(p.requestedAt).toLocaleDateString('en-IN')}
                        </Text>
                      </Table.Cell>
                      <Table.Cell textAlign="end" fontWeight="semibold">
                        {rupees(p.amount)}
                      </Table.Cell>
                      <Table.Cell>
                        <PayTo payout={p} />
                      </Table.Cell>
                      <Table.Cell fontFamily="mono">{p.pan ?? '—'}</Table.Cell>
                      <Table.Cell>
                        <Badge variant="subtle" colorPalette={STATUS_COLOR[p.status]}>
                          {p.status}
                        </Badge>
                        {p.reference && (
                          <Text fontSize="xs" color="fgMuted">
                            Ref {p.reference}
                          </Text>
                        )}
                        {p.adminNote && (
                          <Text fontSize="xs" color="fgMuted">
                            {p.adminNote}
                          </Text>
                        )}
                      </Table.Cell>
                      <Table.Cell textAlign="end">
                        <HStack justify="end" gap={1}>
                          {p.status === 'requested' && (
                            <Button
                              size="xs"
                              variant="outline"
                              loading={decide.isPending}
                              onClick={() => decide.mutate({ id: p.id, action: 'approve' })}
                            >
                              Approve
                            </Button>
                          )}
                          {(p.status === 'requested' || p.status === 'approved') && (
                            <>
                              <Button size="xs" onClick={() => setDecision({ payout: p, action: 'paid' })}>
                                Mark paid
                              </Button>
                              <Button
                                size="xs"
                                variant="ghost"
                                onClick={() => setDecision({ payout: p, action: 'reject' })}
                              >
                                Reject
                              </Button>
                            </>
                          )}
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
        open={decision !== null}
        title={
          decision?.action === 'paid'
            ? `Mark ${rupees(decision.payout.amount)} paid to ${decision.payout.partnerName}`
            : `Reject payout for ${decision?.payout.partnerName ?? ''}`
        }
        submitLabel={decision?.action === 'paid' ? 'Mark paid' : 'Reject'}
        loading={decide.isPending}
        error={decide.isError ? getApiErrorMessage(decide.error) : null}
        onSubmit={() => decision && decide.mutate({ id: decision.payout.id, action: decision.action, value: text })}
        onClose={() => {
          setDecision(null);
          setText('');
        }}
      >
        <Field.Root required={decision?.action === 'paid'}>
          <Field.Label>{decision?.action === 'paid' ? 'UPI / bank transaction reference (UTR)' : 'Reason (shown to you only)'}</Field.Label>
          <Input value={text} onChange={(e) => setText(e.target.value)} />
          {decision?.action === 'reject' && (
            <Field.HelperText>The amount goes back to the partner&apos;s available balance.</Field.HelperText>
          )}
        </Field.Root>
      </FormDialog>
    </PageWrapper>
  );
}
