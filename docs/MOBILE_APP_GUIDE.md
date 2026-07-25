# Mobile App Guide

> How the Expo (React Native, TypeScript) client is built and why. Cross-refs:
> [GOOGLE_OAUTH_AND_GMAIL_API.md](./GOOGLE_OAUTH_AND_GMAIL_API.md),
> [DISCORD_INTEGRATION.md](./DISCORD_INTEGRATION.md),
> [PUSH_NOTIFICATIONS_FCM.md](./PUSH_NOTIFICATIONS_FCM.md).

## Stack

Expo **SDK 57** · expo-router (file-based navigation) · **Zustand** (client
state) · **TanStack Query** (server state) · `react-native-sse` (realtime) ·
`@react-native-google-signin/google-signin` + `expo-auth-session` (OAuth) ·
`expo-notifications` (push) · `expo-document-picker` (KB upload) ·
`@shopify/flash-list`, `@gorhom/bottom-sheet`, `expo-haptics`,
`lucide-react-native`.

> **AGENTS rule:** this SDK is pinned — read the versioned docs at
> `https://docs.expo.dev/versions/v57.0.0/` before writing Expo code
> (`mobile/AGENTS.md`).

## Why a custom dev build — not Expo Go

The app **cannot run in Expo Go**. It depends on native modules Expo Go doesn't
bundle and on a custom URL scheme:

1. **Native Google Sign-In** (`@react-native-google-signin`) — a native module.
2. **Custom scheme `sentinel://`** for the Discord OAuth redirect — Expo Go owns
   its own scheme; only a standalone build can own `sentinel://oauthredirect`.
3. **Push notifications** (`expo-notifications`) — remote push needs a dev/standalone
   build (Expo Go dropped it on Android).
4. **Document picker** (`expo-document-picker`) — native file access for KB upload.

So the app is built with **EAS** (`eas build --profile development --platform
android`) and installed as an APK. The **JavaScript still hot-reloads** from Metro
— you only rebuild when native modules or `app.json` change.

```powershell
cd mobile
npm install
npx eas build --profile development --platform android   # produces an installable APK
```

## State management: Zustand vs TanStack Query (the split)

A deliberate division of labor:

| Concern | Tool | Examples |
| --- | --- | --- |
| **Server data** (fetch, cache, refetch, mutate) | **TanStack Query** | tickets, connections, knowledge-base docs |
| **Client/app state** (synchronous, device-local) | **Zustand** | auth session, user prefs, toast, realtime signals |

Zustand stores (`src/hooks/`):
- `useAuthStore` — session token (SecureStore), current account, OAuth `connect`,
  sign-out.
- `usePrefsStore` — persisted preferences (e.g. haptics on/off).
- `useToastStore` — the global success toast.
- `useRealtimeStore` — a tiny signal store the app-wide SSE bumps so screens (the
  Desk banner) can react without a second connection.

TanStack Query hooks: `useTickets`, `useConnections`, `useKnowledgeBase` — each
owns its cache key, refetch-on-focus, and mutations that invalidate on success.

## Navigation (expo-router)

File-based routes under `app/`:
- `app/(auth)/` — `welcome`, `connect` (OAuth sign-in).
- `app/(app)/` — the tab bar: `index` (Escalation Desk), `inbox`, `channels`,
  `settings`.
- `app/ticket/[id].tsx` — ticket detail (approve/edit/send).
- `app/kb.tsx` — Knowledge Base (upload / add website / replace / refresh).
- `app/_layout.tsx` — root: providers, auth gate, push wiring, global toast.

## OAuth on the client ("Option B")

The app performs OAuth itself and posts the code to the backend to exchange —
no backend callback URL / tunnel. Implemented in `src/lib/oauth.ts`:
- **Discord** — `expo-auth-session` PKCE → `sentinel://oauthredirect`.
- **Google** — native `GoogleSignin` → `serverAuthCode`.

Two details that are easy to miss (both required):
- `WebBrowser.maybeCompleteAuthSession()` must run at module load, or the redirect
  falls through to the router and you get an "Unmatched Route" flash. There's a
  dedicated `app/oauthredirect.tsx` route for this.
- Connecting a **second** channel while signed in passes the existing Bearer token
  to `/exchange` so it **links** to the same account instead of creating a new one.

See the Google & Discord docs for the provider-side setup.

## Realtime: the SSE client

`src/hooks/useEscalationStream.ts` opens one **app-wide** `react-native-sse`
connection (mounted once in the tab layout). On `escalation` / `ticket_update`
events it patches the TanStack Query cache directly (instant) and bumps the
realtime store. The token is passed as a `?token=` query param because
`EventSource` can't set headers.

> Mounting it **once app-wide** (not per-screen) is why a status change made on
> one tab shows up immediately on another.

## Push notifications

Registered app-wide (`usePushNotifications`): after sign-in the device's Expo push
token is sent to the backend; tapping a notification deep-links to the ticket.
Full detail in [PUSH_NOTIFICATIONS_FCM.md](./PUSH_NOTIFICATIONS_FCM.md).

## The Knowledge Base screen

`app/kb.tsx` — upload documents (`expo-document-picker`), add a website, **Replace**
an uploaded doc in place, or **Refresh** a website source. A green **ProgressBar**
(`src/components/ProgressBar.tsx`, pure `Animated`, no native module) shows real
embedding progress (chunks done / total) reported by the backend. Full behavior in
[KNOWLEDGE_BASE_RAG.md](./KNOWLEDGE_BASE_RAG.md).

## Theme

Design tokens live in `src/theme/` (colors, spacing, radius, typography). The
palette is green-forward; components read tokens rather than hard-coding colors.

## Env vars (`mobile/.env`)
```
EXPO_PUBLIC_API_URL=http://<LAN-IP>:8000     # auto-synced by demo-start-lan.ps1
EXPO_PUBLIC_API_KEY=<matches backend SENTINEL_API_KEY>
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=<Google WEB client id>
EXPO_PUBLIC_DISCORD_CLIENT_ID=<Discord application client id>
```
`EXPO_PUBLIC_` is the Expo convention for values inlined into the client bundle —
so **only non-secret** values go here (the API key here is a low-value shared
gate, not a real secret).
