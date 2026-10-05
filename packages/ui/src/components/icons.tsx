// Line icons (1.75px stroke, Lucide-style geometry) plus original devotional glyphs drawn for this brand.
import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement> & { size?: number };

function Svg({ size = 24, children, ...rest }: P & { children: React.ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const IconHome = (p: P) => (
  <Svg {...p}><path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" /></Svg>
);
export const IconUser = (p: P) => (
  <Svg {...p}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></Svg>
);
export const IconSearch = (p: P) => (
  <Svg {...p}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Svg>
);
export const IconFilter = (p: P) => (
  <Svg {...p}><path d="M4 6h16M7 12h10M10 18h4" /></Svg>
);
export const IconX = (p: P) => (
  <Svg {...p}><path d="M18 6 6 18M6 6l12 12" /></Svg>
);
export const IconCheck = (p: P) => (
  <Svg {...p}><path d="M20 6 9 17l-5-5" /></Svg>
);
export const IconChevronDown = (p: P) => (
  <Svg {...p}><path d="m6 9 6 6 6-6" /></Svg>
);
export const IconChevronLeft = (p: P) => (
  <Svg {...p}><path d="m15 18-6-6 6-6" /></Svg>
);
export const IconChevronRight = (p: P) => (
  <Svg {...p}><path d="m9 18 6-6-6-6" /></Svg>
);
export const IconHeart = ({ filled, ...p }: P & { filled?: boolean }) => (
  <Svg {...p} fill={filled ? "currentColor" : "none"}>
    <path d="M19 14c1.5-1.5 3-3.3 3-5.5A5.5 5.5 0 0 0 12 5a5.5 5.5 0 0 0-10 3.5c0 2.2 1.5 4 3 5.5l7 7z" />
  </Svg>
);
export const IconShare = (p: P) => (
  <Svg {...p}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><path d="m8.6 13.5 6.8 4M15.4 6.5l-6.8 4" /></Svg>
);
export const IconPhone = (p: P) => (
  <Svg {...p}><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z" /></Svg>
);
export const IconClock = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Svg>
);
export const IconCalendar = (p: P) => (
  <Svg {...p}><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></Svg>
);
export const IconMapPin = (p: P) => (
  <Svg {...p}><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0" /><circle cx="12" cy="10" r="3" /></Svg>
);
export const IconVideo = (p: P) => (
  <Svg {...p}><rect x="2" y="6" width="14" height="12" rx="2" /><path d="m22 8-6 4 6 4z" /></Svg>
);
export const IconShield = (p: P) => (
  <Svg {...p}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" /><path d="m9 12 2 2 4-4" /></Svg>
);
export const IconGrid = (p: P) => (
  <Svg {...p}><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></Svg>
);
export const IconRepeat = (p: P) => (
  <Svg {...p}><path d="m17 2 4 4-4 4" /><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4" /><path d="M21 13v2a3 3 0 0 1-3 3H3" /></Svg>
);
export const IconPackage = (p: P) => (
  <Svg {...p}><path d="M21 8 12 3 3 8v8l9 5 9-5z" /><path d="m3 8 9 5 9-5M12 13v8" /></Svg>
);
export const IconStar = ({ filled, ...p }: P & { filled?: boolean }) => (
  <Svg {...p} fill={filled ? "currentColor" : "none"}><path d="m12 2 3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z" /></Svg>
);
export const IconGlobe = (p: P) => (
  <Svg {...p}><circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18" /></Svg>
);
export const IconDownload = (p: P) => (
  <Svg {...p}><path d="M12 3v12m-5-5 5 5 5-5M5 21h14" /></Svg>
);
export const IconPlus = (p: P) => (
  <Svg {...p}><path d="M12 5v14M5 12h14" /></Svg>
);
export const IconMinus = (p: P) => (
  <Svg {...p}><path d="M5 12h14" /></Svg>
);

/** Official-style WhatsApp glyph in its brand green so older users find it by the icon. */
export const IconWhatsApp = ({ size = 22, ...p }: P) => (
  <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" focusable="false" {...p}>
    <path
      fill="var(--whatsapp-green)"
      d="M16 3C9 3 3.3 8.6 3.3 15.6c0 2.2.6 4.4 1.7 6.3L3 29l7.3-1.9c1.8 1 3.8 1.5 5.8 1.5 7 0 12.7-5.7 12.7-12.6S23 3 16 3z"
    />
    <path
      fill="#fff"
      d="M23.2 19.6c-.3.9-1.8 1.7-2.5 1.8-.6.1-1.4.1-2.3-.1-.5-.2-1.2-.4-2.1-.8-3.7-1.6-6.1-5.3-6.3-5.6-.2-.2-1.5-2-1.5-3.8s1-2.7 1.3-3.1c.3-.4.7-.5 1-.5h.7c.2 0 .5-.1.8.6l1.1 2.6c.1.2.1.4 0 .6l-.4.6-.5.6c-.2.2-.4.4-.2.7.2.4 1 1.6 2.1 2.6 1.4 1.3 2.6 1.7 3 1.9.4.2.6.2.8-.1l1.1-1.3c.3-.4.5-.3.9-.2l2.5 1.2c.4.2.6.3.7.4.1.2.1 1-.2 1.9z"
    />
  </svg>
);

// ---- original devotional glyphs (lotus, diya, kalash, temple, bell, conch)
function Glyph({ size = 28, children, ...rest }: P & { children: React.ReactNode }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" stroke="currentColor" strokeWidth={1.75}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...rest}>
      {children}
    </svg>
  );
}
export const GlyphLotus = (p: P) => (
  <Glyph {...p}>
    <path d="M16 25c-3-3-3-8 0-13 3 5 3 10 0 13z" />
    <path d="M16 25c-4-1-7-5-6.5-9 3 .5 5.5 4 6.5 9zM16 25c4-1 7-5 6.5-9-3 .5-5.5 4-6.5 9z" />
    <path d="M16 25c-5 .5-9-1.5-11-5 4-.5 8 1.5 11 5zM16 25c5 .5 9-1.5 11-5-4-.5-8 1.5-11 5z" />
  </Glyph>
);
export const GlyphDiya = (p: P) => (
  <Glyph {...p}>
    <path d="M5 19c3 4 19 4 22 0-2 3-6 5-11 5S7 22 5 19z" />
    <path d="M16 18c-2-2.5-1.5-5.5 0-8 1.5 2.5 2 5.5 0 8z" />
  </Glyph>
);
export const GlyphKalash = (p: P) => (
  <Glyph {...p}>
    <path d="M11 13h10l-1 2c3 1.5 4 4.5 2.5 7.5-1 2-4 3-6.5 3s-5.5-1-6.5-3c-1.5-3-.5-6 2.5-7.5z" />
    <path d="M12 13c1-3 2.5-4.5 4-5.5 1.5 1 3 2.5 4 5.5" />
    <circle cx="16" cy="6" r="2" />
  </Glyph>
);
export const GlyphTemple = (p: P) => (
  <Glyph {...p}>
    <path d="M6 27V17h20v10M9 17l2-4h10l2 4M12 13l1.5-3h5L20 13M15 10l1-3 1 3" />
    <path d="M14 27v-4a2 2 0 0 1 4 0v4" />
  </Glyph>
);
export const GlyphBell = (p: P) => (
  <Glyph {...p}>
    <path d="M10 22c0-6 1-11 6-12 5 1 6 6 6 12z" />
    <path d="M8 22h16M16 10V6M16 25v1" />
  </Glyph>
);
export const GlyphConch = (p: P) => (
  <Glyph {...p}>
    <path d="M7 19c2-6 7-9 13-8 4 1 5 4 4 7-1 3-5 5-9 5s-7-1-8-4z" />
    <path d="M13 14c3 0 6 1 7 4M24 18l3 1-2 2" />
  </Glyph>
);
