import { Sparkles } from 'lucide-react-native';
import React from 'react';
import { Pressable, View } from 'react-native';

import { type Ticket } from '../api/client';
import { colors, radius, spacing } from '../theme';
import { relativeTime } from '../lib/time';
import { ticketDisplay } from '../lib/ticket';
import { AppText } from './AppText';
import { Card } from './Card';
import { ChannelPill } from './ChannelPill';
import { UrgencyBadge } from './UrgencyBadge';

interface Props {
  ticket: Ticket;
  onPress: () => void;
}

/** Escalation Desk card: channel, author/subject, excerpt, urgency, AI draft preview. */
export function TicketCard({ ticket, onPress }: Props) {
  const d = ticketDisplay(ticket);
  return (
    <Pressable onPress={onPress} style={({ pressed }) => ({ transform: [{ scale: pressed ? 0.99 : 1 }] })}>
      <Card style={{ gap: spacing.md }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <ChannelPill channel={ticket.channel} />
            <AppText variant="labelSm" color={colors.outline}>
              · {relativeTime(ticket.created_at)}
            </AppText>
          </View>
          <UrgencyBadge score={ticket.urgency_score} />
        </View>

        <View style={{ gap: 3 }}>
          <AppText variant="titleMd" numberOfLines={1}>
            {d.heading}
          </AppText>
          {d.subheading ? (
            <AppText variant="labelMd" color={colors.outline}>
              from {d.subheading}
            </AppText>
          ) : null}
          <AppText
            variant="bodyMd"
            color={colors.onSurfaceVariant}
            numberOfLines={2}
            style={{ marginTop: 2 }}
          >
            &ldquo;{d.body}&rdquo;
          </AppText>
        </View>

        {ticket.ai_draft_reply ? (
          <View
            style={{
              backgroundColor: colors.cardLow,
              borderRadius: radius.md,
              borderWidth: 1,
              borderColor: colors.outlineVariant,
              borderStyle: 'dashed',
              padding: spacing.base,
              gap: 4,
            }}
          >
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Sparkles size={13} color={colors.primary} />
              <AppText variant="labelSm" color={colors.primary} style={{ textTransform: 'uppercase' }}>
                AI Draft Ready
              </AppText>
            </View>
            <AppText variant="bodyMd" color={colors.onSurfaceVariant} numberOfLines={1} style={{ fontStyle: 'italic' }}>
              &ldquo;{ticket.ai_draft_reply}&rdquo;
            </AppText>
          </View>
        ) : null}
      </Card>
    </Pressable>
  );
}
