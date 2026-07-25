import React from 'react';
import { View } from 'react-native';

import { radius, spacing } from '../theme';
import { channelMeta, type ChannelKey } from '../lib/channels';
import { AppText } from './AppText';

/** Low-saturation pill with the channel glyph + name in the brand color. */
export function ChannelPill({ channel }: { channel: ChannelKey }) {
  const { label, color, soft, Icon } = channelMeta(channel);
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: 6,
        backgroundColor: soft,
        paddingHorizontal: 10,
        paddingVertical: 5,
        borderRadius: radius.full,
        alignSelf: 'flex-start',
      }}
    >
      <Icon size={13} color={color} strokeWidth={2.5} />
      <AppText variant="labelSm" color={color} style={{ textTransform: 'uppercase' }}>
        {label}
      </AppText>
    </View>
  );
}
