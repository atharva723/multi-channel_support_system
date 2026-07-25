import type BottomSheet from '@gorhom/bottom-sheet';
import { FlashList } from '@shopify/flash-list';
import { useFocusEffect } from 'expo-router';
import { ShieldCheck, Sparkles } from 'lucide-react-native';
import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RefreshControl, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type Ticket } from '../../src/api/client';
import { AppHeader } from '../../src/components/AppHeader';
import { AppText } from '../../src/components/AppText';
import { EmptyState } from '../../src/components/EmptyState';
import { ErrorState } from '../../src/components/ErrorState';
import { EscalationBanner } from '../../src/components/EscalationBanner';
import { ReplySheet } from '../../src/components/ReplySheet';
import { TicketCard } from '../../src/components/TicketCard';
import { TicketListSkeleton } from '../../src/components/TicketSkeleton';
import { useRealtimeStore } from '../../src/hooks/useRealtimeStore';
import { useTickets } from '../../src/hooks/useTickets';
import { hapticImpact } from '../../src/lib/haptics';
import { colors, radius, spacing } from '../../src/theme';

export default function EscalationDesk() {
  const { data, isLoading, isError, refetch, isRefetching } = useTickets();
  const sheetRef = useRef<BottomSheet>(null);
  const [selected, setSelected] = useState<Ticket | null>(null);
  const [banner, setBanner] = useState(false);
  const escalationSeq = useRealtimeStore((s) => s.escalationSeq);

  // Raise the banner whenever the app-wide stream signals a new escalation.
  useEffect(() => {
    if (escalationSeq === 0) return;
    setBanner(true);
    const t = setTimeout(() => setBanner(false), 6000);
    return () => clearTimeout(t);
  }, [escalationSeq]);

  // Refresh when the Desk regains focus so tab switches always show fresh data.
  useFocusEffect(
    useCallback(() => {
      refetch();
    }, [refetch]),
  );

  // Escalation Desk shows critical, still-pending tickets, highest urgency first.
  const escalations = useMemo(
    () =>
      (data ?? [])
        .filter((t) => t.status === 'PENDING' && t.criticality_score >= 0.8)
        .sort((a, b) => b.urgency_score - a.urgency_score),
    [data],
  );

  // Count of tickets the AI resolved on its own (non-critical auto-replies).
  const autoHandledCount = useMemo(
    () => (data ?? []).filter((t) => t.status === 'AUTO_REPLIED').length,
    [data],
  );

  const openTicket = useCallback((ticket: Ticket) => {
    hapticImpact();
    setSelected(ticket);
    sheetRef.current?.snapToIndex(0);
  }, []);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.surface }}>
      <AppHeader
        right={
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
            <View style={{ width: 8, height: 8, borderRadius: 4, backgroundColor: colors.success }} />
            <View style={{ backgroundColor: colors.card, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.full, flexDirection: 'row', gap: 6 }}>
              <AppText variant="labelMd" color={colors.onSurface}>
                Active Alerts
              </AppText>
              <View style={{ backgroundColor: colors.escalation, minWidth: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 5 }}>
                <AppText variant="labelSm" color={colors.white}>
                  {escalations.length}
                </AppText>
              </View>
            </View>
          </View>
        }
      />

      {banner ? (
        <EscalationBanner
          title="Critical Escalation"
          subtitle="New high-priority ticket just arrived"
          onPress={() => setBanner(false)}
        />
      ) : null}

      <View style={{ paddingHorizontal: spacing.page, paddingTop: spacing.base, paddingBottom: spacing.sm }}>
        <AppText variant="headlineLg">Escalation Desk</AppText>
        <AppText variant="bodyMd" color={colors.onSurfaceVariant}>
          Prioritize high-stakes customer resolutions.
        </AppText>
        {autoHandledCount > 0 ? (
          <View
            style={{
              flexDirection: 'row',
              alignItems: 'center',
              gap: 8,
              marginTop: spacing.md,
              backgroundColor: '#E7E9FD',
              paddingHorizontal: spacing.base,
              paddingVertical: 10,
              borderRadius: radius.md,
            }}
          >
            <Sparkles size={16} color={colors.actionIndigo} />
            <AppText variant="labelMd" color={colors.actionIndigo} style={{ flex: 1 }}>
              AI auto-handled {autoHandledCount} non-critical{' '}
              {autoHandledCount === 1 ? 'message' : 'messages'}
            </AppText>
          </View>
        ) : null}
      </View>

      {isLoading ? (
        <View style={{ padding: spacing.page, paddingTop: spacing.sm }}>
          <TicketListSkeleton count={3} />
        </View>
      ) : isError ? (
        <ErrorState
          title="Couldn't load alerts"
          message="We couldn't reach the server. Check your connection and try again."
          onRetry={refetch}
        />
      ) : (
        <FlashList
          data={escalations}
          keyExtractor={(t) => String(t.id)}
          contentContainerStyle={{ padding: spacing.page, paddingTop: spacing.sm }}
          ItemSeparatorComponent={() => <View style={{ height: spacing.base }} />}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />}
          renderItem={({ item }) => <TicketCard ticket={item} onPress={() => openTicket(item)} />}
          ListEmptyComponent={
            <EmptyState
              icon={<ShieldCheck size={40} color={colors.primary} />}
              title="All clear"
              subtitle="No critical escalations right now. New alerts will appear here instantly."
            />
          }
        />
      )}

      <ReplySheet ref={sheetRef} ticket={selected} onClose={() => setSelected(null)} />
    </SafeAreaView>
  );
}
