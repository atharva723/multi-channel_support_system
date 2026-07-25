import { Stack } from 'expo-router';
import React from 'react';

import { colors } from '../../src/theme';

export default function TicketLayout() {
  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.surface },
        animation: 'slide_from_right',
      }}
    />
  );
}
