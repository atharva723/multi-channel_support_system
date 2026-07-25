import React from 'react';
import { ActivityIndicator, Pressable, View, type PressableProps } from 'react-native';

import { colors, radius, shadow } from '../theme';
import { AppText } from './AppText';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

type Props = Omit<PressableProps, 'children'> & {
  label: string;
  variant?: Variant;
  loading?: boolean;
  icon?: React.ReactNode;
  fullWidth?: boolean;
};

const bg: Record<Variant, string> = {
  primary: colors.primary,
  secondary: colors.actionIndigo,
  ghost: colors.transparent,
  danger: colors.transparent,
};

const fg: Record<Variant, string> = {
  primary: colors.onPrimary,
  secondary: colors.white,
  ghost: colors.primary,
  danger: colors.error,
};

/** Pill-shaped primary action button with spring press feedback. */
export function Button({
  label,
  variant = 'primary',
  loading,
  icon,
  fullWidth = true,
  disabled,
  style,
  ...rest
}: Props) {
  const isFilled = variant === 'primary' || variant === 'secondary';
  return (
    <Pressable
      disabled={disabled || loading}
      style={({ pressed }) => [
        {
          height: 56,
          borderRadius: radius.full,
          alignItems: 'center',
          justifyContent: 'center',
          flexDirection: 'row',
          gap: 8,
          paddingHorizontal: 24,
          backgroundColor: bg[variant],
          borderWidth: variant === 'ghost' || variant === 'danger' ? 1.5 : 0,
          borderColor:
            variant === 'danger' ? colors.error : colors.outlineVariant,
          opacity: disabled ? 0.5 : 1,
          transform: [{ scale: pressed ? 0.97 : 1 }],
          ...(isFilled ? shadow.fab : {}),
        },
        fullWidth ? { alignSelf: 'stretch' } : { alignSelf: 'flex-start' },
        style as object,
      ]}
      {...rest}
    >
      {loading ? (
        <ActivityIndicator color={fg[variant]} />
      ) : (
        <>
          {icon ? <View>{icon}</View> : null}
          <AppText variant="titleSm" color={fg[variant]}>
            {label}
          </AppText>
        </>
      )}
    </Pressable>
  );
}
