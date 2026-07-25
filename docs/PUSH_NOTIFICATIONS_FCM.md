# Push Notifications (Firebase / FCM + Expo)

> How Sentinel alerts an agent's phone the instant a **critical** ticket arrives —
> even when the app is closed — and opens straight to that ticket on tap. Explains
> the Expo → FCM chain and the Firebase setup that isn't obvious the first time.

## Why push (vs. the SSE stream)

The app already gets realtime updates over **SSE** — but only **while it's open**.
When the app is closed or the phone is locked, nothing is running to receive
events. Push notifications solve exactly that: the OS shows a banner + buzz even
with the app closed. So SSE = live updates in-app; push = "wake me when it's
critical."

## The delivery chain — and why each piece exists

```
 Backend (critical ticket)
   → Expo Push Service (https://exp.host/.../push/send)
     → Google FCM (Firebase Cloud Messaging)
       → Android OS
         → the Sentinel app's notification
```

- **An app cannot wake itself.** When it's closed it isn't running, so *something
  external* must poke the phone. On Android that "something" is **Google FCM** —
  the only sanctioned way to deliver to Android when an app is backgrounded. Every
  app that notifies you uses it.
- **Expo Push Service** is a free relay that gives us a simple HTTP API and hands
  off to FCM (and APNs on iOS) so we don't integrate FCM's native SDK directly.
- **Firebase** is the Google project that *authorizes* our app to use FCM.

## Firebase / FCM setup (one-time, done in the Google/Firebase console)

Two artifacts are required — one baked into the app **build**, one uploaded to
**EAS**:

1. **Firebase project + Android app** for package `com.sentinel.app`.
2. **`google-services.json`** — downloaded from Firebase, placed at
   `mobile/google-services.json`, and referenced by
   `expo.android.googleServicesFile` in `app.json`. It contains only **public
   identifiers**, so it's committed. **Adding it requires a rebuild** (it's baked
   into the binary).
3. **A Google service-account key** — uploaded to EAS
   (Project → Credentials → Android → **FCM V1 service account key**). This is the
   *secret* that lets Expo's servers ask FCM to deliver on your behalf. The local
   copy lives at `mobile/credentials/fcm-service-account.json` and is **gitignored**.

> **Why two files?** `google-services.json` identifies the *app* to FCM (public,
> in the build). The service-account key authorizes the *sender* (Expo) to FCM
> (secret, on EAS). Both must exist or delivery silently fails.

Uploading the service-account key does **not** require a rebuild; adding
`google-services.json` does.

## Mobile side

`mobile/src/lib/notifications.ts` + `src/hooks/usePushNotifications.ts`:

1. **Handler + Android channel** — `setNotificationHandler` (so foreground
   notifications show) and an Android `escalations` channel with MAX importance
   (required for heads-up alerts).
2. **Permission + token** — request permission, then fetch this device's **Expo
   push token** with `getExpoPushTokenAsync({ projectId })`.
3. **Register** — after sign-in, POST the token to the backend
   (`/notifications/register`); unregister on sign-out.
4. **Tap-through** — `getLastNotificationResponse()` (cold start) +
   `addNotificationResponseReceivedListener` (warm) read `data.url` and
   `router.push()` to `/ticket/{id}` — so tapping the notification opens that
   ticket.

`app.json` includes the `expo-notifications` plugin (color + default channel).
Push needs a **dev/standalone build**, not Expo Go.

## Backend side

- **Model:** `push_tokens` — one row per device (multiple per account allowed),
  unique on the token so a re-registering device updates its owner.
- **Endpoints:** `POST /notifications/register` and `/unregister` (tenant-scoped).
- **Service:** `app/services/push.py` → `send_to_account` posts to the Expo Push
  API for every device of an account, with `channelId: escalations`,
  `priority: high`, and a `data.url` deep link. It **prunes dead tokens** Expo
  reports as `DeviceNotRegistered`.
- **Trigger:** in `endpoints/triage.py`, a **critical** ticket publishes the SSE
  `escalation` event **and** calls `send_to_account` (best-effort — a push failure
  never breaks triage). The notification title/body is the sender + a message
  preview; `data.url = /ticket/{id}`.

## Testing it

1. Ensure the dev build (with `google-services.json`) is installed and you granted
   the notification permission on first launch.
2. Background the app / lock the phone.
3. Send a **critical** message (e.g. "URGENT: production is down, customers can't
   pay").
4. Expect a banner + buzz within a few seconds → tap → opens that ticket.

If nothing arrives, see [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) (permission not
granted, FCM key missing, or a stale token).
