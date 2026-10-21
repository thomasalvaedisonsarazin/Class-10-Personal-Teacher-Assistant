import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { api } from './api';

/** The token this phone registered, so sign-out can remove it. */
let registeredToken: string | null = null;

/** Show notifications while the app is open too (quietly, no sound). */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: false,
    shouldSetBadge: false,
  }),
});

function easProjectId(): string | null {
  const extra = Constants.expoConfig?.extra as { eas?: { projectId?: string } } | undefined;
  return extra?.eas?.projectId ?? Constants.easConfig?.projectId ?? null;
}

/**
 * Ask permission, get this phone's Expo push token and send it to the API.
 * Quietly does nothing on web, simulators, without an EAS project, or if refused.
 */
export async function registerForPushNotifications(): Promise<void> {
  if (Platform.OS === 'web' || !Device.isDevice) return;
  const projectId = easProjectId();
  if (!projectId) return; // set up with `eas init` before release builds
  try {
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Study reminders',
        importance: Notifications.AndroidImportance.DEFAULT,
      });
    }
    const current = await Notifications.getPermissionsAsync();
    const granted = current.granted || (await Notifications.requestPermissionsAsync()).granted;
    if (!granted) return;
    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
    await api.post('/devices', { expoPushToken: token, platform: Platform.OS === 'ios' ? 'ios' : 'android' });
    registeredToken = token;
  } catch {
    // Notifications are optional; never block the app.
  }
}

/** Stop pushes to this phone (best effort, before tokens are cleared on sign-out). */
export async function unregisterPushNotifications(): Promise<void> {
  if (!registeredToken) return;
  const token = registeredToken;
  registeredToken = null;
  try {
    await api.post('/devices/remove', { expoPushToken: token, platform: Platform.OS === 'ios' ? 'ios' : 'android' });
  } catch {
    // Ignore: the server also drops dead tokens when Expo reports them.
  }
}

export interface NotificationTarget {
  screen: 'topic' | 'child' | 'partner';
  id: number;
}

/** Where a tapped notification should take the user. */
export function targetFromData(data: Record<string, unknown> | undefined): NotificationTarget | null {
  if (!data) return null;
  if (data.screen === 'topic' && typeof data.topicId === 'number') return { screen: 'topic', id: data.topicId };
  if (data.screen === 'child' && typeof data.studentId === 'number') return { screen: 'child', id: data.studentId };
  if (data.screen === 'partner') return { screen: 'partner', id: 0 };
  return null;
}
