// Server component. Cached pages render both currencies; an inline script picks the visitor's before paint.
import { useLocale } from "next-intl";

import { money } from "@/lib/format";
import type { Money } from "@/lib/types";

export default function Price({ prices, template }: { prices: Money; template?: (formatted: string) => string }) {
  const locale = useLocale();
  const fmt = (cur: "INR" | "USD") => {
    const s = money(prices[cur], cur, locale);
    return template ? template(s) : s;
  };
  return (
    <>
      <span data-cur="INR">{fmt("INR")}</span>
      <span data-cur="USD">{fmt("USD")}</span>
    </>
  );
}

/** Sets <html data-currency> from the cookie before first paint (no flash, works with ISR). */
export const CURRENCY_SCRIPT = `try{var m=document.cookie.match(/(?:^|; )pp_currency=(INR|USD)/);document.documentElement.dataset.currency=m?m[1]:"INR"}catch(e){}`;
