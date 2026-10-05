"use client";
import { IconGrid, IconHome, IconRepeat, IconUser, cx } from "@pujapath/ui";
import { useLocale } from "next-intl";
import { usePathname } from "next/navigation";

import Link from "@/components/Link";

/** Mobile bottom tabs on every page; all four keep the current locale. */
export default function BottomTabBar({ labels }: { labels: { home: string; pujas: string; sevas: string; account: string; nav: string } }) {
  const pathname = usePathname();
  const locale = useLocale();
  const rest = pathname.replace(new RegExp(`^/${locale}`), "") || "/";
  const tabs = [
    { href: "/", label: labels.home, icon: IconHome, active: rest === "/" },
    { href: "/pujas", label: labels.pujas, icon: IconGrid, active: rest.startsWith("/pujas") || rest.startsWith("/temples") },
    { href: "/sevas", label: labels.sevas, icon: IconRepeat, active: rest.startsWith("/sevas") },
    { href: "/account", label: labels.account, icon: IconUser, active: rest.startsWith("/account") },
  ];
  return (
    <nav aria-label={labels.nav}
      className="fixed inset-x-0 bottom-0 z-40 border-t border-gold-line bg-surface pb-[env(safe-area-inset-bottom)] md:hidden">
      <ul className="grid grid-cols-4">
        {tabs.map((t) => (
          <li key={t.href}>
            <Link href={t.href} aria-current={t.active ? "page" : undefined}
              className={cx("flex min-h-16 flex-col items-center justify-center gap-0.5 text-small no-underline",
                t.active ? "font-semibold text-gold-700" : "text-ink-600")}>
              <t.icon size={22} />
              {t.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
