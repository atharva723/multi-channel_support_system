import React from 'react';
import { Text as RNText, type TextProps } from 'react-native';

import { colors, type, type TypeToken } from '../theme';

type Props = TextProps & {
  variant?: TypeToken;
  color?: string;
  center?: boolean;
};

/** Themed text primitive that applies a typography token + color. */
export function AppText({
  variant = 'bodyMd',
  color = colors.onSurface,
  center,
  style,
  ...rest
}: Props) {
  return (
    <RNText
      {...rest}
      style={[type[variant], { color }, center && { textAlign: 'center' }, style]}
    />
  );
}
