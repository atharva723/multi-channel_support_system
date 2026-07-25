import * as Haptics from 'expo-haptics';

import { hapticsEnabled } from '../hooks/usePrefsStore';

/**
 * Haptics wrappers that respect the user's "Haptic Feedback" preference. Use
 * these instead of calling `expo-haptics` directly so the Settings toggle
 * actually silences feedback app-wide.
 */
export function hapticImpact(style: Haptics.ImpactFeedbackStyle = Haptics.ImpactFeedbackStyle.Light) {
  if (hapticsEnabled()) Haptics.impactAsync(style).catch(() => {});
}

export function hapticSuccess() {
  if (hapticsEnabled()) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
}

export function hapticWarning() {
  if (hapticsEnabled()) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => {});
}

export function hapticError() {
  if (hapticsEnabled()) Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error).catch(() => {});
}
