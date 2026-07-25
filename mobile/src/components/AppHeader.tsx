import { Radio } from 'lucide-react-native';
import React from 'react';
import { View } from 'react-native';

import { colors, spacing } from '../theme';
import { AppText } from './AppText';

interface Props {
  title?: string;
  right?: React.ReactNode;
  live?: boolean;
}

/** Compact top brand bar with an optional live indicator. */
export function AppHeader({ title = 'Sentinel', right, live }: Props) {
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        justifyContent: 'space-between',
        paddingHorizontal: spacing.page,
        paddingVertical: spacing.md,
      }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
        <View
          style={{
            width: 32,
            height: 32,
            borderRadius: 10,
            backgroundColor: colors.primary,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <AppText variant="labelMd" color={colors.primaryFixed}>
            S
          </AppText>
        </View>
        <AppText variant="titleMd" color={colors.primary}>
          {title}
        </AppText>
      </View>
      {right ?? (
        <Radio size={20} color={live ? colors.success : colors.outline} strokeWidth={2.5} />
      )}
    </View>
  );
}
