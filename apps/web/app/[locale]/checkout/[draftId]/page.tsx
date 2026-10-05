import type { Metadata } from "next";
import { setRequestLocale } from "next-intl/server";
import { Suspense } from "react";

import Checkout from "@/components/checkout/Checkout";

export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function CheckoutPage({ params }: { params: Promise<{ locale: string; draftId: string }> }) {
  const { locale, draftId } = await params;
  setRequestLocale(locale);
  return <Suspense><Checkout draftId={draftId} /></Suspense>;
}
