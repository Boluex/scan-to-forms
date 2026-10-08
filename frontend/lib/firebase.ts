import { getApp, getApps, initializeApp } from "firebase/app";
export const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  messagingSenderId: process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};
export const googleConfigured = Boolean(
  firebaseConfig.apiKey &&
    firebaseConfig.authDomain &&
    firebaseConfig.projectId &&
    firebaseConfig.appId,
);
export function firebaseApp() {
  if (!googleConfigured)
    throw new Error("Google sign-in is not configured yet.");
  return getApps().length ? getApp() : initializeApp(firebaseConfig);
}
export async function googleIdToken() {
  const {
    getAuth,
    GoogleAuthProvider,
    signInWithPopup,
    signOut,
    setPersistence,
    inMemoryPersistence,
  } = await import("firebase/auth");
  const auth = getAuth(firebaseApp());
  await setPersistence(auth, inMemoryPersistence);
  const provider = new GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  const result = await signInWithPopup(auth, provider);
  try {
    return await result.user.getIdToken();
  } finally {
    await signOut(auth);
  }
}
