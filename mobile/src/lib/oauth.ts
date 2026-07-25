import * as AuthSession from 'expo-auth-session';
import * as WebBrowser from 'expo-web-browser';
import {
  GoogleSignin,
  statusCodes,
} from '@react-native-google-signin/google-signin';

import { AuthApi, type SessionOut } from '../api/client';
import { config } from '../lib/config';

// REQUIRED by expo-auth-session: lets the auth redirect complete/dismiss the
// in-app browser instead of falling through to the router ("unmatched route").
WebBrowser.maybeCompleteAuthSession();

/**
 * Option B — app-owned OAuth.
 *
 * The app performs the OAuth handshake itself against a FIXED redirect identity
 * (the app's `sentinel://` scheme for Discord; the native Google SDK for Gmail),
 * then hands the resulting code to the backend to exchange for tokens. The
 * redirect never depends on the backend's address, so it needs registering only
 * once and the tunnel is unnecessary.
 *
 * NOTE: requires a development build (custom scheme + native Google module do
 * not work in Expo Go).
 */

// --- Discord: Authorization Code + PKCE ------------------------------------
const DISCORD_DISCOVERY: AuthSession.DiscoveryDocument = {
  authorizationEndpoint: 'https://discord.com/oauth2/authorize',
  tokenEndpoint: 'https://discord.com/api/oauth2/token',
};

export function discordRedirectUri(): string {
  // sentinel://oauthredirect in a dev/standalone build.
  return AuthSession.makeRedirectUri({ scheme: config.authScheme, path: 'oauthredirect' });
}

export async function connectDiscord(
  sessionToken?: string | null,
): Promise<SessionOut | null> {
  const redirectUri = discordRedirectUri();
  const request = new AuthSession.AuthRequest({
    clientId: config.discordClientId,
    scopes: ['identify', 'email', 'guilds'],
    redirectUri,
    responseType: AuthSession.ResponseType.Code,
    usePKCE: true,
  });

  await request.makeAuthUrlAsync(DISCORD_DISCOVERY);
  const result = await request.promptAsync(DISCORD_DISCOVERY);

  if (result.type !== 'success' || !result.params.code) return null;
  const code = result.params.code;
  const verifier = request.codeVerifier;
  if (!verifier) throw new Error('Missing PKCE verifier.');

  // The app holds only the one-time code; the backend does the secure exchange.
  return AuthApi.exchangeDiscordPkce(code, verifier, redirectUri, sessionToken);
}

// --- Google: native Sign-In (serverAuthCode) -------------------------------
let googleConfigured = false;

function ensureGoogleConfigured() {
  if (googleConfigured) return;
  GoogleSignin.configure({
    webClientId: config.googleWebClientId,
    offlineAccess: true, // -> returns a serverAuthCode + refresh token
    // Force a fresh serverAuthCode each sign-in so Google issues a refresh token
    // even when the user has already consented before.
    forceCodeForRefreshToken: true,
    scopes: [
      'https://www.googleapis.com/auth/gmail.send',
      'https://www.googleapis.com/auth/gmail.readonly',
    ],
  });
  googleConfigured = true;
}

export async function connectGoogle(
  sessionToken?: string | null,
): Promise<SessionOut | null> {
  ensureGoogleConfigured();
  await GoogleSignin.hasPlayServices({ showPlayServicesUpdateDialog: true });

  // Clear any cached silent session so signIn() always yields a FRESH
  // serverAuthCode (needed for Google to return a refresh token).
  try {
    await GoogleSignin.signOut();
  } catch {
    // ignore — nothing cached
  }

  try {
    const result: any = await GoogleSignin.signIn();
    // Support both new ({type,data}) and legacy shapes.
    const serverAuthCode =
      result?.data?.serverAuthCode ?? result?.serverAuthCode ?? null;
    if (!serverAuthCode) {
      throw new Error('Google did not return a serverAuthCode (check offlineAccess).');
    }
    return AuthApi.exchangeGoogleServerCode(serverAuthCode, sessionToken);
  } catch (e: any) {
    if (e?.code === statusCodes.SIGN_IN_CANCELLED) return null;
    throw e;
  }
}
