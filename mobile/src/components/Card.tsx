import React from 'react';
import { View, type ViewProps } from 'react-native';

import { colors, radius, shadow, spacing } from '../theme';

/** White, rounded, softly-elevated "Sentinel Card" surface. */
export function Card({ style, ...rest }: ViewProps) {
  return (
    <View
      {...rest}
      style={[
        {
          backgroundColor: colors.card,
          borderRadius: radius.lg,
          padding: spacing.xl,
          ...shadow.card,
        },
        style,
      ]}
    />
  );
}
