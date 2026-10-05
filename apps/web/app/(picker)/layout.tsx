import "../globals.css";

import type { Metadata, Viewport } from "next";

import { adminFonts } from "@/lib/fonts";
import { SITE } from "@/lib/seo";

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#FBF9F5" };
export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  alternates: {
    languages: { te: `${SITE}/te`, hi: `${SITE}/hi`, ta: `${SITE}/ta`, en: `${SITE}/en`, "x-default": `${SITE}/` },
  },
};

export default function PickerLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={adminFonts.className} style={adminFonts.style}>
      <body className="min-h-dvh">{children}</body>
    </html>
  );
}
