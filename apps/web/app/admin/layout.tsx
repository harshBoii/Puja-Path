import "../globals.css";

import type { Metadata, Viewport } from "next";

import { adminFonts } from "@/lib/fonts";

export const metadata: Metadata = { title: "Admin", robots: { index: false, follow: false } };
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function AdminRootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={adminFonts.className} style={adminFonts.style}>
      <body className="min-h-dvh bg-marble-50">{children}</body>
    </html>
  );
}
