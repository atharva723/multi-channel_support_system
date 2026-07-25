import { Hash, Mail } from 'lucide-react-native';
import React from 'react';

import { colors } from '../theme';

export type ChannelKey = 'discord' | 'email' | string;

interface ChannelMeta {
  label: string;
  color: string;
  soft: string;
  Icon: typeof Hash;
}

const MAP: Record<string, ChannelMeta> = {
  discord: { label: 'Discord', color: colors.discord, soft: colors.discordSoft, Icon: Hash },
  email: { label: 'Gmail', color: colors.gmail, soft: colors.gmailSoft, Icon: Mail },
  gmail: { label: 'Gmail', color: colors.gmail, soft: colors.gmailSoft, Icon: Mail },
};

export function channelMeta(channel: ChannelKey): ChannelMeta {
  return (
    MAP[channel?.toLowerCase()] ?? {
      label: channel ?? 'Channel',
      color: colors.outline,
      soft: colors.cardMuted,
      Icon: Hash,
    }
  );
}

/** Map a provider name to the same visual identity as its channel. */
export function providerMeta(provider: string): ChannelMeta {
  if (provider === 'google') return channelMeta('email');
  return channelMeta(provider);
}
