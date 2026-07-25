import Constants from 'expo-constants';
import { Platform } from 'react-native';

/**
 * Backend base URL.
 *
 * On a physical device you cannot reach the host's "localhost"; set
 * EXPO_PUBLIC_API_URL to your machine's LAN IP (e.g. http://192.168.1.5:8000).
 * Android emulator maps the host to 10.0.2.2. Web/iOS-sim use localhost.
 */
function resolveBaseUrl(): string {
  const fromEnv = process.env.EXPO_PUBLIC_API_URL;
  if (fromEnv) return fromEnv.replace(/\/$/, '');

  // Try to infer the dev host (Metro) IP so real devices work automatically.
  const hostUri =
    Constants.expoConfig?.hostUri ??
    (Constants as unknown as { manifest?: { debuggerHost?: string } }).manifest
      ?.debuggerHost;
  const host = hostUri?.split(':')[0];

  if (Platform.OS === 'android' && (!host || host === 'localhost')) {
    return 'http://10.0.2.2:8000';
  }
  if (host && host !== 'localhost') {
    return `http://${host}:8000`;
  }
  return 'http://localhost:8000';
}

export const config = {
  apiBaseUrl: resolveBaseUrl(),
  apiPrefix: '/api/v1',
  /** Deep link the OAuth callback redirects back to. */
  authScheme: 'sentinel',
  googleWebClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? '',
  discordClientId: process.env.EXPO_PUBLIC_DISCORD_CLIENT_ID ?? '',
  apiKey: process.env.EXPO_PUBLIC_API_KEY ?? '',
} as const;

export const apiUrl = (path: string) =>
  `${config.apiBaseUrl}${config.apiPrefix}${path}`;
