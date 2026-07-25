import { useRouter } from 'expo-router';
import { Bell, BookOpen, ChevronRight, Hash, LogOut, Mail, ShieldAlert, Smartphone, User } from 'lucide-react-native';
import React from 'react';
import { Alert, Pressable, ScrollView, Switch, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppHeader } from '../../src/components/AppHeader';
import { AppText } from '../../src/components/AppText';
import { Button } from '../../src/components/Button';
import { Card } from '../../src/components/Card';
import { useAuthStore } from '../../src/hooks/useAuthStore';
import { useConnections } from '../../src/hooks/useConnections';
import { usePrefsStore } from '../../src/hooks/usePrefsStore';
import { shortDate } from '../../src/lib/time';
import { colors, radius, spacing } from '../../src/theme';

const CRITICALITY_THRESHOLD = 0.8; // System default; mirrors backend config.

function SectionLabel({ children }: { children: string }) {
  return (
    <AppText variant="labelMd" color={colors.outline} style={{ textTransform: 'uppercase', marginTop: spacing.md }}>
      {children}
    </AppText>
  );
}

function Row({
  icon,
  label,
  sublabel,
  right,
}: {
  icon: React.ReactNode;
  label: string;
  sublabel?: string;
  right?: React.ReactNode;
}) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.base, paddingVertical: spacing.md }}>
      <View style={{ width: 40, height: 40, borderRadius: 20, backgroundColor: colors.secondaryContainer, alignItems: 'center', justifyContent: 'center' }}>
        {icon}
      </View>
      <View style={{ flex: 1 }}>
        <AppText variant="titleSm">{label}</AppText>
        {sublabel ? (
          <AppText variant="labelSm" color={colors.outline}>
            {sublabel}
          </AppText>
        ) : null}
      </View>
      {right}
    </View>
  );
}

export default function Settings() {
  const router = useRouter();
  const account = useAuthStore((s) => s.account);
  const signOut = useAuthStore((s) => s.signOut);
  const { data: connections } = useConnections();
  const hapticsEnabled = usePrefsStore((s) => s.hapticsEnabled);
  const setHaptics = usePrefsStore((s) => s.setHaptics);

  const channelCount = connections?.length ?? 0;
  const providerSummary =
    channelCount === 0
      ? 'None connected'
      : (connections ?? [])
          .map((c) => (c.provider === 'discord' ? 'Discord' : 'Gmail'))
          .filter((v, i, a) => a.indexOf(v) === i)
          .join(' · ');

  const confirmSignOut = () => {
    Alert.alert('Sign out', 'You will need to reconnect a channel to sign back in.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Sign Out', style: 'destructive', onPress: () => signOut() },
    ]);
  };

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: colors.surface }}>
      <AppHeader />
      <ScrollView contentContainerStyle={{ padding: spacing.page, gap: spacing.base, paddingBottom: spacing.xxxl }}>
        <Card style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.base }}>
          <View style={{ width: 60, height: 60, borderRadius: 30, backgroundColor: colors.primaryFixed, alignItems: 'center', justifyContent: 'center' }}>
            <User size={30} color={colors.primary} />
          </View>
          <View style={{ flex: 1 }}>
            <AppText variant="titleMd">{account?.display_name ?? 'Support Agent'}</AppText>
            <AppText variant="bodyMd" color={colors.onSurfaceVariant} numberOfLines={1}>
              {account?.email ?? 'No email on file'}
            </AppText>
            {account?.created_at ? (
              <AppText variant="labelSm" color={colors.outline} style={{ marginTop: 2 }}>
                Member since {shortDate(account.created_at)}
              </AppText>
            ) : null}
          </View>
        </Card>

        <SectionLabel>Account</SectionLabel>
        <Card style={{ paddingVertical: spacing.xs }}>
          <Pressable onPress={() => router.push('/(app)/channels')}>
            <Row
              icon={channelCount && (connections ?? [])[0]?.provider === 'discord'
                ? <Hash size={20} color={colors.primary} />
                : <Mail size={20} color={colors.primary} />}
              label="Connected Channels"
              sublabel={providerSummary}
              right={
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
                  <View style={{ minWidth: 22, height: 22, borderRadius: 11, backgroundColor: colors.secondaryContainer, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 6 }}>
                    <AppText variant="labelSm" color={colors.primary}>
                      {channelCount}
                    </AppText>
                  </View>
                  <ChevronRight size={20} color={colors.outline} />
                </View>
              }
            />
          </Pressable>
          <View style={{ height: 1, backgroundColor: colors.cardHighest }} />
          <Pressable onPress={() => router.push('/kb')}>
            <Row
              icon={<BookOpen size={20} color={colors.primary} />}
              label="Knowledge Base"
              sublabel="Documents the AI answers from"
              right={<ChevronRight size={20} color={colors.outline} />}
            />
          </Pressable>
        </Card>

        <SectionLabel>Triage</SectionLabel>
        <Card style={{ gap: spacing.md }}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <View style={{ flex: 1, flexDirection: 'row', gap: spacing.md, alignItems: 'center' }}>
              <ShieldAlert size={20} color={colors.escalation} />
              <View style={{ flex: 1 }}>
                <AppText variant="titleSm">Criticality Threshold</AppText>
                <AppText variant="labelSm" color={colors.outline}>
                  Tickets above this escalate to you
                </AppText>
              </View>
            </View>
            <AppText variant="headlineMd" color={colors.primary}>
              {CRITICALITY_THRESHOLD.toFixed(2)}
            </AppText>
          </View>
          <View style={{ height: 6, backgroundColor: colors.cardHighest, borderRadius: 3 }}>
            <View style={{ width: `${CRITICALITY_THRESHOLD * 100}%`, height: 6, backgroundColor: colors.primary, borderRadius: 3 }} />
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
            <AppText variant="labelSm" color={colors.outline}>Lax</AppText>
            <AppText variant="labelSm" color={colors.outline}>Extreme</AppText>
          </View>
        </Card>

        <SectionLabel>Preferences</SectionLabel>
        <Card style={{ paddingVertical: spacing.xs }}>
          <Row
            icon={<Smartphone size={20} color={colors.primary} />}
            label="Haptic Feedback"
            sublabel="Vibrate on actions & alerts"
            right={
              <Switch
                value={hapticsEnabled}
                onValueChange={setHaptics}
                trackColor={{ true: colors.primary }}
                thumbColor={colors.white}
              />
            }
          />
          <View style={{ height: 1, backgroundColor: colors.cardHighest }} />
          <Row
            icon={<Bell size={20} color={colors.primary} />}
            label="Push Notifications"
            sublabel="Alerts for critical escalations"
            right={
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: colors.secondaryContainer, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.full }}>
                <View style={{ width: 7, height: 7, borderRadius: 4, backgroundColor: colors.success }} />
                <AppText variant="labelSm" color={colors.primary}>
                  On
                </AppText>
              </View>
            }
          />
        </Card>

        <View style={{ marginTop: spacing.lg }}>
          <Button
            label="Sign Out"
            variant="danger"
            icon={<LogOut size={18} color={colors.error} />}
            onPress={confirmSignOut}
          />
        </View>
        <AppText variant="labelSm" color={colors.outline} center style={{ marginTop: spacing.sm }}>
          Sentinel v1.0.0 · Stable Build
        </AppText>
      </ScrollView>
    </SafeAreaView>
  );
}
