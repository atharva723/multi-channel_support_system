import { FlashList } from '@shopify/flash-list';
import { useFocusEffect, useRouter } from 'expo-router';
import { Clock, Inbox as InboxIcon, Search } from 'lucide-react-native';
import React, { useCallback, useMemo, useState } from 'react';
import { Pressable, RefreshControl, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type Ticket, type TicketStatus } from '../../src/api/client';
import { AppHeader } from '../../src/components/AppHeader';
import { AppText } from '../../src/components/AppText';
import { Card } from '../../src/components/Card';
import { ChannelPill } from '../../src/components/ChannelPill';
import { EmptyState } from '../../src/components/EmptyState';
import { ErrorState } from '../../src/components/ErrorState';
import { SegmentedFilter } from '../../src/components/SegmentedFilter';
import { StatusChip } from '../../src/components/StatusChip';
import { TicketListSkeleton } from '../../src/components/TicketSkeleton';
import { useTickets } from '../../src/hooks/useTickets';
import { relativeTime } from '../../src/lib/time';
import { ticketDisplay } from '../../src/lib/ticket';
import { colors, radius, spacing } from '../../src/theme';

type Filter = 'ALL' | TicketStatus;

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'APPROVED', label: 'Approved' },
  { value: 'AUTO_REPLIED', label: 'Auto' },
  { value: 'DISMISSED', label: 'Dismissed' },
];

export default function Inbox() {
  const router = useRouter();
  const { data, isLoading, isError, isRefetching, refetch } = useTickets();
  const [filter, setFilter] = useState<Filter>('ALL');
  const [q, setQ] = useState('');

  // Refresh when the Inbox regains focus so realtime/auto-reply status is current.
  useFocusEffect(
    useCallback(() => {
      refetch();
    }, [refetch]),
  );

  const rows = useMemo(() => {
    let list = data ?? [];
    if (filter !== 'ALL') list = list.filter((t) => t.status === filter || (filter === 'APPROVED' && t.status === 'MODIFIED'));
    if (q.trim()) {
      const needle = q.toLowerCase();
      list = list.filter(
        (t) => t.author_name.toLowerCase().includes(needle) || t.content.toLowerCase().includes(needle),
      );
    }
    // Newest first. Sort by id (monotonic with creation) — reliable across JS
    // engines regardless of timestamp string parsing quirks.
    return [...list].sort((a, b) => b.id - a.id);
  }, [data, filter, q]);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.surface }}>
      <AppHeader />

      <View style={{ paddingHorizontal: spacing.page, paddingVertical: spacing.sm, gap: spacing.base }}>
        <View
          style={{
            flexDirection: 'row',
            alignItems: 'center',
            gap: spacing.md,
            backgroundColor: colors.cardMuted,
            borderRadius: radius.full,
            paddingHorizontal: spacing.base,
            height: 50,
          }}
        >
          <Search size={20} color={colors.outline} />
          <TextInput
            value={q}
            onChangeText={setQ}
            placeholder="Search tickets…"
            placeholderTextColor={colors.outline}
            style={{ flex: 1, fontFamily: 'HankenGrotesk_400Regular', fontSize: 16, color: colors.onSurface }}
          />
        </View>
      </View>

      <View style={{ paddingBottom: spacing.md }}>
        <SegmentedFilter options={FILTERS} value={filter} onChange={setFilter} />
      </View>

      {isLoading ? (
        <View style={{ padding: spacing.page, paddingTop: spacing.sm }}>
          <TicketListSkeleton count={4} />
        </View>
      ) : isError ? (
        <ErrorState
          title="Couldn't load tickets"
          message="We couldn't reach the server. Check your connection and try again."
          onRetry={refetch}
        />
      ) : (
        <FlashList
          data={rows}
          keyExtractor={(t) => String(t.id)}
          contentContainerStyle={{ padding: spacing.page, paddingTop: spacing.sm }}
          ItemSeparatorComponent={() => <View style={{ height: spacing.base }} />}
          refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />}
          renderItem={({ item }: { item: Ticket }) => (
            <Pressable onPress={() => router.push(`/ticket/${item.id}`)}>
              <Card style={{ gap: spacing.sm }}>
                <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                  <ChannelPill channel={item.channel} />
                  <StatusChip status={item.status} />
                </View>
                <AppText variant="titleSm" numberOfLines={1}>
                  {ticketDisplay(item).heading}
                </AppText>
                <AppText variant="bodyMd" color={colors.onSurfaceVariant} numberOfLines={2}>
                  &ldquo;{ticketDisplay(item).body}&rdquo;
                </AppText>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Clock size={13} color={colors.outline} />
                  <AppText variant="labelSm" color={colors.outline}>
                    {relativeTime(item.created_at)}
                  </AppText>
                </View>
              </Card>
            </Pressable>
          )}
          ListEmptyComponent={
            <EmptyState
              icon={<InboxIcon size={40} color={colors.primary} />}
              title={q || filter !== 'ALL' ? 'No matches' : 'No tickets yet'}
              subtitle={
                q || filter !== 'ALL'
                  ? 'Try a different search or filter.'
                  : 'Incoming support messages will show up here once your channels are active.'
              }
            />
          }
        />
      )}
    </SafeAreaView>
  );
}
