import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import Link from "@/components/Link";
import ProofPlayer from "@/components/ProofPlayer";
import { getProof } from "@/lib/api";
import { dateIST } from "@/lib/format";

export const dynamic = "force-dynamic"; // SSR, unguessable token, never indexed
export const metadata: Metadata = { robots: { index: false, follow: false } };

export default async function ProofPage({ params }: { params: Promise<{ locale: string; token: string }> }) {
  const { locale, token } = await params;
  setRequestLocale(locale);
  const p = await getProof(token);
  if (!p) notFound();
  const t = await getTranslations();
  return (
    <article className="pp-gutter max-w-3xl space-y-6 pt-6">
      <header>
        <h1 className="pp-foil-text text-display">{t("proof.title", { puja: p.puja })}</h1>
        <p className="mt-2 text-ink-600">{t("proof.performedOn", { date: dateIST(p.starts_at, locale, { year: "numeric" }), temple: p.temple })}</p>
        <p className="font-semibold">{t("proof.forNames", { names: p.names.join(", ") })}</p>
      </header>
      {p.clip && <section><h2 className="mb-2 text-h3">{t("proof.clip")}</h2><ProofPlayer src={p.clip.url} poster={p.clip.poster} type="mp4" label={t("proof.clip")} /></section>}
      {p.full_video && <section><h2 className="mb-2 text-h3">{t("proof.full")}</h2><ProofPlayer src={p.full_video.url} type={p.full_video.type} label={t("proof.full")} /></section>}
      {p.photos.length > 0 && (
        <section><h2 className="mb-2 text-h3">{t("proof.photos")}</h2>
          <ul className="grid grid-cols-2 gap-3">{p.photos.map((ph) => <li key={ph.url}><img src={ph.url} alt={ph.alt} className="w-full rounded-card" loading="lazy" /></li>)}</ul>
        </section>
      )}
      <Link href="/pujas" className="pp-btn pp-btn-primary">{t("proof.bookYours")}</Link>
    </article>
  );
}
