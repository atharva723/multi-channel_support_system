import { Tabs } from 'expo-router';
import { LayoutGrid, Inbox, Share2, Settings } from 'lucide-react-native';
import React from 'react';

import { useEscalationStream } from '../../src/hooks/useEscalationStream';
import { colors, fonts } from '../../src/theme';

export default function AppTabsLayout() {
  // One app-wide SSE connection so realtime updates land on every tab.
  useEscalationStream();

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.primary,
        tabBarInactiveTintColor: colors.outline,
        tabBarStyle: {
          backgroundColor: colors.cardMuted,
          borderTopWidth: 0,
          height: 88,
          paddingTop: 10,
          paddingBottom: 28,
          paddingHorizontal: 8,
        },
        tabBarLabelStyle: {
          fontFamily: fonts.hankenSemibold,
          fontSize: 11,
        },
        tabBarItemStyle: { borderRadius: 16 },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: 'Desk',
          tabBarIcon: ({ color, focused }) => (
            <LayoutGrid size={24} color={color} fill={focused ? color : 'transparent'} />
          ),
        }}
      />
      <Tabs.Screen
        name="inbox"
        options={{
          title: 'Inbox',
          tabBarIcon: ({ color }) => <Inbox size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="channels"
        options={{
          title: 'Channels',
          tabBarIcon: ({ color }) => <Share2 size={24} color={color} />,
        }}
      />
      <Tabs.Screen
        name="settings"
        options={{
          title: 'Settings',
          tabBarIcon: ({ color }) => <Settings size={24} color={color} />,
        }}
      />
    </Tabs>
  );
}
