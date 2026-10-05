"use client";
import { UiLinkContext } from "@pujapath/ui";
import type { ReactNode } from "react";

import Link from "@/components/Link";

const UiLinkAdapter = (props: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => <Link {...props} />;

export default function Providers({ children }: { children: ReactNode }) {
  return <UiLinkContext.Provider value={UiLinkAdapter}>{children}</UiLinkContext.Provider>;
}
