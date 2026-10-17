import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking, StyleSheet, View } from 'react-native';
import { HelperText } from 'react-native-paper';

import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, ErrorState, LoadingView, PrimaryButton, Screen } from '@/components/ui';
import { parseIdParam } from '@/hooks/useCurriculum';
import {
  BASE_PLAN_YEARLY,
  FALLBACK_PRICES,
  formatUntil,
  isPremiumActive,
  planOptions,
} from '@/lib/billing';
import type { PlanChoice } from '@/lib/billing';
import { getApiErrorMessage } from '@/services/api';
import { billingService } from '@/services/billingService';
import { isStoreAvailable, playStore } from '@/services/playStore';
import type { StorePrices } from '@/services/playStore';
import { palette, radius, spacing } from '@/theme';

const MANAGE_URL =
  'https://play.google.com/store/account/subscriptions?package=com.edsolution.teacherassistant';

interface PlanCard {
  key: string;
  choice: PlanChoice;
  title: string;
  price: string;
  note: string;
}

function planCards(options: PlanChoice[], prices: StorePrices): PlanCard[] {
  return options.map((choice) => {
    if (choice.kind === 'subscription') {
      const yearly = choice.basePlanId === BASE_PLAN_YEARLY;
      const storePrice = prices.plans?.[choice.productId]?.[choice.basePlanId]?.price;
      const price = storePrice ?? (yearly ? FALLBACK_PRICES.yearly : FALLBACK_PRICES.monthly);
      return {
        key: `${choice.productId}-${choice.basePlanId}`,
        choice,
        title: yearly ? 'Yearly plan' : 'Monthly plan',
        price: `${price}${yearly ? ' / year' : ' / month'}`,
        note: `All topics in every subject. Renews every ${yearly ? 'year' : 'month'}; cancel any time in Google Play.`,
      };
    }
    return {
      key: `topic-${choice.topicId}`,
      choice,
      title: 'Only this topic',
      price: prices.topic ?? FALLBACK_PRICES.topic,
      note: 'Unlocks this one topic forever, and you can open it straight away.',
    };
  });
}

