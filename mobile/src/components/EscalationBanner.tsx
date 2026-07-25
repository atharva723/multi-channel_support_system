import { AlertCircle, ChevronRight } from 'lucide-react-native';
import React from 'react';
import { Pressable, View } from 'react-native';
import Animated, { FadeInUp, FadeOutUp } from 'react-native-reanimated';

import { colors, radius, shadow, spacing } from '../theme';
import { AppText } from './AppText';

interface Props {
  title: string;
  subtitle: string;
  onPress?: () => void;
}

/** Rose banner that slides in from the top on a new critical escalation. */
export function EscalationBanner({ title, subtitle, onPress }: Props) {
  return (
    <Animated.View entering={FadeInUp.springify().damping(16)} exiting={FadeOutUp}>
      <Pressable
        onPress={onPress}
        style={({ pressed }) => ({
          marginHorizontal: spacing.page,
          backgroundColor: colors.escalation,
          borderRadius: radius.lg,
          padding: spacing.base,
          flexDirection: 'row',
          alignItems: 'center',
          gap: spacing.md,
          transform: [{ scale: pressed ? 0.99 : 1 }],
          ...shadow.fab,
        })}
      >
        <View
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            backgroundColor: 'rgba(255,255,255,0.2)',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <AlertCircle size={24} color={colors.white} />
        </View>
        <View style={{ flex: 1 }}>
          <AppText variant="titleSm" color={colors.white}>
            {title}
          </AppText>
          <AppText variant="bodyMd" color="rgba(255,255,255,0.85)">
            {subtitle}
          </AppText>
        </View>
        <ChevronRight size={22} color={colors.white} />
      </Pressable>
    </Animated.View>
  );
}
