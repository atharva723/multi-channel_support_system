import React from 'react';
import { View } from 'react-native';
import Svg, { Circle } from 'react-native-svg';

import { colors } from '../theme';
import { AppText } from './AppText';

interface Props {
  value: number; // 0..1
  label: string;
  color: string;
}

/** Small radial progress meter for criticality/urgency. */
export function Meter({ value, label, color }: Props) {
  const size = 96;
  const stroke = 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.min(Math.max(value, 0), 1);
  const offset = c * (1 - pct);

  return (
    <View style={{ alignItems: 'center', gap: 8, flex: 1 }}>
      <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
        <Svg width={size} height={size} style={{ position: 'absolute' }}>
          <Circle cx={size / 2} cy={size / 2} r={r} stroke={colors.cardHighest} strokeWidth={stroke} fill="none" />
          <Circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            stroke={color}
            strokeWidth={stroke}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={offset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
          />
        </Svg>
        <AppText variant="titleMd" color={color}>
          {Math.round(pct * 100)}%
        </AppText>
      </View>
      <AppText variant="labelSm" color={colors.outline} style={{ textTransform: 'uppercase' }}>
        {label}
      </AppText>
    </View>
  );
}
