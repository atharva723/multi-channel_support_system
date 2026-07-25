import BottomSheet, { BottomSheetBackdrop, BottomSheetFlatList, BottomSheetView } from '@gorhom/bottom-sheet';
import { Check, Hash } from 'lucide-react-native';
import React, { forwardRef, useCallback, useMemo } from 'react';
import { ActivityIndicator, Pressable, View } from 'react-native';

import { useDiscordGuilds, useLinkGuild } from '../hooks/useConnections';
import { useToastStore } from '../hooks/useToastStore';
import { colors, radius, spacing } from '../theme';
import { AppText } from './AppText';

type Guild = { id: string; name: string };

interface Props {
  /** Whether the sheet is currently mounted/active (drives the guilds query). */
  active: boolean;
  onClose: () => void;
}

/**
 * Bottom sheet that lists the Discord servers the connected user is in and lets
 * them pick which one Sentinel should watch for support messages. The currently
 * linked server is highlighted with a check.
 */
export const GuildPickerSheet = forwardRef<BottomSheet, Props>(({ active, onClose }, ref) => {
  const snapPoints = useMemo(() => ['60%'], []);
  const { data, isLoading, isError, refetch } = useDiscordGuilds(active);
  const link = useLinkGuild();
  const showToast = useToastStore((s) => s.show);

  const renderBackdrop = useCallback(
    (props: any) => <BottomSheetBackdrop {...props} disappearsOnIndex={-1} appearsOnIndex={0} opacity={0.4} />,
    [],
  );

  const closeSheet = useCallback(() => {
    if (ref && typeof ref !== 'function') ref.current?.close();
  }, [ref]);

  const pick = (guildId: string, name: string) => {
    link.mutate(guildId, {
      onSuccess: () => {
        closeSheet();
        showToast(`Watching #${name}`, 'discord');
      },
    });
  };

  return (
    <BottomSheet
      ref={ref}
      index={-1}
      snapPoints={snapPoints}
      enablePanDownToClose
      onClose={onClose}
      backdropComponent={renderBackdrop}
      backgroundStyle={{ backgroundColor: colors.surface, borderTopLeftRadius: radius.xxl, borderTopRightRadius: radius.xxl }}
      handleIndicatorStyle={{ backgroundColor: colors.outlineVariant, width: 44, height: 5 }}
    >
      <BottomSheetView style={{ paddingHorizontal: spacing.page, paddingBottom: spacing.md, gap: 4 }}>
        <AppText variant="labelSm" color={colors.outline} style={{ textTransform: 'uppercase' }}>
          Discord
        </AppText>
        <AppText variant="titleMd">Choose a server to watch</AppText>
      </BottomSheetView>

      {isLoading ? (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', paddingVertical: spacing.xl }}>
          <ActivityIndicator color={colors.primary} />
        </View>
      ) : isError ? (
        <View style={{ padding: spacing.page, gap: spacing.md, alignItems: 'center' }}>
          <AppText variant="bodyMd" color={colors.onSurfaceVariant} center>
            Couldn&apos;t load your servers.
          </AppText>
          <Pressable onPress={() => refetch()}>
            <AppText variant="titleSm" color={colors.primary}>
              Try again
            </AppText>
          </Pressable>
        </View>
      ) : (
        <BottomSheetFlatList
          data={(data?.guilds ?? []) as Guild[]}
          keyExtractor={(g: Guild) => g.id}
          contentContainerStyle={{ padding: spacing.page, paddingTop: 0, gap: spacing.sm }}
          ListEmptyComponent={
            <AppText variant="bodyMd" color={colors.onSurfaceVariant} center style={{ paddingVertical: spacing.xl }}>
              No servers found for this Discord account.
            </AppText>
          }
          renderItem={({ item }: { item: Guild }) => {
            const linked = data?.linked_guild === item.id;
            const busy = link.isPending && link.variables === item.id;
            return (
              <Pressable
                disabled={link.isPending}
                onPress={() => pick(item.id, item.name)}
                style={{
                  flexDirection: 'row',
                  alignItems: 'center',
                  gap: spacing.md,
                  backgroundColor: linked ? colors.secondaryContainer : colors.card,
                  borderRadius: radius.lg,
                  borderWidth: linked ? 1.5 : 1,
                  borderColor: linked ? colors.primary : colors.cardHighest,
                  padding: spacing.base,
                }}
              >
                <View style={{ width: 40, height: 40, borderRadius: radius.md, backgroundColor: colors.discordSoft, alignItems: 'center', justifyContent: 'center' }}>
                  <Hash size={20} color={colors.discord} strokeWidth={2.5} />
                </View>
                <AppText variant="titleSm" style={{ flex: 1 }} numberOfLines={1}>
                  {item.name}
                </AppText>
                {busy ? (
                  <ActivityIndicator color={colors.primary} />
                ) : linked ? (
                  <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' }}>
                    <Check size={16} color={colors.white} strokeWidth={3} />
                  </View>
                ) : null}
              </Pressable>
            );
          }}
        />
      )}
    </BottomSheet>
  );
});

GuildPickerSheet.displayName = 'GuildPickerSheet';
