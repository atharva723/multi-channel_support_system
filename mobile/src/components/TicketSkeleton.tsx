import React, { useEffect } from 'react';
import { View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { colors, radius, shadow, spacing } from '../theme';

/** A single shimmering placeholder block. */
function Shimmer({ width, height, style }: { width: any; height: number; style?: any }) {
  const opacity = useSharedValue(0.4);
  useEffect(() => {
    opacity.value = withRepeat(
      withTiming(0.85, { duration: 800, easing: Easing.inOut(Easing.ease) }),
      -1,
      true,
    );
  }, [opacity]);
  const animStyle = useAnimatedStyle(() => ({ opacity: opacity.value }));
  return (
    <Animated.View
      style={[
        { width, height, borderRadius: radius.sm, backgroundColor: colors.cardHighest },
        animStyle,
        style,
      ]}
    />
  );
}

/** Skeleton placeholder mimicking a TicketCard while data loads. */
export function TicketCardSkeleton() {
  return (
    <View
      style={{
        backgroundColor: colors.card,
        borderRadius: radius.lg,
        padding: spacing.xl,
        gap: spacing.md,
        ...shadow.card,
      }}
    >
      <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
        <Shimmer width={90} height={22} style={{ borderRadius: radius.full }} />
        <Shimmer width={70} height={22} style={{ borderRadius: radius.full }} />
      </View>
      <Shimmer width="55%" height={20} />
      <Shimmer width="90%" height={14} />
      <Shimmer width="75%" height={14} />
      <Shimmer width="100%" height={54} style={{ borderRadius: radius.md, marginTop: 4 }} />
    </View>
  );
}

/** A list of skeleton cards. */
export function TicketListSkeleton({ count = 3 }: { count?: number }) {
  return (
    <View style={{ gap: spacing.base }}>
      {Array.from({ length: count }).map((_, i) => (
        <TicketCardSkeleton key={i} />
      ))}
    </View>
  );
}
