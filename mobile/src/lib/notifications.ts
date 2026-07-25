import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { Platform } from 'react-native';

import { colors } from '../theme';

/**
 * Foreground notification behaviour. Without this, notifications that arrive
 * while the app is open are silently dropped. (SDK 57 shape.)
 */
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

/**
 * Ensure the Android "escalations" channel exists. Android requires a channel
 * for the permission prompt to appear and for high-importance heads-up alerts.
 */
export async function ensureAndroidChannel() {
  if (Platform.OS !== 'android') return;
  // Note: omit `sound` so the channel uses the system default notification
  // sound. Passing a string (e.g. 'default') makes Android look for a BUNDLED
  // custom sound file by that name, which triggers the "Custom sound 'default'
  // not found" warning. `shouldPlaySound` in the handler + MAX importance still
  // give an audible heads-up alert.
  await Notifications.setNotificationChannelAsync('escalations', {
    name: 'Critical escalations',
    importance: Notifications.AndroidImportance.MAX,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: colors.primary,
  });
}

/**
 * Request permission and fetch this device's Expo push token. Returns null if
 * not a physical device or permission was denied.
 */
export async function registerForPushNotificationsAsync(): Promise<string | null> {
  await ensureAndroidChannel();

  if (!Device.isDevice) return null;

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;
  if (existing !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }
  if (finalStatus !== 'granted') return null;

  const projectId =
    Constants?.expoConfig?.extra?.eas?.projectId ??
    (Constants as any)?.easConfig?.projectId;
  if (!projectId) return null;

  try {
    const { data } = await Notifications.getExpoPushTokenAsync({ projectId });
    currentPushToken = data;
    return data;
  } catch {
    return null;
  }
}

/** The most recently obtained Expo push token for this device (or null). */
let currentPushToken: string | null = null;
export function getCurrentPushToken(): string | null {
  return currentPushToken;
}
