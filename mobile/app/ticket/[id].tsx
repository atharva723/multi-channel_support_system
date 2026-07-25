import { useLocalSearchParams, useRouter } from 'expo-router';
import { AlertCircle, AlertTriangle, ArrowLeft, Check, RefreshCw, Sparkles, X } from 'lucide-react-native';
import React, { useEffect, useRef, useState } from 'react';
import { Animated, KeyboardAvoidingView, Platform, Pressable, ScrollView, TextInput, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ApiError } from '../../src/api/client';
import { AppText } from '../../src/components/AppText';
import { Button } from '../../src/components/Button';
import { Card } from '../../src/components/Card';
import { ChannelPill } from '../../src/components/ChannelPill';
import { Meter } from '../../src/components/Meter';
import { StatusChip } from '../../src/components/StatusChip';
import { useTicket, useUpdateTicket } from '../../src/hooks/useTickets';
import { useToastStore } from '../../src/hooks/useToastStore';
import { channelMeta } from '../../src/lib/channels';
import { relativeTime } from '../../src/lib/time';
import { ticketDisplay } from '../../src/lib/ticket';
import { colors, radius, spacing } from '../../src/theme';

const SENT_STATUSES = ['APPROVED', 'MODIFIED', 'AUTO_REPLIED'];

export default function TicketDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const ticketId = Number(id);
  const { data: ticket, isLoading } = useTicket(ticketId);
  const update = useUpdateTicket();
  const showToast = useToastStore((s) => s.show);
  const [draft, setDraft] = useState('');
  const [justSent, setJustSent] = useState(false);
  const [sendError, setSendError] = useState<string | null>(null);

  useEffect(() => {
    if (ticket) setDraft(ticket.ai_draft_reply ?? '');
  }, [ticket?.id]);

  const submit = (status: 'APPROVED' | 'MODIFIED' | 'DISMISSED') => {
    if (!ticket) return;
    setSendError(null);
    const edited = draft !== (ticket.ai_draft_reply ?? '');
    const label = channelMeta(ticket.channel).label;
    update.mutate(
      {
        id: ticket.id,
        status: status === 'APPROVED' && edited ? 'MODIFIED' : status,
        reply: status === 'DISMISSED' ? undefined : draft,
      },
      {
        onSuccess: () => {
          if (status === 'DISMISSED') {
            router.back();
          } else {
            setJustSent(true);
            showToast(`Reply sent via ${label}`, ticket.channel);
          }
        },
        onError: (e: unknown) => {
          // A 502 means the reply couldn't leave through the channel (usually an
          // expired token). Surface it inline with a reconnect path.
          const msg =
            e instanceof ApiError
              ? e.message
              : 'Something went wrong. Please try again.';
          setSendError(msg);
        },
      },
    );
  };

  const showConfirmation = !!ticket && (justSent || SENT_STATUSES.includes(ticket.status));
  const sentMeta = ticket ? channelMeta(ticket.channel) : null;
  const recipient = ticket ? ticketDisplay(ticket).subheading || ticket.author_name : '';
  const sentVerb = ticket?.status === 'AUTO_REPLIED' ? 'Auto-replied' : 'Reply sent';
  const isCritical = !!ticket && ticket.criticality_score >= 0.8;
  // A send failure that looks token-related gets a "Reconnect channel" hint.
  const looksLikeAuth = !!sendError && /token|auth|expired|reconnect|401|403/i.test(sendError);

  // Entrance animation for the "sent" confirmation card.
  const confirmAnim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    if (showConfirmation) {
      confirmAnim.setValue(0);
      Animated.spring(confirmAnim, {
        toValue: 1,
        useNativeDriver: true,
        friction: 7,
        tension: 60,
      }).start();
    }
  }, [showConfirmation, confirmAnim]);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: spacing.page, paddingVertical: spacing.md }}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <ArrowLeft size={26} color={colors.onSurface} />
        </Pressable>
        <AppText variant="titleMd" color={colors.primary}>
          Ticket Detail
        </AppText>
        <View style={{ width: 26 }} />
      </View>

      {ticket ? (
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
          keyboardVerticalOffset={Platform.OS === 'ios' ? 8 : 0}
        >
          <ScrollView
            contentContainerStyle={{ padding: spacing.page, gap: spacing.lg, paddingBottom: 220 }}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="interactive"
            showsVerticalScrollIndicator={false}
          >
          <Card style={{ gap: spacing.md }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <ChannelPill channel={ticket.channel} />
                <StatusChip status={ticket.status} />
              </View>
              <AppText variant="labelSm" color={colors.outline}>
                {relativeTime(ticket.created_at)}
              </AppText>
            </View>
            <AppText variant="titleMd">{ticketDisplay(ticket).heading}</AppText>
            {ticketDisplay(ticket).subheading ? (
              <AppText variant="labelMd" color={colors.outline}>
                from {ticketDisplay(ticket).subheading}
              </AppText>
            ) : null}
            <AppText variant="bodyLg" color={colors.onSurfaceVariant}>
              {ticketDisplay(ticket).body}
            </AppText>
          </Card>

          <View style={{ flexDirection: 'row', gap: spacing.base }}>
            <Card style={{ flex: 1, alignItems: 'center' }}>
              <Meter value={ticket.criticality_score} label="Criticality" color={colors.escalation} />
            </Card>
            <Card style={{ flex: 1, alignItems: 'center' }}>
              <Meter value={Math.min(ticket.urgency_score / 10, 1)} label="Urgency" color={colors.warning} />
            </Card>
          </View>

          <Card style={{ gap: spacing.md, backgroundColor: colors.cardMuted }}>
            <AppText variant="titleSm">Ticket Status</AppText>
            <View style={{ flexDirection: 'row', gap: spacing.md, alignItems: 'center' }}>
              <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: isCritical ? colors.escalation : colors.actionIndigo, alignItems: 'center', justifyContent: 'center' }}>
                {isCritical ? <AlertCircle size={18} color={colors.white} /> : <Sparkles size={16} color={colors.white} />}
              </View>
              <View>
                <AppText variant="labelMd">{isCritical ? 'Escalated' : 'Auto-handled'}</AppText>
                <AppText variant="labelSm" color={colors.outline}>
                  {isCritical ? 'Automated Sentinel Trigger' : 'Below escalation threshold'}
                </AppText>
              </View>
            </View>
            <View style={{ flexDirection: 'row', gap: spacing.md, alignItems: 'center' }}>
              <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: colors.primary, alignItems: 'center', justifyContent: 'center' }}>
                <Sparkles size={16} color={colors.white} />
              </View>
              <View>
                <AppText variant="labelMd">AI Draft Prepared</AppText>
                <AppText variant="labelSm" color={colors.outline}>
                  llama3.2 · High precision
                </AppText>
              </View>
            </View>
          </Card>

          {showConfirmation && sentMeta ? (
            <Animated.View
              style={{
                opacity: confirmAnim,
                transform: [
                  { scale: confirmAnim.interpolate({ inputRange: [0, 1], outputRange: [0.94, 1] }) },
                  { translateY: confirmAnim.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) },
                ],
              }}
            >
              <Card style={{ gap: spacing.md, backgroundColor: '#E7F6EC', borderWidth: 1, borderColor: '#B8E6C8' }}>
                <View style={{ flexDirection: 'row', gap: spacing.md, alignItems: 'center' }}>
                  <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.success, alignItems: 'center', justifyContent: 'center' }}>
                    <Check size={22} color={colors.white} strokeWidth={3} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                      <sentMeta.Icon size={15} color={sentMeta.color} strokeWidth={2.5} />
                      <AppText variant="labelMd">
                        {sentVerb} via {sentMeta.label}
                      </AppText>
                    </View>
                    {recipient ? (
                      <AppText variant="labelSm" color={colors.outline} style={{ marginTop: 2 }}>
                        to {recipient}
                      </AppText>
                    ) : null}
                  </View>
                </View>
              </Card>
            </Animated.View>
          ) : null}

          <View style={{ gap: spacing.md }}>
            <AppText variant="labelMd" color={colors.primary} style={{ textTransform: 'uppercase' }}>
              {showConfirmation ? 'Reply' : 'AI Draft Reply'}
            </AppText>
            <View
              style={{
                backgroundColor: colors.card,
                borderRadius: radius.lg,
                borderWidth: 2,
                borderColor: showConfirmation ? colors.cardMuted : colors.primaryFixedDim,
                padding: spacing.base,
                minHeight: 140,
              }}
            >
              <TextInput
                multiline
                editable={!showConfirmation}
                value={draft}
                onChangeText={setDraft}
                placeholder="Edit the reply…"
                placeholderTextColor={colors.outline}
                style={{
                  color: showConfirmation ? colors.onSurfaceVariant : colors.onSurface,
                  fontSize: 16,
                  lineHeight: 24,
                  fontFamily: 'HankenGrotesk_400Regular',
                  textAlignVertical: 'top',
                  minHeight: 110,
                }}
              />
            </View>
          </View>

          {sendError ? (
            <Card style={{ gap: spacing.md, backgroundColor: colors.errorContainer, borderWidth: 1, borderColor: '#F5C6C2' }}>
              <View style={{ flexDirection: 'row', gap: spacing.md, alignItems: 'flex-start' }}>
                <AlertTriangle size={20} color={colors.error} style={{ marginTop: 2 }} />
                <View style={{ flex: 1 }}>
                  <AppText variant="labelMd" color={colors.error}>
                    Couldn&apos;t send the reply
                  </AppText>
                  <AppText variant="bodyMd" color={colors.onSurfaceVariant} style={{ marginTop: 2 }}>
                    {looksLikeAuth
                      ? 'This channel needs to be reconnected before replies can go out.'
                      : sendError}
                  </AppText>
                </View>
              </View>
              {looksLikeAuth ? (
                <Pressable
                  onPress={() => router.push('/(app)/channels')}
                  style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, backgroundColor: colors.primary, borderRadius: radius.full, paddingVertical: 12 }}
                >
                  <RefreshCw size={16} color={colors.white} />
                  <AppText variant="titleSm" color={colors.white}>
                    Reconnect channel
                  </AppText>
                </Pressable>
              ) : null}
            </Card>
          ) : null}

          {showConfirmation ? (
            <Button
              label="Done"
              icon={<Check size={20} color={colors.onPrimary} />}
              onPress={() => router.back()}
            />
          ) : ticket.status === 'PENDING' ? (
            <View style={{ gap: spacing.md }}>
              <Button
                label={sendError ? 'Retry send' : 'Approve & Send'}
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
          ) : null}
          </ScrollView>
        </KeyboardAvoidingView>
      ) : (
        <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center' }}>
          <AppText variant="bodyMd" color={colors.outline}>
            {isLoading ? 'Loading…' : 'Ticket not found.'}
          </AppText>
        </View>
      )}
    </SafeAreaView>
  );
}
