import { StyleSheet, View } from 'react-native';

import { AppHeader } from '@/components/layout/AppHeader';
import { AppText, Screen } from '@/components/ui';
import { useAuth } from '@/hooks/useAuth';
import { spacing } from '@/theme';

/** Placeholder — Phase 2 adds ContinueLearningCard + SubjectTileGrid. */
export default function HomeScreen() {
  const { user } = useAuth();
  const greeting = user?.fullName ? `Welcome, ${user.fullName}` : 'Welcome';

  return (
    <Screen testID="home-screen" padded={false}>
      <AppHeader title="Home" />
      <View style={styles.body}>
        <AppText variant="title">{greeting}</AppText>
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  body: {
    flex: 1,
    padding: spacing.lg,
  },
});
