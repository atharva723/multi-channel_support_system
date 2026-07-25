import React from 'react';
import { View } from 'react-native';

import { colors, radius } from '../theme';
import { type TicketStatus } from '../api/client';
import { AppText } from './AppText';

const STYLES: Record<TicketStatus, { bg: string; fg: string; label: string }> = {
  PENDING: { bg: '#FDEFD6', fg: colors.warning, label: 'Pending' },
  APPROVED: { bg: '#D6F5E6', fg: colors.success, label: 'Approved' },
  MODIFIED: { bg: '#D6F5E6', fg: colors.success, label: 'Sent' },
  DISMISSED: { bg: colors.cardHighest, fg: colors.outline, label: 'Dismissed' },
  AUTO_REPLIED: { bg: '#E7E9FD', fg: colors.actionIndigo, label: 'Auto-replied' },
};

export function StatusChip({ status }: { status: TicketStatus }) {
  const s = STYLES[status] ?? STYLES.PENDING;
  return (
    <View
      style={{
        backgroundColor: s.bg,
        paddingHorizontal: 10,
        paddingVertical: 4,
        borderRadius: radius.full,
      }}
    >
      <AppText variant="labelSm" color={s.fg}>
        {s.label}
      </AppText>
    </View>
  );
}
