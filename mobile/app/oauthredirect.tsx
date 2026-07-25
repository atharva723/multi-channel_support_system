import { Redirect } from 'expo-router';
import * as WebBrowser from 'expo-web-browser';
import React, { useEffect } from 'react';

/**
 * Landing route for the OAuth deep link (`sentinel://oauthredirect`).
 *
 * The in-app auth browser normally consumes the redirect itself, but on Android
 * the OS may still deliver the deep link to the router afterward. Without this
 * route it renders as "Unmatched Route". Here we finalize any pending auth
 * session and bounce home so the leftover deep link resolves cleanly.
 */
export default function OAuthRedirect() {
  useEffect(() => {
    WebBrowser.maybeCompleteAuthSession();
  }, []);
  return <Redirect href="/(app)" />;
}
