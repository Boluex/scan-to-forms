"use client";
import { useEffect, useState } from "react";
import { BellRing } from "lucide-react";
import { disablePush, enablePush, pushEnabled } from "@/lib/push";
export default function PushSettings() {
  const [enabled, setEnabled] = useState(false),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  useEffect(() => {
    setEnabled(pushEnabled());
  }, []);
  async function toggle() {
    setBusy(true);
    setMessage("");
    try {
      if (enabled) await disablePush();
      else await enablePush();
      setEnabled(!enabled);
      setMessage(
        enabled
          ? "Notifications disabled on this device."
          : "You’ll receive order updates and announcements on this device.",
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to update notifications.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="mvp-panel push-settings">
      <div className="section-icon">
        <BellRing size={22} />
      </div>
      <div>
        <h2>Stay up to date</h2>
        <p>
          Get notified when your results are ready, even when you’re away from
          the app.
        </p>
        <p className="form-note">
          On iPhone or iPad, add ScanToForms to your Home Screen first. Your
          inbox keeps every update.
        </p>
        {message && <p role="status">{message}</p>}
      </div>
      <button className="btn btn-secondary" onClick={toggle} disabled={busy}>
        {busy
          ? "Updating…"
          : enabled
            ? "Disable notifications"
            : "Enable notifications"}
      </button>
    </section>
  );
}
