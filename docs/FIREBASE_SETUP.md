# Firebase credentials and activation guide

The code supports Google sign-in and Firebase Cloud Messaging (FCM). Firebase credentials are not present yet; neither feature has been tested against a real Firebase project. No Gmail API access is needed. Keep PostgreSQL, Redis, and private R2 storage: Firebase does not replace them. Firestore, Firebase Storage, Analytics and Cloud Functions are not needed for this implementation.

## Values needed

Create/select one Firebase project for this environment and register a **Web app** under Project settings → General. Use a separate project for staging if practical.

| Value | Where to find it | Where to put it |
| --- | --- | --- |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | Web app SDK configuration → `apiKey` | Frontend build environment |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | `authDomain`, usually `PROJECT.firebaseapp.com` | Frontend build environment |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | `projectId` | Frontend build environment |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | `messagingSenderId` | Frontend build environment |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | `appId` | Frontend build environment |
| `NEXT_PUBLIC_FIREBASE_VAPID_KEY` | Project settings → Cloud Messaging → Web Push certificates → Generate key pair → public key | Frontend build environment |
| `FIREBASE_PROJECT_ID` | Same project ID | Django and push sender |
| `GOOGLE_APPLICATION_CREDENTIALS` **or** `FIREBASE_SERVICE_ACCOUNT_JSON` | Project settings → Service accounts → Firebase Admin SDK → Generate new private key | Django and push sender only |
| `FIREBASE_PUSH_ENABLED=true` | Feature switch, set after credentials work | Django and push sender |

The web configuration and VAPID public key are public identifiers. The service-account JSON contains a **private key**. Do not paste it into chat, commit it, put it under `frontend/`, or give it a `NEXT_PUBLIC_` name. Use a provider secret file or secret environment variable. For this computer, store the JSON outside the repository, chmod it to `600`, and set its absolute path in `.env.worker`. Prefer service-account credentials limited to Firebase Authentication verification and FCM sending rather than project-owner access. If using inline JSON in a dotenv file, keep it on one single-quoted line with the original escaped newlines.

## Console setup

1. Authentication → Sign-in method → enable **Google**, set the project support email, and save.
2. Authentication → Settings → Authorized domains → add the actual frontend hostnames. Add `localhost` explicitly for development if absent. Domain entries contain hostnames, not URL paths.
3. Confirm the Firebase Cloud Messaging HTTP v1 API is enabled for this project. Generate the Web Push certificate public key above.
4. Keep the generated `authDomain` unless deliberately configuring a custom authentication domain. The OAuth redirect handler associated with that domain must remain registered; enabling Google through Firebase sets up its provider configuration. No separate Google client secret is required by this application.
5. Public deployment must use HTTPS. Localhost is supported for local development. On iOS/iPadOS, test push from an installed Home Screen web app on a supported OS/browser.

References: [Google sign-in](https://firebase.google.com/docs/auth/web/google-signin), [Admin ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens), [FCM web setup](https://firebase.google.com/docs/cloud-messaging/web/get-started), [FCM receiving messages](https://firebase.google.com/docs/cloud-messaging/web/receive-messages), [Apple Home Screen push](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/).

## Put the values in the app

- Local Next.js: copy `frontend/.env.example` to ignored `frontend/.env.local`; fill the six public values and correct API URL. The root `.env` is not automatically read by a native Next.js process in `frontend/`.
- Render frontend: add the six `NEXT_PUBLIC_FIREBASE_*` variables and **rebuild**; Next.js embeds public variables at build time.
- Django/API: add `FIREBASE_PROJECT_ID`, a service-account secret, and the push switch. Deploy the updated backend and apply migrations before testing.
- Ubuntu: put the server variables in the existing ignored `.env.worker`. Install/update requirements, run migrations once for the shared database, and restart processes after changing credentials.

```bash
.venv/bin/pip install -r backend/requirements/base.txt
SCANTO_FORMS_ENV_FILE="$PWD/.env.worker" .venv/bin/python backend/manage.py migrate
python3 scripts/install-worker.py
systemctl --user start scanforms-push
```

Set `FIREBASE_PUSH_ENABLED=true` on every process that creates notifications, including OCR workers, and restart those processes. OCR-only hosts need this switch to populate the outbox but do not need the Firebase private key.

Push delivery is a separate lightweight process and does not wait behind OCR. Keep it running for timely alerts. A sleeping/offline computer delays delivery. The outbox survives process downtime; failed sends back off up to eight attempts. The admin dashboard shows pending/stopped counts. There is no automatic retry after the eighth failure; investigate the error class and repair/requeue selected rows through a controlled maintenance session. A crash after Firebase accepts a send can result in a duplicate; the browser notification tag helps collapse duplicates. Firebase acceptance is not proof of receipt or reading.

## Account behaviour and no-email operation

New Google users are created with verified email and no local password. No app email is sent for Google registration or sign-in. Only a verified Firebase ID token with the Google provider is accepted. Django issues its existing API session tokens; Google sign-in does not grant access to Google Forms or Drive.

Existing email/password users must log in and use **Account settings → Link Google account** with the same email. Matching emails are not silently linked. This protects existing accounts. Suspended users cannot sign in via Google or continue using existing API tokens.

Order notifications and admin announcements use the inbox plus optional push; they do not use Gmail or Resend. Existing password registration/verification and password reset still use the existing mail provider. Do not remove that provider until all users have a tested Google recovery path or a separately implemented no-password registration policy. Push cannot recover an account on a new device where the user is not signed in and has never subscribed.

## Acceptance checklist

1. Rebuild frontend, deploy backend, and start the sender with the same project credentials.
2. Sign up via Google. Confirm `/auth/me/` is the expected user and no administrator role is granted. Sign out and sign back in.
3. Link an existing password account; confirm another Google email cannot link it. Suspend the test user and check sign-in/API access are blocked.
4. In Notifications, click **Enable notifications** and accept the browser prompt. Permission is requested only after the click. Test denial and an unsupported browser too.
5. Use a disposable admin announcement and confirm both the inbox and a background push. Click push and confirm it opens `/notifications`.
6. Complete a disposable order through payment verification/review/ready; confirm the existing ORDER_READY event reaches the inbox and device. Never send an announcement to real users merely to test production.
7. Disable notifications, log out, and switch to a different test user on the same browser. Check old pending notifications are not delivered to the new owner.
8. Test Android Chrome and iOS Home Screen separately on HTTPS. Desktop success does not establish mobile success.
9. Stop the sender, generate an update, restart it, and verify outbox recovery without losing the inbox entry.

## PWA cache policy

One root `/sw.js` handles both push and offline support. The manifest includes installable PNG icons. The cache stores an explicit offline page, icons, and up to 100 Next.js static assets. Navigations always try the network and fall back to the offline page. Authenticated HTML, API responses, RSC payloads, source documents, results, credentials and mutations are never added to Cache Storage. This is offline shell support, not offline editing or background uploads. Unsaved form changes are not queued. New service-worker versions activate after existing tabs close; increment the cache version when changing the offline shell. Use browser DevTools to inspect unregister/cache behaviour during development.
