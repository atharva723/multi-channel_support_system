import { Check } from 'lucide-react-native';
import React, { useEffect, useRef } from 'react';
import { Animated, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useToastStore } from '../hooks/useToastStore';
import { channelMeta } from '../lib/channels';
import { colors, radius, shadow, spacing } from '../theme';
import { AppText } from './AppText';

const VISIBLE_MS = 2000;

/**
 * Global success toast: a pill with a green tick + one-liner that slides down
 * from the top, holds for ~2s, then slides away. Rendered once at the root so
 * it overlays every screen (including bottom sheets).
 */
export function Toast() {
  const { visible, message, channel, hide } = useToastStore();
  const insets = useSafeAreaInsets();
  const anim = useRef(new Animated.Value(0)).current;
  const meta = channel ? channelMeta(channel) : null;

  useEffect(() => {
    if (!visible) return;
    anim.setValue(0);
    Animated.spring(anim, { toValue: 1, useNativeDriver: true, friction: 8, tension: 70 }).start();
    const timer = setTimeout(() => {
      Animated.timing(anim, { toValue: 0, duration: 220, useNativeDriver: true }).start(() => hide());
    }, VISIBLE_MS);
    return () => clearTimeout(timer);
  }, [visible, message, anim, hide]);

  if (!visible) return null;

  return (
    <Animated.View
      pointerEvents="none"
      style={{
        position: 'absolute',
        top: insets.top + spacing.sm,
        left: spacing.page,
        right: spacing.page,
        zIndex: 1000,
        opacity: anim,
        transform: [
          { translateY: anim.interpolate({ inputRange: [0, 1], outputRange: [-24, 0] }) },
        ],
      }}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.md,
          backgroundColor: colors.surface,
          borderRadius: radius.full,
          borderWidth: 1,
          borderColor: '#B8E6C8',
          paddingVertical: 12,
          paddingHorizontal: spacing.base,
          ...shadow.card,
        }}
      >
        <View
          style={{
            width: 28,
            height: 28,
            borderRadius: 14,
            backgroundColor: colors.success,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Check size={17} color={colors.white} strokeWidth={3} />
        </View>
        <AppText variant="labelMd" color={colors.onSurface} style={{ flex: 1 }} numberOfLines={2}>
          {message}
        </AppText>
        {meta ? <meta.Icon size={16} color={meta.color} strokeWidth={2.5} /> : null}
      </View>
    </Animated.View>
  );
}
