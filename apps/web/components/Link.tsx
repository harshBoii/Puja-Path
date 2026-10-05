// The only place allowed to import next/link (ESLint: pujapath/no-raw-internal-link).
// Every internal href is written without a locale and gets the current one, so no link drops the locale.
import NextLink from "next/link";
import { useLocale } from "next-intl";
import type { ComponentProps } from "react";

export function localeHref(locale: string, href: string): string {
  if (!href.startsWith("/") || href.startsWith("//") || href.startsWith("/api/") || href.startsWith("/media/")) return href;
  return href === "/" ? `/${locale}` : `/${locale}${href}`;
}

/** Viewport prefetching is off by default: on a budget Android phone, prefetching every visible link's
 *  payload blocks the main thread for seconds (PRD §12 performance budget). Pass prefetch to opt in. */
export default function Link({ href, locale: forced, prefetch = false, ...rest }: Omit<ComponentProps<typeof NextLink>, "href" | "locale"> & {
  href: string; locale?: string;
}) {
  const current = useLocale();
  return <NextLink href={localeHref(forced ?? current, href)} prefetch={prefetch} {...rest} />;
}
