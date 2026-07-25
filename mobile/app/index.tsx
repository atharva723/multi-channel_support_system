import { Redirect } from 'expo-router';
import React from 'react';

/** Entry: the AuthGate in _layout redirects based on session; default to app. */
export default function Index() {
  return <Redirect href="/(app)" />;
}
