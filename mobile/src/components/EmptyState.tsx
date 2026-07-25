import React from 'react';
import { View } from 'react-native';

import { colors, spacing } from '../theme';
import { AppText } from './AppText';

interface Props {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
}

/** Centered empty/placeholder state. */
export function EmptyState({ icon, title, subtitle }: Props) {
  return (
    <View style={{ alignItems: 'center', justifyContent: 'center', paddingVertical: spacing.xxxl * 2, gap: spacing.md }}>
      <View
        style={{
          width: 88,
          height: 88,
          borderRadius: 44,
          backgroundColor: colors.secondaryContainer,
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        {icon}
      </View>
      <AppText variant="titleMd" center>
        {title}
      </AppText>
      {subtitle ? (
        <AppText variant="bodyMd" color={colors.outline} center style={{ maxWidth: 260 }}>
          {subtitle}
        </AppText>
      ) : null}
    </View>
  );
}
