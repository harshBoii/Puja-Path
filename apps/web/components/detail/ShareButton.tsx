"use client";
import { IconShare } from "@pujapath/ui";

/** Web Share API, falling back to a WhatsApp share link with localized prefilled text. */
export default function ShareButton({ title, text, label }: { title: string; text: string; label: string }) {
  return (
    <button type="button" className="flex h-12 w-12 items-center justify-center rounded-full border border-gold-line bg-surface text-gold-700"
      aria-label={label} onClick={async () => {
        const url = window.location.href.split("?")[0];
        const body = text.replace("{url}", url);
        if (navigator.share) {
          try { await navigator.share({ title, text: body, url }); return; } catch { /* dismissed */ }
        }
        window.open(`https://wa.me/?text=${encodeURIComponent(body)}`, "_blank", "noopener");
      }}>
      <IconShare size={22} />
    </button>
  );
}
