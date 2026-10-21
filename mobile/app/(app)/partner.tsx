import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { RefreshControl, ScrollView, Share, StyleSheet, View } from 'react-native';
import { HelperText, ProgressBar, SegmentedButtons, TextInput } from 'react-native-paper';

import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { formatRupees } from '@/lib/referral';
import { getApiErrorMessage } from '@/services/api';
import { partnerService } from '@/services/partnerService';
import { palette, radius, spacing } from '@/theme';
import type { PartnerDashboard, PayoutDetailsInput, PayoutStatus } from '@/types/partner';

const STATUS_TEXT: Record<PayoutStatus, string> = {
  requested: 'Waiting for approval',
  approved: 'Approved — payment on the way',
  paid: 'Paid ✓',
  rejected: 'Not approved — amount returned to your balance',
};

const QUERY_KEY = ['partner', 'dashboard'] as const;

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.stat}>
      <AppText variant="title">{value}</AppText>
      <AppText variant="caption" tone="secondary" center>
        {label}
      </AppText>
    </View>
  );
}

/** Payout details form: UPI ID or bank account, plus optional PAN (stored encrypted). */
function PayoutDetailsForm({ onSaved }: { onSaved: (data: PartnerDashboard) => void }) {
  const [method, setMethod] = useState<'upi' | 'bank'>('upi');
  const [upiId, setUpiId] = useState('');
  const [holderName, setHolderName] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [ifsc, setIfsc] = useState('');
  const [pan, setPan] = useState('');
  const save = useMutation({
    mutationFn: (input: PayoutDetailsInput) => partnerService.savePayoutDetails(input),
    onSuccess: onSaved,
  });
  const submit = (): void => {
    const panValue = pan.trim() ? pan.trim().toUpperCase() : undefined;
    save.mutate(
      method === 'upi'
        ? { method, upiId: upiId.trim(), pan: panValue }
        : { method, holderName: holderName.trim(), accountNumber: accountNumber.trim(), ifsc: ifsc.trim().toUpperCase(), pan: panValue },
    );
  };
  return (
    <View style={styles.section}>
      <SegmentedButtons
        value={method}
        onValueChange={(value) => setMethod(value === 'bank' ? 'bank' : 'upi')}
        buttons={[
          { value: 'upi', label: 'UPI ID' },
          { value: 'bank', label: 'Bank account' },
        ]}
      />
      {method === 'upi' ? (
        <TextInput label="UPI ID (e.g. name@okhdfc)" mode="outlined" autoCapitalize="none" value={upiId} onChangeText={setUpiId} />
      ) : (
        <>
          <TextInput label="Account holder name" mode="outlined" value={holderName} onChangeText={setHolderName} />
          <TextInput label="Account number" mode="outlined" keyboardType="number-pad" value={accountNumber} onChangeText={setAccountNumber} />
          <TextInput label="IFSC code" mode="outlined" autoCapitalize="characters" value={ifsc} onChangeText={setIfsc} />
        </>
      )}
      <TextInput label="PAN (optional, for tax records)" mode="outlined" autoCapitalize="characters" maxLength={10} value={pan} onChangeText={setPan} />
      <HelperText type="error" visible={save.isError}>
        {save.isError ? getApiErrorMessage(save.error) : ''}
      </HelperText>
      <PrimaryButton label="Save payment details" onPress={submit} loading={save.isPending} />
    </View>
  );
}

