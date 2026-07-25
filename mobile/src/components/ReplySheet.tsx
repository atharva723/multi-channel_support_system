import BottomSheet, { BottomSheetBackdrop, BottomSheetTextInput, BottomSheetView } from '@gorhom/bottom-sheet';
import { Check, X } from 'lucide-react-native';
import React, { forwardRef, useCallback, useEffect, useMemo, useState } from 'react';
import { Alert, View } from 'react-native';

import { type Ticket } from '../api/client';
import { useToastStore } from '../hooks/useToastStore';
import { useUpdateTicket } from '../hooks/useTickets';
import { channelMeta } from '../lib/channels';
import { colors, radius, shadow, spacing } from '../theme';
import { AppText } from './AppText';
import { Button } from './Button';

interface Props {
  ticket: Ticket | null;
  onClose: () => void;
}

/** Slide-up sheet to edit + approve/send (or dismiss) an AI-drafted reply. */
export const ReplySheet = forwardRef<BottomSheet, Props>(({ ticket, onClose }, ref) => {
  const snapPoints = useMemo(() => ['55%', '90%'], []);
  const [draft, setDraft] = useState('');
  const update = useUpdateTicket();
  const showToast = useToastStore((s) => s.show);

  useEffect(() => {
    setDraft(ticket?.ai_draft_reply ?? '');
  }, [ticket?.id]);

  // Safety: if the selection is cleared while the sheet is still open, close it
  // so it can never sit open with no ticket (which rendered a blank sheet).
  useEffect(() => {
    if (!ticket && ref && typeof ref !== 'function') ref.current?.close();
  }, [ticket, ref]);

  const renderBackdrop = useCallback(
    (props: any) => <BottomSheetBackdrop {...props} disappearsOnIndex={-1} appearsOnIndex={0} opacity={0.4} />,
    [],
  );

  const closeSheet = useCallback(() => {
    if (ref && typeof ref !== 'function') ref.current?.close();
  }, [ref]);

  const submit = (status: 'APPROVED' | 'MODIFIED' | 'DISMISSED') => {
    if (!ticket) return;
    const edited = draft !== (ticket.ai_draft_reply ?? '');
    const channel = ticket.channel;
    const label = channelMeta(channel).label;
    update.mutate(
      {
        id: ticket.id,
        status: status === 'APPROVED' && edited ? 'MODIFIED' : status,
        reply: status === 'DISMISSED' ? undefined : draft,
      },
      {
        // Close the sheet immediately (never leave it blank) and surface a
        // transient success toast confirming where the reply went.
        onSuccess: () => {
          closeSheet();
          if (status !== 'DISMISSED') {
            showToast(`Reply sent via ${label}`, channel);
          }
        },
        onError: (e: any) => {
          // Keep the sheet open so the draft isn't lost; explain what failed.
          Alert.alert(
            'Couldn\u2019t send the reply',
            e?.message ?? 'Please try again. If it keeps failing, reconnect the channel in Channels.',
          );
        },
      },
    );
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
      <BottomSheetView style={{ flex: 1, padding: spacing.page, gap: spacing.lg }}>
        {ticket ? (
          <>
            <View style={{ gap: 4 }}>
              <AppText variant="labelSm" color={colors.outline} style={{ textTransform: 'uppercase' }}>
                Edit draft reply
              </AppText>
              <AppText variant="titleMd">Override response for {ticket.author_name}</AppText>
            </View>

            <View
              style={{
                backgroundColor: colors.card,
                borderRadius: radius.lg,
                borderWidth: 2,
                borderColor: colors.primaryFixedDim,
                padding: spacing.base,
                minHeight: 160,
                ...shadow.card,
              }}
            >
              <BottomSheetTextInput
                multiline
                value={draft}
                onChangeText={setDraft}
                placeholder="Write your reply…"
                placeholderTextColor={colors.outline}
                style={{
                  color: colors.onSurface,
                  fontSize: 16,
                  lineHeight: 24,
                  fontFamily: 'HankenGrotesk_400Regular',
                  textAlignVertical: 'top',
                  flex: 1,
                }}
              />
            </View>

            <View style={{ gap: spacing.md, marginTop: 'auto' }}>
              <Button
                label="Approve & Send"
                loading={update.isPending}
                icon={<Check size={20} color={colors.onPrimary} />}
                onPress={() => submit('APPROVED')}
              />
              <Button
                label="Dismiss"
                variant="ghost"
                icon={<X size={18} color={colors.primary} />}
                onPress={() => submit('DISMISSED')}
              />
            </View>
          </>
        ) : null}
      </BottomSheetView>
    </BottomSheet>
  );
});

ReplySheet.displayName = 'ReplySheet';
