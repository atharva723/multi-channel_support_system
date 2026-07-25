import React from 'react';
import { Pressable, ScrollView } from 'react-native';

import { colors, radius, spacing } from '../theme';
import { AppText } from './AppText';

interface Props<T extends string> {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}

export function SegmentedFilter<T extends string>({ options, value, onChange }: Props<T>) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={{ gap: spacing.sm, paddingHorizontal: spacing.page }}
    >
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <Pressable
            key={opt.value}
            onPress={() => onChange(opt.value)}
            style={{
              paddingHorizontal: 20,
              paddingVertical: 10,
              borderRadius: radius.full,
              backgroundColor: active ? colors.primary : colors.cardMuted,
            }}
          >
            <AppText variant="labelMd" color={active ? colors.onPrimary : colors.onSurfaceVariant}>
              {opt.label}
            </AppText>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}
