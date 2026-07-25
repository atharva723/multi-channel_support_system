import { Image } from 'expo-image';
import { useRouter } from 'expo-router';
import { Link2 } from 'lucide-react-native';
import React, { useEffect } from 'react';
import { Pressable, View } from 'react-native';
import Animated, {
  Easing,
  FadeIn,
  FadeInDown,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AppText } from '../../src/components/AppText';
import { colors, radius, shadow, spacing } from '../../src/theme';

const hero = require('../../assets/welcome-hero.png');

export default function Welcome() {
  const router = useRouter();

  // Gentle floating motion for the hero image.
  const float = useSharedValue(0);
  useEffect(() => {
    float.value = withRepeat(
      withTiming(1, { duration: 2600, easing: Easing.inOut(Easing.ease) }),
      -1,
      true,
    );
  }, [float]);

  const floatStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: -8 * float.value }],
  }));

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.surface }}>
      {/* Soft mist backdrop behind the hero */}
      <View
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          height: '60%',
          backgroundColor: '#e5ede9',
          opacity: 0.5,
        }}
      />

      <View
        style={{
          flex: 1,
          justifyContent: 'space-between',
          paddingHorizontal: spacing.xl,
          paddingBottom: spacing.xl,
        }}
      >
        {/* Floating hero image */}
        <Animated.View
          entering={FadeIn.duration(700)}
          style={[
            {
              flex: 1,
              alignItems: 'center',
              justifyContent: 'center',
              paddingTop: spacing.xxxl,
            },
            floatStyle,
          ]}
        >
          <Image
            source={hero}
            style={{ width: '86%', aspectRatio: 0.78 }}
            contentFit="contain"
          />
        </Animated.View>

        {/* Title + subtitle + CTA */}
        <Animated.View
          entering={FadeInDown.delay(150).duration(600)}
          style={{ gap: spacing.xl }}
        >
          <View style={{ gap: spacing.sm, alignItems: 'center' }}>
            <AppText variant="displayXl" color={colors.primary} center>
              AI Sentinel
            </AppText>
            <AppText
              variant="bodyLg"
              color={colors.onSurfaceVariant}
              center
              style={{ maxWidth: 300 }}
            >
              One inbox for Discord &amp; Gmail — triaged by AI.
            </AppText>
          </View>

          <View style={{ gap: spacing.md }}>
            <Pressable
              onPress={() => router.push('/(auth)/connect')}
              style={({ pressed }) => ({
                height: 60,
                borderRadius: radius.full,
                backgroundColor: colors.primary,
                alignItems: 'center',
                justifyContent: 'center',
                flexDirection: 'row',
                gap: 10,
                transform: [{ scale: pressed ? 0.98 : 1 }],
                ...shadow.fab,
              })}
            >
              <Link2 size={20} color={colors.onPrimary} strokeWidth={2.5} />
              <AppText variant="titleSm" color={colors.onPrimary}>
                Connect a channel
              </AppText>
            </Pressable>
            <AppText
              variant="labelSm"
              color={colors.outline}
              center
              style={{ textTransform: 'uppercase' }}
            >
              Securely encrypted · No credit card
            </AppText>
          </View>
        </Animated.View>
      </View>
    </SafeAreaView>
  );
}
