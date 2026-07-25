import { Zap } from 'lucide-react-native';
import React from 'react';
import { View } from 'react-native';

import { colors, radius } from '../theme';
import { AppText } from './AppText';

/**
 * Urgency chip. Color escalates with the score:
 *  >= 7 rose (critical), >= 4 amber (elevated), else muted.
 */
export function UrgencyBadge({ score, label = 'Priority' }: { score: number; label?: string }) {
  const tier = score >= 7 ? colors.escalation : score >= 4 ? colors.warning : colors.outline;
  const soft = score >= 7 ? '#FEE4E9' : score >= 4 ? '#FDEFD6' : colors.cardMuted;
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: 4,
        backgroundColor: soft,
        paddingHorizontal: 10,
        paddingVertical: 5,
        borderRadius: radius.full,
      }}
    >
      {score >= 4 ? <Zap size={12} color={tier} fill={tier} /> : null}
      <AppText variant="labelMd" color={tier}>
        {label} {score.toFixed(1)}
      </AppText>
    </View>
  );
}
