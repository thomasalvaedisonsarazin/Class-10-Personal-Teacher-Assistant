import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Share, StyleSheet, View } from 'react-native';
import { Button, HelperText } from 'react-native-paper';

import { AppText, PrimaryButton } from '@/components/ui';
import { getApiErrorMessage } from '@/services/api';
import { parentService } from '@/services/parentService';
import { palette, radius, spacing } from '@/theme';

function formatCode(code: string): string {
  return `${code.slice(0, 4)}-${code.slice(4)}`;
}

function formatDate(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleDateString();
}

/** Student profile section: invite a parent with a code, see and remove linked parents. */
export function ParentAccess() {
  const queryClient = useQueryClient();
  const links = useQuery({ queryKey: ['parent-links'], queryFn: parentService.myParents });
  const invalidate = (): Promise<void> => queryClient.invalidateQueries({ queryKey: ['parent-links'] });
  const invite = useMutation({ mutationFn: parentService.createInvite, onSuccess: invalidate });
  const remove = useMutation({ mutationFn: parentService.removeParent, onSuccess: invalidate });

  const code = invite.data?.code ?? links.data?.invite?.code ?? null;
  const expires = invite.data?.expiresAt ?? links.data?.invite?.expiresAt ?? null;

  const share = (): void => {
    if (!code) return;
    Share.share({
      message:
        `Follow my studies on Personal Teacher Assistant. Open the app, choose "I'm a parent" ` +
        `and enter this code: ${formatCode(code)}`,
    }).catch(() => undefined);
  };

  return (
    <View style={styles.box} testID="parent-access">
      <AppText variant="subtitle">Parents</AppText>
      <AppText variant="caption" tone="secondary">
        A parent can see your progress and test scores (they cannot change anything).
      </AppText>

      {links.data?.parents.map((p) => (
        <View key={p.linkId} style={styles.parentRow}>
          <View style={styles.parentText}>
            <AppText>{p.name ?? p.email}</AppText>
            <AppText variant="caption" tone="secondary">
              {p.email}
            </AppText>
          </View>
          <Button
            mode="text"
            textColor={palette.error}
            onPress={() => remove.mutate(p.linkId)}
            loading={remove.isPending && remove.variables === p.linkId}
            accessibilityLabel={`Remove ${p.name ?? p.email}`}
          >
            Remove
          </Button>
        </View>
      ))}

      {code ? (
        <View style={styles.codeBox}>
          <AppText variant="caption" tone="secondary">
            Share this code with your parent{expires ? ` (valid until ${formatDate(expires)})` : ''}
          </AppText>
          <AppText variant="display" center testID="invite-code">
            {formatCode(code)}
          </AppText>
          <PrimaryButton label="Share code" icon="share-variant" mode="outlined" onPress={share} />
        </View>
      ) : (
        <PrimaryButton
          label="Invite a parent"
          icon="account-plus-outline"
          mode="outlined"
          onPress={() => invite.mutate()}
          loading={invite.isPending}
          testID="invite-parent"
        />
      )}
      <HelperText type="error" visible={invite.isError || remove.isError || links.isError}>
        {invite.isError
          ? getApiErrorMessage(invite.error)
          : remove.isError
            ? getApiErrorMessage(remove.error)
            : links.isError
              ? getApiErrorMessage(links.error)
              : ''}
      </HelperText>
    </View>
  );
}

const styles = StyleSheet.create({
  box: {
    gap: spacing.sm,
  },
  parentRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: palette.surface,
  },
  parentText: {
    flex: 1,
  },
  codeBox: {
    gap: spacing.sm,
    padding: spacing.lg,
    borderRadius: radius.md,
    borderWidth: 1,
    borderStyle: 'dashed',
    borderColor: palette.primary,
    backgroundColor: palette.surface,
  },
});