/** Plans for a student (or a parent paying for a linked child) and single-topic unlock. */
export default function PremiumScreen() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useLocalSearchParams<{ topicId?: string; topicTitle?: string; studentId?: string; childName?: string }>();
  const topicId = params.topicId ? parseIdParam(params.topicId) : null;
  const studentId = params.studentId ? parseIdParam(params.studentId) : undefined;
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [message, setMessage] = useState<{ type: 'error' | 'info'; text: string } | null>(null);
  const goBack = (): void => (router.canGoBack() ? router.back() : router.replace('/'));

  const status = useQuery({
    queryKey: ['billing', studentId ?? 'me'],
    queryFn: () => billingService.getStatus(studentId),
  });
  const prices = useQuery({
    queryKey: ['storePrices'],
    queryFn: playStore.loadPrices,
    enabled: isStoreAvailable && status.data?.billingEnabled === true,
    staleTime: 10 * 60_000,
  });

  const refreshAccess = async (): Promise<void> => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['billing'] }),
      queryClient.invalidateQueries({ queryKey: ['subjects'] }),
      queryClient.invalidateQueries({ queryKey: ['topics'] }),
    ]);
  };

  // Finish payments that were confirmed later (UPI) or interrupted.
  useEffect(() => {
    if (!isStoreAvailable) return;
    playStore
      .syncPurchases()
      .then((count) => (count > 0 ? refreshAccess() : undefined))
      .catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status.isPending) {
    return (
      <Screen padded={false}>
        <AppHeader title="Premium" onBack={goBack} />
        <LoadingView />
      </Screen>
    );
  }
  if (status.isError) {
    return (
      <Screen padded={false}>
        <AppHeader title="Premium" onBack={goBack} />
        <ErrorState message={getApiErrorMessage(status.error)} onRetry={() => void status.refetch()} />
      </Screen>
    );
  }

  const info = status.data;
  const active = isPremiumActive(info.premiumUntil);
  const options: PlanChoice[] = [
    ...(active ? [] : planOptions(info.nextSubscriptionId)),
    ...(topicId !== null && !active && !info.purchasedTopicIds.includes(topicId)
      ? [{ kind: 'topic' as const, topicId }]
      : []),
  ];
  const cards = planCards(options, prices.data ?? {});

  const buy = async (card: PlanCard): Promise<void> => {
    setMessage(null);
    setBusyKey(card.key);
    try {
      const outcome = await playStore.buy(card.choice, info, prices.data ?? {});
      if (outcome.status === 'done') {
        await refreshAccess();
        setMessage({ type: 'info', text: 'Unlocked! Thank you.' });
      } else if (outcome.status === 'pending') {
        setMessage({
          type: 'info',
          text: 'Payment is pending (UPI can take a few minutes). It unlocks by itself once Google confirms it — open this screen again later.',
        });
      }
    } catch (err) {
      setMessage({ type: 'error', text: getApiErrorMessage(err) });
    } finally {
      setBusyKey(null);
    }
  };

  const forWhom = params.childName ? ` for ${params.childName}` : '';

  return (
    <Screen padded={false} testID="premium-screen">
      <AppHeader title="Premium" onBack={goBack} />
      <Screen scroll edges={[]}>
        <View style={styles.content}>
          {!info.billingEnabled ? (
            <AppText tone="secondary">Every topic is free right now. Enjoy learning!</AppText>
          ) : (
            <>
              <AppText variant="title">
                {active ? `Premium is active${forWhom}` : `Unlock all topics${forWhom}`}
              </AppText>
              {active && info.premiumUntil ? (
                <AppText tone="secondary">Active until {formatUntil(info.premiumUntil)}.</AppText>
              ) : (
                <AppText tone="secondary">
                  The first topic of every subject is free. Choose a plan to open all topics, or buy
                  just the topic you need.
                </AppText>
              )}
              {params.topicTitle ? (
                <AppText variant="bodySmall" tone="secondary">
                  Topic: {params.topicTitle}
                </AppText>
              ) : null}

              {!active && info.nextSubscriptionId === null ? (
                <AppText tone="secondary">
                  You already have plans for 3 children on this Google account. Use another Google
                  account for more children.
                </AppText>
              ) : null}

              {!isStoreAvailable ? (
                <AppText tone="secondary">Payments work in the Android app.</AppText>
              ) : (
                cards.map((card) => (
                  <View key={card.key} style={styles.card} testID={`plan-${card.key}`}>
                    <View style={styles.cardHeader}>
                      <AppText variant="subtitle">{card.title}</AppText>
                      <AppText variant="subtitle">{card.price}</AppText>
                    </View>
                    <AppText variant="bodySmall" tone="secondary">
                      {card.note}
                    </AppText>
                    <PrimaryButton
                      label={`Pay ${card.price.split(' ')[0]}`}
                      onPress={() => void buy(card)}
                      loading={busyKey === card.key}
                      disabled={busyKey !== null}
                    />
                  </View>
                ))
              )}

              <HelperText type={message?.type ?? 'info'} visible={message !== null}>
                {message?.text ?? ''}
              </HelperText>

              {isStoreAvailable ? (
                <PrimaryButton
                  label="Manage or cancel my plan"
                  mode="text"
                  onPress={() => void Linking.openURL(MANAGE_URL)}
                />
              ) : null}
              <AppText variant="caption" tone="secondary">
                Payments are handled by Google Play (UPI, cards, Play balance).
              </AppText>
            </>
          )}
        </View>
      </Screen>
    </Screen>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: spacing.lg,
    paddingVertical: spacing.lg,
  },
  card: {
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: palette.outline,
    backgroundColor: palette.surface,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
});
