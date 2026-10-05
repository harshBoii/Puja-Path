import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import { getTranslations, setRequestLocale } from "next-intl/server";

import { getPuja } from "@/lib/api";
import { idFromSlug, pujaPath } from "@/lib/format";
import { SITE, alternates } from "@/lib/seo";
import PujaDetailView from "./PujaDetailView";

type Props = { params: Promise<{ locale: string; slug: string }> };

export async function detailMetadata({ params }: Props): Promise<Metadata> {
  const { locale, slug } = await params;
  const id = idFromSlug(slug);
  const p = id ? await getPuja(locale, id) : null;
  if (!p) return {};
  const t = await getTranslations({ locale });
  const path = pujaPath(p);
  return {
    title: p.meta_title ?? p.title,
    description: p.meta_description ?? p.subtitle ?? t("meta.siteDescription"),
    alternates: alternates(locale, path, p.available_locales),
    openGraph: { title: p.meta_title ?? p.title, description: p.meta_description ?? undefined, url: `${SITE}/${locale}${path}`,
      type: "website", images: [`/${locale}${path}/opengraph-image`] },
  };
}

/** Static (ISR) detail page. Staff previews of unpublished copy live at /{locale}/preview/{id} instead,
 *  so this page never reads request data and stays cacheable. */
export async function DetailPage({ params, section }: Props & { section: "pujas" | "sevas" }) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const id = idFromSlug(slug);
  if (!id) notFound();
  const puja = await getPuja(locale, id);
  if (!puja) notFound();
  const canonical = pujaPath(puja);
  if (`/${section}/${slug}` !== canonical) permanentRedirect(`/${locale}${canonical}`);
  return <PujaDetailView puja={puja} />;
}
