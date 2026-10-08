import Settings from "@/app/dashboard/settings/page";
import GoogleSignIn from "@/components/GoogleSignIn";
import PushSettings from "@/components/PushSettings";
export default function Account() {
  return (
    <>
      <Settings />
      <section className="mvp-panel">
        <h2>Connected account</h2>
        <p>
          Link Google with the same email address to sign in without a password.
        </p>
        <GoogleSignIn link />
      </section>
      <PushSettings />
    </>
  );
}