/** School / teacher partner dashboard: code, students joined and commission. */
export default function PartnerScreen() {
  const queryClient = useQueryClient();
  const { signOut } = useAuth();
  const [editingDetails, setEditingDetails] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const dashboard = useQuery({ queryKey: QUERY_KEY, queryFn: partnerService.dashboard });

  const payout = useMutation({
    mutationFn: partnerService.requestPayout,
    onSuccess: async () => {
      setNotice('Payout requested. You will get the money after the admin approves it.');
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
    },
  });

  if (dashboard.isPending) {
    return (
      <Screen padded={false}>
        <AppHeader title="Partner" />
        <LoadingView />
      </Screen>
    );
  }
  if (dashboard.isError) {
    return (
      <Screen padded={false}>
        <AppHeader title="Partner" />
        <ErrorState message={getApiErrorMessage(dashboard.error)} onRetry={() => void dashboard.refetch()} />
      </Screen>
    );
  }

  const d = dashboard.data;
  const progress = d.payoutMinimum > 0 ? Math.min(1, d.available / d.payoutMinimum) : 0;
  const share = (): void => {
    void Share.share({
      message: `Learn 10th standard topics with story lessons, tests and progress reports. Join with our code ${d.code}: ${d.shareLink}`,
    });
  };

  return (
    <Screen padded={false} testID="partner-screen">
      <AppHeader title="Partner" subtitle={d.name} />
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={dashboard.isRefetching} onRefresh={() => void dashboard.refetch()} />}
      >
        <View style={[styles.card, styles.codeCard]}>
          <AppText variant="caption" tone="secondary">
            Your code
          </AppText>
          <AppText variant="display" testID="partner-code">
            {d.code}
          </AppText>
          <AppText variant="bodySmall" tone="secondary" center>
            Students enter this code when they sign up, or open your link.
          </AppText>
          <PrimaryButton label="Share link" icon="share-variant" onPress={share} />
        </View>

        <View style={[styles.card, styles.statsRow]}>
          <Stat label="students joined" value={String(d.studentsJoined)} />
          <Stat label="paying students" value={String(d.payingStudents)} />
          <Stat label="your rate" value={`${d.commissionPct}%`} />
        </View>

        <View style={styles.card}>
          <AppText variant="subtitle">Commission</AppText>
          <View style={styles.rowBetween}>
            <AppText tone="secondary">Total earned</AppText>
            <AppText>{formatRupees(d.earned)}</AppText>
          </View>
          <View style={styles.rowBetween}>
            <AppText tone="secondary">On hold ({d.holdDays}-day refund window)</AppText>
            <AppText>{formatRupees(d.onHold)}</AppText>
          </View>
          <View style={styles.rowBetween}>
            <AppText tone="secondary">Ready to claim</AppText>
            <AppText variant="subtitle">{formatRupees(d.available)}</AppText>
          </View>
          <View style={styles.rowBetween}>
            <AppText tone="secondary">Paid to you</AppText>
            <AppText>{formatRupees(d.paid)}</AppText>
          </View>
          <ProgressBar progress={progress} color={palette.success} style={styles.progress} />
          <AppText variant="caption" tone="secondary">
            {d.available >= d.payoutMinimum
              ? 'You reached the payout limit!'
              : `${formatRupees(Math.max(0, d.payoutMinimum - d.available))} more to reach the ${formatRupees(d.payoutMinimum)} payout limit.`}
          </AppText>
          {d.requested > 0 ? (
            <AppText tone="secondary">{formatRupees(d.requested)} is waiting for the admin.</AppText>
          ) : null}
          <PrimaryButton
            label={`Get my money${d.available > 0 ? ` (${formatRupees(d.available)})` : ''}`}
            icon="cash"
            onPress={() => {
              setNotice(null);
              payout.mutate();
            }}
            disabled={!d.canRequestPayout}
            loading={payout.isPending}
            testID="request-payout"
          />
          <HelperText type={payout.isError ? 'error' : 'info'} visible={payout.isError || notice !== null}>
            {payout.isError ? getApiErrorMessage(payout.error) : (notice ?? '')}
          </HelperText>
        </View>

        <View style={styles.card}>
          <AppText variant="subtitle">Where we pay you</AppText>
          {d.payoutMethod && !editingDetails ? (
            <>
              <AppText>{d.payoutMethod}</AppText>
              <AppText variant="caption" tone="secondary">
                {d.panAdded ? 'PAN added' : 'PAN not added'}
              </AppText>
              <PrimaryButton label="Change" mode="text" onPress={() => setEditingDetails(true)} />
            </>
          ) : (
            <PayoutDetailsForm
              onSaved={(data) => {
                queryClient.setQueryData(QUERY_KEY, data);
                setEditingDetails(false);
              }}
            />
          )}
        </View>

        {d.payouts.length > 0 ? (
          <View style={styles.card}>
            <AppText variant="subtitle">Payout history</AppText>
            {d.payouts.map((p) => (
              <View key={p.id} style={styles.rowBetween}>
                <View style={styles.flex}>
                  <AppText>{formatRupees(p.amount)}</AppText>
                  <AppText variant="caption" tone="secondary">
                    {STATUS_TEXT[p.status]}
                    {p.reference ? ` · Ref ${p.reference}` : ''}
                  </AppText>
                </View>
                <AppText variant="caption" tone="secondary">
                  {new Date(p.requestedAt).toLocaleDateString('en-IN')}
                </AppText>
              </View>
            ))}
          </View>
        ) : null}

        <AppText variant="caption" tone="secondary" center>
          You earn {d.commissionPct}% of what we receive (after Google&apos;s fee) on every payment by students who
          joined with your code. For privacy, student names are not shown.
        </AppText>
        <PrimaryButton label="Sign out" mode="outlined" onPress={() => void signOut()} />
      </ScrollView>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: spacing.lg,
    gap: spacing.lg,
  },
  card: {
    backgroundColor: palette.surface,
    borderRadius: radius.md,
    padding: spacing.lg,
    gap: spacing.sm,
  },
  codeCard: {
    alignItems: 'center',
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stat: {
    flex: 1,
    alignItems: 'center',
    gap: spacing.xxs,
  },
  rowBetween: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: spacing.md,
  },
  flex: {
    flex: 1,
  },
  progress: {
    height: 8,
    borderRadius: radius.sm,
    marginTop: spacing.xs,
  },
  section: {
    gap: spacing.sm,
  },
});
