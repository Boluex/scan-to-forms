import PwaProvider from "@/components/PwaProvider";
import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  manifest: "/manifest.webmanifest",
  appleWebApp: {
    capable: true,
    title: "ScanToForms",
    statusBarStyle: "default",
  },
  icons: { apple: "/icon-192.png", icon: "/icon-192.png" },
  title: "ScanToForms — Paper questionnaires, digitized",
  description:
    "Turn completed paper questionnaires into structured, reviewable data.",
};

export const viewport: Viewport = { themeColor: "#243d35" };

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <PwaProvider />
        {process.env.NEXT_PUBLIC_DEPLOYMENT_NOTICE && (
          <aside
            role="note"
            style={{
              padding: "12px 20px",
              background: "#fff3cd",
              color: "#664d03",
              textAlign: "center",
            }}
          >
            {process.env.NEXT_PUBLIC_DEPLOYMENT_NOTICE}
          </aside>
        )}
        {children}
      </body>
    </html>
  );
}
