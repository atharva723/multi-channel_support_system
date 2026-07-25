import { ArrowRight, Lock } from 'lucide-react-native';
import React from 'react';
import { ActivityIndicator, Pressable, View } from 'react-native';

import { colors, radius, shadow, spacing } from '../theme';
import { AppText } from './AppText';

interface Props {
  name: string;
  description: string;
  icon: React.ReactNode;
  iconBg: string;
  accent: string;
  onConnect: () => void;
  loading?: boolean;
  comingSoon?: boolean;
}

/** A connectable provider card (Discord / Gmail). */
export function ProviderCard({
  name,
  description,
  icon,
  iconBg,
  accent,
  onConnect,
  loading,
  comingSoon,
}: Props) {
  return (
    <View
      style={{
        backgroundColor: comingSoon ? colors.cardMuted : colors.card,
        borderRadius: radius.lg,
        padding: spacing.lg,
        gap: spacing.base,
        ...(comingSoon ? {} : shadow.card),
      }}
    >
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.md }}>
        <View
          style={{
            width: 52,
            height: 52,
            borderRadius: radius.md,
            backgroundColor: iconBg,
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {icon}
        </View>
        <View style={{ flex: 1 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <AppText variant="titleMd">{name}</AppText>
            {comingSoon ? (
              <View style={{ backgroundColor: colors.cardHighest, paddingHorizontal: 8, paddingVertical: 3, borderRadius: radius.full }}>
                <AppText variant="labelSm" color={colors.outline}>
                  Coming soon
                </AppText>
              </View>
            ) : null}
          </View>
          <AppText variant="bodyMd" color={colors.onSurfaceVariant}>
            {description}
          </AppText>
        </View>
      </View>

      <Pressable
        disabled={comingSoon || loading}
        onPress={onConnect}
        style={({ pressed }) => ({
          height: 50,
          borderRadius: radius.full,
          backgroundColor: comingSoon ? colors.outlineVariant : accent,
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'row',
          gap: 8,
          transform: [{ scale: pressed ? 0.98 : 1 }],
        })}
      >
        {loading ? (
          <ActivityIndicator color={colors.white} />
        ) : (
          <>
            <AppText variant="titleSm" color={colors.white}>
              Connect
            </AppText>
            {comingSoon ? (
              <Lock size={16} color={colors.white} />
            ) : (
              <ArrowRight size={18} color={colors.white} />
            )}
          </>
        )}
      </Pressable>
    </View>
  );
}
