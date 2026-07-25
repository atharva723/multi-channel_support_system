import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import { useEffect, useRef } from 'react';
import { Platform } from 'react-native';

import { NotificationsApi } from '../api/client';
import { registerForPushNotificationsAsync } from '../lib/notifications';
import { useAuthStore } from './useAuthStore';

/** Route a tapped notification to the ticket it references (`data.url`). */
function redirectFromNotification(notification: Notifications.Notification) {
  const url = notification.request.content.data?.url;
  if (typeof url === 'string' && url.length > 0) {
    router.push(url as never);
  }
}

/**
 * App-wide push wiring, mounted once at the root:
 *  1. When authenticated, registers this device's Expo push token with the
 *     backend so escalations can reach it (and unregisters on sign-out).
 *  2. Handles notification taps (cold-start + warm) by deep-linking to the
 *     referenced ticket.
 */
export function usePushNotifications() {
  const token = useAuthStore((s) => s.token);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const pushTokenRef = useRef<string | null>(null);

  // Register / unregister the device token with the backend.
  useEffect(() => {
    let cancelled = false;

    if (isAuthenticated && token) {
      registerForPushNotificationsAsync().then((pushToken) => {
        if (cancelled || !pushToken) return;
        pushTokenRef.current = pushToken;
        NotificationsApi.register(pushToken, Platform.OS).catch(() => {});
      });
    }

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, token]);

  // Tap-through: cold start (app opened from a notification) + while running.
  useEffect(() => {
    const last = Notifications.getLastNotificationResponse();
    if (last?.notification) {
      redirectFromNotification(last.notification);
    }

    const sub = Notifications.addNotificationResponseReceivedListener((response) => {
      redirectFromNotification(response.notification);
    });

    return () => {
      sub.remove();
    };
  }, []);
}
