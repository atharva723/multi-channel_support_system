import { AlertTriangle, RefreshCw } from 'lucide-react-native';
import React from 'react';
import { Pressable, View } from 'react-native';

import { colors, radius, spacing } from '../theme';
import { AppText } from './AppText';

interface Props {
  title?: string;
  message?: string;
  onRetry?: () => void;
}

/** Centered error state with a retry action. */
export function ErrorState({
  title = "Couldn't load",
  message = 'Check your connection and try again.',
  onRetry,
}: Props) {
  return (
    <View
      style={{
        alignItems: 'center',
        justifyContent: 'center',
        paddingVertical: spacing.xxxl * 2,
        gap: spacing.md,
      }}
    >
      <View
        style={{
          width: 88,
          height: 88,
          borderRadius: 44,
          backgroundColor: '#FEE4E9',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <AlertTriangle size={40} color={colors.escalation} />
      </View>
      <AppText variant="titleMd" center>
        {title}
      </AppText>
      <AppText variant="bodyMd" color={colors.outline} center style={{ maxWidth: 280 }}>
        {message}
      </AppText>
      {onRetry ? (
        <Pressable
          onPress={onRetry}
          style={({ pressed }) => ({
            flexDirection: 'row',
            alignItems: 'center',
            gap: 8,
            marginTop: spacing.sm,
            paddingHorizontal: 20,
            paddingVertical: 12,
            borderRadius: radius.full,
            backgroundColor: colors.primary,
            transform: [{ scale: pressed ? 0.97 : 1 }],
          })}
        >
          <RefreshCw size={16} color={colors.onPrimary} />
          <AppText variant="labelMd" color={colors.onPrimary}>
            Try again
          </AppText>
        </Pressable>
      ) : null}
    </View>
  );
}
