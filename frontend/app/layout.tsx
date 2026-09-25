import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ScanToForms — Paper questionnaires, digitized",
  description: "Turn completed paper questionnaires into structured, reviewable data.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        {process.env.NEXT_PUBLIC_DEPLOYMENT_NOTICE && (
          <aside role="note" style={{ padding: "12px 20px", background: "#fff3cd", color: "#664d03", textAlign: "center" }}>
            {process.env.NEXT_PUBLIC_DEPLOYMENT_NOTICE}
          </aside>
        )}
        {children}
      </body>
    </html>
  );
}
