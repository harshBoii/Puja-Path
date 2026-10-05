// One config value renders both the label and the link (PRD §12: displayed number = linked number).
import { IconPhone, IconWhatsApp } from "@pujapath/ui";

import { whatsappUrl } from "@/lib/format";

export function formatPhone(e164: string): string {
  const d = e164.replace(/\D/g, "");
  if (d.startsWith("91") && d.length === 12) return `+91 ${d.slice(2, 7)} ${d.slice(7)}`;
  return `+${d}`;
}

export function PhoneLink({ e164, className, children }: { e164: string; className?: string; children?: React.ReactNode }) {
  return (
    <a href={`tel:${e164}`} className={className}>
      {children ?? formatPhone(e164)}
    </a>
  );
}

export function WhatsAppButton({ e164, text, label, className, showNumber }: {
  e164: string; text: string; label: string; className?: string; showNumber?: boolean;
}) {
  return (
    <a href={whatsappUrl(e164, text)} target="_blank" rel="noopener noreferrer"
      className={className ?? "pp-btn pp-btn-whatsapp"}>
      <IconWhatsApp />
      <span>{label}{showNumber ? ` · ${formatPhone(e164)}` : ""}</span>
    </a>
  );
}

export function CallButton({ e164, label }: { e164: string; label: string }) {
  return (
    <PhoneLink e164={e164} className="pp-btn pp-btn-secondary">
      <IconPhone size={20} /> <span>{label}</span>
    </PhoneLink>
  );
}
