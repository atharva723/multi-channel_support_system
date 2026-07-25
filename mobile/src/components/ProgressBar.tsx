import React, { useEffect, useRef, useState } from 'react';
import { Animated, Easing, View, type StyleProp, type ViewStyle } from 'react-native';

import { colors, radius } from '../theme';
import { AppText } from './AppText';

interface Props {
  /** Determinate progress 0–100. Ignored when `indeterminate` is true. */
  value?: number;
  /** Show a looping sweep instead of a filled percentage (unknown progress). */
  indeterminate?: boolean;
  /** Optional phase label shown above the bar. */
  label?: string;
  /** Bar height in px. Default 10. */
  height?: number;
  style?: StyleProp<ViewStyle>;
}

/**
 * Green "flux" progress bar — a vivid emerald fill with a gliding white sheen,
 * plus an optional phase label. Adapted for React Native (Animated, no native
 * modules) from a web progress concept, recolored to the app's green vibe.
 *
 * `value` drives a real percentage; `indeterminate` runs a looping sweep for
 * phases where progress isn't yet known (parsing / crawling).
 */
export function ProgressBar({ value = 0, indeterminate = false, label, height = 10, style }: Props) {
  const pct = Math.max(0, Math.min(100, value));
  const widthAnim = useRef(new Animated.Value(0)).current;
  const sheenAnim = useRef(new Animated.Value(0)).current;
  const indetAnim = useRef(new Animated.Value(0)).current;
  const [trackWidth, setTrackWidth] = useState(0);

  // Animate the determinate fill toward the current percentage.
  useEffect(() => {
    if (indeterminate) return;
    Animated.timing(widthAnim, {
      toValue: pct / 100,
      duration: 550,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [pct, indeterminate, widthAnim]);

  // Looping white sheen glide over the filled portion.
  useEffect(() => {
    if (trackWidth === 0) return;
    const loop = Animated.loop(
      Animated.timing(sheenAnim, {
        toValue: 1,
        duration: 1400,
        easing: Easing.linear,
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [trackWidth, sheenAnim]);

  // Indeterminate segment sweeping left → right.
  useEffect(() => {
    if (!indeterminate || trackWidth === 0) return;
    indetAnim.setValue(0);
    const loop = Animated.loop(
      Animated.timing(indetAnim, {
        toValue: 1,
        duration: 1200,
        easing: Easing.inOut(Easing.ease),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [indeterminate, trackWidth, indetAnim]);

  const fillWidth = widthAnim.interpolate({
    inputRange: [0, 1],
    outputRange: ['0%', '100%'],
  });

  const segWidth = Math.max(48, trackWidth * 0.4);
  const sheenTranslate = sheenAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [-segWidth, trackWidth],
  });
  const indetTranslate = indetAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [-segWidth, trackWidth],
  });

  return (
    <View style={[{ gap: 8 }, style]}>
      {label ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
          <AppText variant="labelSm" color={colors.primary}>
            {label}
          </AppText>
          {!indeterminate ? (
            <AppText variant="labelSm" color={colors.outline}>
              {Math.round(pct)}%
            </AppText>
          ) : null}
        </View>
      ) : null}

      <View
        onLayout={(e) => setTrackWidth(e.nativeEvent.layout.width)}
        style={{
          height,
          width: '100%',
          borderRadius: radius.full,
          backgroundColor: colors.cardHighest,
          overflow: 'hidden',
        }}
      >
        {indeterminate ? (
          trackWidth > 0 ? (
            <Animated.View
              style={{
                position: 'absolute',
                top: 0,
                bottom: 0,
                width: segWidth,
                borderRadius: radius.full,
                backgroundColor: colors.success,
                transform: [{ translateX: indetTranslate }],
              }}
            />
          ) : null
        ) : (
          <Animated.View
            style={{
              height: '100%',
              width: fillWidth,
              borderRadius: radius.full,
              backgroundColor: colors.success,
              overflow: 'hidden',
            }}
          >
            {trackWidth > 0 ? (
              <Animated.View
                style={{
                  position: 'absolute',
                  top: 0,
                  bottom: 0,
                  width: segWidth,
                  backgroundColor: 'rgba(255,255,255,0.45)',
                  transform: [{ translateX: sheenTranslate }],
                }}
              />
            ) : null}
          </Animated.View>
        )}
      </View>
    </View>
  );
}
