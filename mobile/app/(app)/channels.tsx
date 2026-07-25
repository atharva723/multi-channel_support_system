import type BottomSheet from '@gorhom/bottom-sheet';
import { useRouter } from 'expo-router';
import { AlertTriangle, Hash, Mail, Plus, RefreshCw, Server, Settings2, Trash2 } from 'lucide-react-native';
import React, { useCallback, useRef, useState } from 'react';
import { ActivityIndicator, Alert, Pressable, RefreshControl, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { type Connection } from '../../src/api/client';
import { AppHeader } from '../../src/components/AppHeader';
import { AppText } from '../../src/components/AppText';
import { Button } from '../../src/components/Button';
import { Card } from '../../src/components/Card';
import { EmptyState } from '../../src/components/EmptyState';
import { ErrorState } from '../../src/components/ErrorState';
import { GuildPickerSheet } from '../../src/components/GuildPickerSheet';
import { useConnections, useDeleteConnection } from '../../src/hooks/useConnections';
import { useAuthStore } from '../../src/hooks/useAuthStore';
import { useToastStore } from '../../src/hooks/useToastStore';
import { providerMeta } from '../../src/lib/channels';
import { shortDate } from '../../src/lib/time';
import { colors, radius, spacing } from '../../src/theme';

function ProviderGlyph({ provider }: { provider: string }) {
  const { color, soft } = providerMeta(provider);
  const Icon = provider === 'discord' ? Hash : Mail;
  return (
    <View style={{ width: 52, height: 52, borderRadius: radius.md, backgroundColor: soft, alignItems: 'center', justifyContent: 'center' }}>
      <Icon size={26} color={color} strokeWidth={2.5} />
    </View>
  );
}

export default function Channels() {
  const router = useRouter();
  const { data: connections, isLoading, isError, isRefetching, refetch } = useConnections();
  const del = useDeleteConnection();
  const connect = useAuthStore((s) => s.connect);
  const showToast = useToastStore((s) => s.show);
  const [reconnecting, setReconnecting] = useState<string | null>(null);

  const guildSheetRef = useRef<BottomSheet>(null);
  const [guildSheetActive, setGuildSheetActive] = useState(false);

  const openGuildPicker = useCallback(() => {
    setGuildSheetActive(true);
    guildSheetRef.current?.snapToIndex(0);
  }, []);

  const confirmRemove = (c: Connection) => {
    Alert.alert(
      'Disconnect channel',
      `Remove your ${providerMeta(c.provider).label} connection? Tickets from it will stop arriving.`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Remove',
          style: 'destructive',
          onPress: () =>
            del.mutate(c.id, {
              onSuccess: () => showToast(`${providerMeta(c.provider).label} disconnected`),
            }),
        },
      ],
    );
  };

  const reconnect = async (provider: string) => {
    try {
      setReconnecting(provider);
      const ok = await connect(provider as 'google' | 'discord');
      if (ok) {
        await refetch();
        showToast(`${providerMeta(provider).label} reconnected`, provider);
      }
    } catch (e: any) {
      Alert.alert('Reconnect failed', e?.message ?? 'Please try again.');
    } finally {
      setReconnecting(null);
    }
  };

  const hasDiscord = (connections ?? []).some((c) => c.provider === 'discord');
  const list = connections ?? [];

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.surface }}>
      <AppHeader />
      <ScrollView
        contentContainerStyle={{ padding: spacing.page, gap: spacing.lg, paddingBottom: spacing.xxxl }}
        refreshControl={<RefreshControl refreshing={isRefetching} onRefresh={refetch} tintColor={colors.primary} />}
      >
        <View style={{ gap: spacing.sm }}>
          <AppText variant="headlineLg">Communication Hub</AppText>
          <AppText variant="bodyMd" color={colors.onSurfaceVariant}>
            Manage the Discord and Gmail channels Sentinel watches for support requests.
          </AppText>
        </View>

        <AppText variant="labelMd" color={colors.primary} style={{ textTransform: 'uppercase' }}>
          Active Connections
        </AppText>

        {isLoading ? (
          <View style={{ alignItems: 'center', paddingVertical: spacing.xl }}>
            <ActivityIndicator color={colors.primary} />
          </View>
        ) : isError ? (
          <ErrorState
            title="Couldn't load channels"
            message="We couldn't reach the server. Pull to refresh or try again."
            onRetry={refetch}
          />
        ) : list.length === 0 ? (
          <EmptyState
            icon={<Server size={40} color={colors.primary} />}
            title="No channels connected"
            subtitle="Connect Discord or Gmail to start receiving triaged tickets."
          />
        ) : (
          list.map((c) => {
            const meta = providerMeta(c.provider);
            const isDiscord = c.provider === 'discord';
            const identity = c.email ?? c.display_name ?? '—';
            const busy = reconnecting === c.provider;
            return (
              <Card key={c.id} style={{ gap: spacing.base }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.base }}>
                  <ProviderGlyph provider={c.provider} />
                  <View style={{ flex: 1 }}>
                    <AppText variant="titleMd">{meta.label}</AppText>
                    <AppText variant="bodyMd" color={colors.onSurfaceVariant} numberOfLines={1}>
                      {identity}
                    </AppText>
                  </View>
                  {c.needs_reconnect ? (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#FDF0D5', paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.full }}>
                      <AlertTriangle size={13} color={colors.warning} />
                      <AppText variant="labelSm" color={colors.warning}>
                        Reconnect
                      </AppText>
                    </View>
                  ) : (
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: colors.secondaryContainer, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.full }}>
                      <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: colors.success }} />
                      <AppText variant="labelSm" color={colors.primary}>
                        Connected
                      </AppText>
                    </View>
                  )}
                </View>

                {isDiscord ? (
                  <Pressable
                    onPress={openGuildPicker}
                    style={{
                      flexDirection: 'row',
                      alignItems: 'center',
                      gap: spacing.sm,
                      backgroundColor: colors.cardMuted,
                      borderRadius: radius.md,
                      paddingHorizontal: spacing.base,
                      paddingVertical: 10,
                    }}
                  >
                    <Server size={16} color={colors.primary} />
                    <AppText variant="labelMd" color={colors.onSurface} style={{ flex: 1 }} numberOfLines={1}>
                      {c.external_ref ? `Watching server ${c.external_ref}` : 'No server selected'}
                    </AppText>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                      <Settings2 size={14} color={colors.primary} />
                      <AppText variant="labelSm" color={colors.primary}>
                        {c.external_ref ? 'Change' : 'Select'}
                      </AppText>
                    </View>
                  </Pressable>
                ) : null}

                <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
                  <AppText variant="labelSm" color={colors.outline} style={{ flex: 1, textTransform: 'uppercase' }}>
                    Since {shortDate(c.created_at)}
                  </AppText>
                  {c.needs_reconnect ? (
                    <Pressable
                      disabled={busy}
                      onPress={() => reconnect(c.provider)}
                      style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.full, backgroundColor: colors.primary }}
                    >
                      {busy ? (
                        <ActivityIndicator size="small" color={colors.white} />
                      ) : (
                        <>
                          <RefreshCw size={14} color={colors.white} />
                          <AppText variant="labelMd" color={colors.white}>
                            Reconnect
                          </AppText>
                        </>
                      )}
                    </Pressable>
                  ) : null}
                  <Pressable
                    onPress={() => confirmRemove(c)}
                    hitSlop={8}
                    style={{ flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 12, paddingVertical: 7, borderRadius: radius.full, backgroundColor: colors.errorContainer }}
                  >
                    <Trash2 size={14} color={colors.error} />
                    <AppText variant="labelMd" color={colors.error}>
                      Remove
                    </AppText>
                  </Pressable>
                </View>
              </Card>
            );
          })
        )}

        {hasDiscord ? (
          <Pressable onPress={openGuildPicker}>
            <View
              style={{
                flexDirection: 'row',
                alignItems: 'center',
                gap: spacing.base,
                backgroundColor: colors.card,
                borderRadius: radius.lg,
                borderWidth: 1.5,
                borderColor: colors.primaryFixedDim,
                borderStyle: 'dashed',
                padding: spacing.lg,
              }}
            >
              <View style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: colors.secondaryContainer, alignItems: 'center', justifyContent: 'center' }}>
                <Server size={22} color={colors.primary} />
              </View>
              <AppText variant="titleSm" style={{ flex: 1 }}>
                Choose Discord server
              </AppText>
            </View>
          </Pressable>
        ) : null}

        <Button
          label="Add channel"
          icon={<Plus size={20} color={colors.onPrimary} />}
          onPress={() => router.push('/(auth)/connect')}
        />
      </ScrollView>

      <GuildPickerSheet
        ref={guildSheetRef}
        active={guildSheetActive}
        onClose={() => setGuildSheetActive(false)}
      />
    </SafeAreaView>
  );
}
