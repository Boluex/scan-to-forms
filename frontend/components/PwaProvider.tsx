"use client";
import { useEffect, useState } from "react";
type InstallEvent = Event & {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: string }>;
};
export default function PwaProvider() {
  const [offline, setOffline] = useState(false),
    [install, setInstall] = useState<InstallEvent | null>(null);
  useEffect(() => {
    if ("serviceWorker" in navigator)
      navigator.serviceWorker.register("/sw.js").catch(() => undefined);
    const connection = () => setOffline(!navigator.onLine);
    const prompt = (event: Event) => {
      event.preventDefault();
      setInstall(event as InstallEvent);
    };
    const message = () =>
      window.dispatchEvent(new Event("notifications-updated"));
    const installed = () => setInstall(null);
    connection();
    window.addEventListener("online", connection);
    window.addEventListener("offline", connection);
    window.addEventListener("beforeinstallprompt", prompt);
    window.addEventListener("appinstalled", installed);
    navigator.serviceWorker?.addEventListener("message", message);
    return () => {
      window.removeEventListener("online", connection);
      window.removeEventListener("offline", connection);
      window.removeEventListener("beforeinstallprompt", prompt);
      window.removeEventListener("appinstalled", installed);
      navigator.serviceWorker?.removeEventListener("message", message);
    };
  }, []);
  return (
    <>
      {offline && (
        <div className="connection-banner" role="status">
          You’re offline. Reconnect to upload files, view current orders, or
          save changes.
        </div>
      )}
      {install && (
        <button
          className="install-app btn btn-secondary"
          onClick={async () => {
            await install.prompt();
            await install.userChoice;
            setInstall(null);
          }}
        >
          Install app
        </button>
      )}
    </>
  );
}
