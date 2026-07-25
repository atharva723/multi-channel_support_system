import { useRouter } from 'expo-router';
import { Hash, Info, Mail } from 'lucide-react-native';
import React, { useState } from 'react';
import { Alert, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppText } from '../../src/components/AppText';
import { ProviderCard } from '../../src/components/ProviderCard';
import { useAuthStore } from '../../src/hooks/useAuthStore';
import { colors, radius, spacing } from '../../src/theme';

export default function Connect() {
  const router = useRouter();
  const connect = useAuthStore((s) => s.connect);
  const [busy, setBusy] = useState<string | null>(null);

  const handle = async (provider: 'google' | 'discord') => {
    try {
      setBusy(provider);
      const ok = await connect(provider);
      if (ok) {
        router.replace('/(app)');
      } else {
        Alert.alert('Connection cancelled', 'You can try connecting again anytime.');
      }
    } catch (e: any) {
      Alert.alert('Connection failed', e?.message ?? 'Please try again.');
    } finally {
      setBusy(null);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.surface }}>
      <View style={{ flex: 1, paddingHorizontal: spacing.page, gap: spacing.xl }}>
        <View style={{ gap: spacing.md, paddingTop: spacing.lg }}>
          <AppText variant="headlineLg">Connect Channels</AppText>
          <View
            style={{
              flexDirection: 'row',
              gap: spacing.md,
              backgroundColor: colors.secondaryContainer,
              padding: spacing.base,
              borderRadius: radius.md,
              alignItems: 'center',
            }}
          >
            <Info size={20} color={colors.primary} />
            <AppText variant="bodyMd" color={colors.primary} style={{ flex: 1 }}>
              Connecting a channel is how you sign in (no passwords).
            </AppText>
          </View>
        </View>

        <View style={{ gap: spacing.lg }}>
          <Animated.View entering={FadeInDown.delay(60)}>
            <ProviderCard
              name="Discord"
              description="Manage server alerts & support"
              icon={<Hash size={26} color={colors.discord} strokeWidth={2.5} />}
              iconBg={colors.discordSoft}
              accent={colors.discord}
              loading={busy === 'discord'}
              onConnect={() => handle('discord')}
            />
          </Animated.View>

          <Animated.View entering={FadeInDown.delay(140)}>
            <ProviderCard
              name="Gmail"
              description="Auto-triage support tickets"
              icon={<Mail size={26} color={colors.gmail} strokeWidth={2.5} />}
              iconBg={colors.gmailSoft}
              accent={colors.primary}
              loading={busy === 'google'}
              onConnect={() => handle('google')}
            />
          </Animated.View>
        </View>
      </View>
    </SafeAreaView>
  );
}
