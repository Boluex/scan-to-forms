import { api } from "./api";
import { firebaseApp } from "./firebase";
const storageKey = "scanforms_push_token";
export async function enablePush(requestPermission = true) {
  if (
    !("serviceWorker" in navigator) ||
    !("Notification" in window) ||
    !window.isSecureContext
  )
    throw new Error(
      "This browser needs HTTPS and web push support. On iPhone, add this app to your Home Screen first.",
    );
  const vapidKey = process.env.NEXT_PUBLIC_FIREBASE_VAPID_KEY;
  if (!vapidKey) throw new Error("Push notifications are not configured yet.");
  const permission = requestPermission
    ? await Notification.requestPermission()
    : Notification.permission;
  if (permission !== "granted")
    throw new Error(
      "Notifications are blocked. Enable them in your browser settings; your inbox is always available.",
    );
  const { getMessaging, getToken, isSupported } = await import(
    "firebase/messaging"
  );
  if (!(await isSupported()))
    throw new Error(
      "Web push is not supported here. On iPhone, use the installed Home Screen app.",
    );
  await navigator.serviceWorker.register("/sw.js");
  const registration = await navigator.serviceWorker.ready;
  const token = await getToken(getMessaging(firebaseApp()), {
    vapidKey,
    serviceWorkerRegistration: registration,
  });
  await api("/notifications/devices/", {
    method: "POST",
    body: JSON.stringify({ token, label: navigator.userAgent.slice(0, 120) }),
  });
  localStorage.setItem(storageKey, token);
}
export function pushEnabled() {
  return Boolean(localStorage.getItem(storageKey));
}
export async function disablePush() {
  const token = localStorage.getItem(storageKey);
  if (token)
    await api("/notifications/devices/", {
      method: "DELETE",
      body: JSON.stringify({ token }),
    });
  // Unsubscribe at the browser as well, including when the backend is unavailable.
  await removeBrowserPush();
}
export async function removeBrowserPush() {
  if ("serviceWorker" in navigator) {
    const registration = await navigator.serviceWorker.getRegistration("/");
    const subscription = await registration?.pushManager.getSubscription();
    await subscription?.unsubscribe();
  }
  localStorage.removeItem(storageKey);
}
