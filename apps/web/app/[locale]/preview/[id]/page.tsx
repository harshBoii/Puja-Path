import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { setRequestLocale } from "next-intl/server";

import PujaDetailView from "@/components/detail/PujaDetailView";
import { loadPuja } from "@/components/detail/loadPuja";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { robots: { index: false, follow: false } };

/** CMS side-by-side preview: the real detail page rendered from unpublished copy (staff cookie required). */
export default async function Preview({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const puja = await loadPuja(locale, Number(id), true);
  if (!puja) notFound();
  return <PujaDetailView puja={puja} />;
}
