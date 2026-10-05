// Server-safe presentational components. All copy arrives as props; nothing here hardcodes user-facing text.
import type { ReactNode } from "react";

import {
  GlyphDiya,
  GlyphKalash,
  GlyphLotus,
  GlyphTemple,
  IconCalendar,
  IconCheck,
  IconMapPin,
  IconShield,
  IconStar,
  IconVideo,
} from "./icons";
import { UiLink } from "./link";

export function cx(...parts: (string | false | null | undefined)[]) {
  return parts.filter(Boolean).join(" ");
}

// ---------------------------------------------------------------- ornaments
export function OrnamentDivider({ className }: { className?: string }) {
  return (
    <div className={cx("flex items-center gap-3 py-2 text-gold-600", className)} aria-hidden="true">
      <span className="h-px flex-1 bg-gradient-to-r from-transparent to-gold-600" />
      <GlyphLotus size={26} />
      <span className="h-px flex-1 bg-gradient-to-l from-transparent to-gold-600" />
    </div>
  );
}

/** Temple-arch mask with a gold-foil stroke (one SVG path for both). */
export function ArchFrame({ src, alt, srcSet, sizes, priority, className }: {
  src: string; alt: string; srcSet?: string; sizes?: string; priority?: boolean; className?: string;
}) {
  return (
    <div className={cx("relative aspect-[10/13] w-full", className)}>
      <img
        src={src}
        srcSet={srcSet}
        sizes={sizes}
        alt={alt}
        className="pp-arch absolute inset-0 h-full w-full object-cover"
        loading={priority ? "eager" : "lazy"}
        fetchPriority={priority ? "high" : undefined}
        decoding="async"
      />
      <svg viewBox="0 0 100 130" preserveAspectRatio="none" className="pointer-events-none absolute inset-0 h-full w-full"
        aria-hidden="true">
        <defs>
          <linearGradient id="pp-foil" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#8C6A1F" /><stop offset=".4" stopColor="#D4AF37" />
            <stop offset=".55" stopColor="#F3E3A3" /><stop offset=".75" stopColor="#B8922E" />
            <stop offset="1" stopColor="#8C6A1F" />
          </linearGradient>
        </defs>
        <path d="M1 129V52C1 25 22 10 50 1c28 9 49 24 49 51v77Z" fill="none" stroke="url(#pp-foil)" strokeWidth="1.6"
          vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
  );
}

export function SectionTitle({ children, kicker, id, className }: {
  children: ReactNode; kicker?: ReactNode; id?: string; className?: string;
}) {
  return (
    <div className={cx("mb-5", className)}>
      {kicker && <p className="mb-1 text-small font-medium text-gold-700">{kicker}</p>}
      <h2 id={id} className="text-h2 text-ink-900">{children}</h2>
    </div>
  );
}

// ---------------------------------------------------------------- home blocks
export function PromiseStrip({ items }: { items: { key: string; label: string }[] }) {
  const icons: Record<string, ReactNode> = {
    sankalp: <GlyphDiya size={28} />, venue: <GlyphTemple size={28} />, video: <IconVideo size={26} />,
    verified: <IconShield size={26} />,
  };
  return (
    <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {items.map((it) => (
        <li key={it.key} className="pp-card flex items-center gap-3 border border-gold-line px-3 py-3 text-small">
          <span className="shrink-0 text-gold-700">{icons[it.key] ?? <IconCheck />}</span>
          <span className="font-medium">{it.label}</span>
        </li>
      ))}
    </ul>
  );
}

export function StepsRow({ steps }: { steps: { title: string; text: string }[] }) {
  const glyphs = [GlyphLotus, GlyphKalash, GlyphDiya, IconVideo];
  return (
    <ol className="grid gap-4 md:grid-cols-4">
      {steps.map((s, i) => {
        const G = glyphs[i % glyphs.length];
        return (
          <li key={s.title} className="flex gap-3 md:flex-col">
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-gold-600 bg-surface text-gold-700">
              <G size={24} />
            </span>
            <div>
              <p className="font-semibold"><span className="text-gold-700">{i + 1}. </span>{s.title}</p>
              <p className="text-small text-ink-600">{s.text}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function TrustBar({ items, asOf, label }: { items: { key: string; text: string }[]; asOf: string; label: string }) {
  if (!items.length) return null;
  return (
    <section aria-label={label} className="pp-card border border-gold-line px-4 py-4">
      <ul className="flex flex-wrap justify-center gap-x-8 gap-y-2 text-center">
        {items.map((it) => (
          <li key={it.key} className="font-display text-h3 text-ink-900">{it.text}</li>
        ))}
      </ul>
      <p className="mt-1 text-center text-small text-ink-600">{asOf}</p>
    </section>
  );
}

// ---------------------------------------------------------------- cards
export function VenueBadge({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center rounded-chip border border-gold-600 bg-gold-100 px-2 py-0.5 text-small font-medium text-gold-700">
      {label}
    </span>
  );
}

export function OccasionChip({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-chip border border-gold-600 bg-surface/95 px-2.5 py-0.5 text-small font-semibold text-gold-700">
      {children}
    </span>
  );
}

export function PujaCard({ href, image, chip, title, temple, venue, dateLabel, priceLabel, bookLabel, featured, action }: {
  href: string; image?: { url: string; alt: string; srcset?: string } | null; chip?: string | null; title: string;
  temple: string; venue: string; dateLabel?: ReactNode; priceLabel?: ReactNode; bookLabel: string; featured?: boolean;
  action?: ReactNode;
}) {
  return (
    <article className={cx("pp-card relative flex h-full flex-col overflow-hidden", featured && "border border-gold-600")}>
      <div className="relative aspect-[4/3] bg-marble-100">
        {image && (
          <img src={image.url} srcSet={image.srcset} sizes="(min-width: 768px) 33vw, 90vw" alt={image.alt}
            loading="lazy" decoding="async" className="h-full w-full object-cover" />
        )}
        {chip && <span className="absolute left-3 top-3"><OccasionChip>{chip}</OccasionChip></span>}
        {action && <span className="absolute right-2 top-2 z-10">{action}</span>}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-4">
        <h3 className="pp-clamp-2 text-h3">
          <UiLink href={href} className="text-ink-900 no-underline after:absolute after:inset-0">{title}</UiLink>
        </h3>
        <p className="flex items-start gap-1.5 text-small text-ink-600">
          <IconMapPin size={18} className="mt-0.5 shrink-0 text-gold-700" />
          <span>{temple} · <VenueBadge label={venue} /></span>
        </p>
        {dateLabel && (
          <p className="flex items-center gap-1.5 text-small text-ink-900">
            <IconCalendar size={18} className="shrink-0 text-gold-700" />{dateLabel}
          </p>
        )}
        <div className="mt-auto flex items-center justify-between gap-3 pt-3">
          <span className="text-small font-semibold text-ink-900">{priceLabel}</span>
          <span className="pp-btn pp-btn-primary relative z-10 min-h-12 px-4 text-small" aria-hidden="true">{bookLabel}</span>
        </div>
      </div>
    </article>
  );
}

export function TempleCard({ href, image, name, city, venue }: {
  href: string; image?: { url: string; alt: string } | null; name: string; city: string; venue: string;
}) {
  return (
    <article className="pp-card relative w-64 shrink-0 snap-start overflow-hidden">
      <div className="aspect-[3/2] bg-marble-100">
        {image && <img src={image.url} alt={image.alt} loading="lazy" className="h-full w-full object-cover" />}
      </div>
      <div className="p-4">
        <h3 className="text-h3">
          <UiLink href={href} className="text-ink-900 no-underline after:absolute after:inset-0">{name}</UiLink>
        </h3>
        <p className="mt-1 flex items-center gap-2 text-small text-ink-600">{city} <VenueBadge label={venue} /></p>
      </div>
    </article>
  );
}

export function ReviewCard({ rating, text, name, meta, ratingLabel }: {
  rating: number; text?: string | null; name: string; meta: string; ratingLabel: string;
}) {
  return (
    <figure className="pp-card flex h-full flex-col gap-3 p-5">
      <div className="flex gap-0.5 text-gold-600" role="img" aria-label={ratingLabel}>
        {[1, 2, 3, 4, 5].map((i) => <IconStar key={i} size={18} filled={i <= rating} />)}
      </div>
      {text && <blockquote className="text-ink-900">“{text}”</blockquote>}
      <figcaption className="mt-auto text-small text-ink-600"><span className="font-semibold text-ink-900">{name}</span> · {meta}</figcaption>
    </figure>
  );
}

// ---------------------------------------------------------------- detail blocks
export function FactBox({ facts }: { facts: { label: string; value: string }[] }) {
  return (
    <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-card border border-gold-line bg-gold-line">
      {facts.map((f) => (
        <div key={f.label} className="bg-surface p-4">
          <dt className="text-small text-ink-600">{f.label}</dt>
          <dd className="font-semibold">{f.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function BenefitList({ items }: { items: { title: string; line: string }[] }) {
  return (
    <ul className="grid gap-3 md:grid-cols-3">
      {items.map((b) => (
        <li key={b.title} className="pp-card flex gap-3 p-4">
          <GlyphLotus size={24} className="shrink-0 text-gold-700" />
          <div><p className="font-semibold">{b.title}</p><p className="text-small text-ink-600">{b.line}</p></div>
        </li>
      ))}
    </ul>
  );
}

export function RitualSteps({ items, mainLabel }: { items: { title: string; text: string; main?: boolean }[]; mainLabel: string }) {
  return (
    <ol className="relative space-y-4 border-l border-gold-300 pl-6">
      {items.map((r, i) => (
        <li key={r.title} className="relative">
          <span className="absolute -left-[2.15rem] flex h-8 w-8 items-center justify-center rounded-full border border-gold-600 bg-surface text-small font-semibold text-gold-700">
            {i + 1}
          </span>
          <p className="font-semibold">
            {r.title}
            {r.main && <span className="ml-2 rounded-chip bg-gold-100 px-2 py-0.5 text-small font-medium text-gold-700">{mainLabel}</span>}
          </p>
          <p className="text-ink-600">{r.text}</p>
        </li>
      ))}
    </ol>
  );
}

export function DeliverablesList({ items, note }: { items: string[]; note: string }) {
  return (
    <div className="pp-card border border-gold-line p-5">
      <ul className="space-y-2">
        {items.map((d) => (
          <li key={d} className="flex items-start gap-2"><IconCheck size={20} className="mt-1 shrink-0 text-tulsi-600" />{d}</li>
        ))}
      </ul>
      <p className="mt-3 text-small text-ink-600">{note}</p>
    </div>
  );
}

/** FAQ accordion on native <details>: works without JavaScript and is keyboard-accessible. */
export function Accordion({ items }: { items: { q: string; a: string }[] }) {
  return (
    <div className="divide-y divide-gold-line rounded-card border border-gold-line bg-surface">
      {items.map((f) => (
        <details key={f.q} className="group px-4 py-1">
          <summary className="flex min-h-12 cursor-pointer list-none items-center justify-between gap-3 py-2 font-semibold [&::-webkit-details-marker]:hidden">
            {f.q}
            <span className="shrink-0 text-gold-700 transition-transform group-open:rotate-180" aria-hidden="true">▾</span>
          </summary>
          <p className="whitespace-pre-line pb-3 text-ink-600">{f.a}</p>
        </details>
      ))}
    </div>
  );
}

export function PriceSummary({ lines, totalLabel, total, note }: {
  lines: { label: string; value: string }[]; totalLabel: string; total: string; note?: string;
}) {
  return (
    <div className="pp-card p-5">
      <dl className="space-y-2">
        {lines.map((l) => (
          <div key={l.label} className="flex justify-between gap-4 text-ink-600"><dt>{l.label}</dt><dd className="tabular-nums">{l.value}</dd></div>
        ))}
        <div className="flex justify-between gap-4 border-t border-gold-600 pt-3 text-h3 font-semibold text-ink-900">
          <dt>{totalLabel}</dt><dd className="tabular-nums">{total}</dd>
        </div>
      </dl>
      {note && <p className="mt-2 text-small text-ink-600">{note}</p>}
    </div>
  );
}

export function BookingTimeline({ steps }: { steps: { key: string; label: string; done: boolean; at?: string | null }[] }) {
  return (
    <ol className="space-y-3">
      {steps.map((s) => (
        <li key={s.key} className="flex items-center gap-3">
          <span className={cx("flex h-8 w-8 items-center justify-center rounded-full border",
            s.done ? "border-tulsi-600 bg-tulsi-600 text-surface" : "border-marble-400 bg-surface text-marble-400")}>
            {s.done ? <IconCheck size={18} /> : <span className="h-2 w-2 rounded-full bg-marble-400" />}
          </span>
          <span className={cx("font-medium", !s.done && "text-ink-600")}>{s.label}</span>
          {s.at && <span className="ml-auto text-small text-ink-600">{s.at}</span>}
        </li>
      ))}
    </ol>
  );
}

export function EmptyState({ title, text, action }: { title: string; text?: string; action?: ReactNode }) {
  return (
    <div className="pp-card flex flex-col items-center gap-3 px-6 py-10 text-center">
      <GlyphDiya size={40} className="text-gold-600" />
      <p className="text-h3">{title}</p>
      {text && <p className="max-w-md text-ink-600">{text}</p>}
      {action}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("animate-pulse rounded-card bg-marble-100", className)} aria-hidden="true" />;
}

export function StatusChip({ status, label }: { status: string; label: string }) {
  const tone = ["completed", "proof_sent", "confirmed", "locked", "performed", "proof_ready"].includes(status)
    ? "border-tulsi-600 text-tulsi-600"
    : ["cancelled", "refunded"].includes(status) ? "border-sindoor-600 text-sindoor-600" : "border-gold-600 text-gold-700";
  return <span className={cx("inline-flex rounded-chip border bg-surface px-2.5 py-0.5 text-small font-semibold", tone)}>{label}</span>;
}

/** Loading state: a brass diya with a flickering flame. Announced to screen readers via role="status". */
export function DiyaLoader({ label, size = 72, className }: { label: string; size?: number; className?: string }) {
  return (
    <div role="status" aria-live="polite" className={cx("flex flex-col items-center justify-center gap-3 py-16", className)}>
      <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
        <defs>
          <radialGradient id="pp-diya-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0" stopColor="#F6EDD0" stopOpacity="0.95" />
            <stop offset="1" stopColor="#F6EDD0" stopOpacity="0" />
          </radialGradient>
          <linearGradient id="pp-diya-flame" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0" stopColor="#B8922E" />
            <stop offset="0.45" stopColor="#D4AF37" />
            <stop offset="1" stopColor="#F3E3A3" />
          </linearGradient>
          <linearGradient id="pp-diya-bowl" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#D4AF37" />
            <stop offset="1" stopColor="#7A5C17" />
          </linearGradient>
        </defs>
        <circle className="pp-diya-glow" cx="32" cy="24" r="20" fill="url(#pp-diya-glow)" />
        <path className="pp-diya-flame" d="M32 6c-5 7-7 12-7 16a7 7 0 0 0 14 0c0-4-2-9-7-16z" fill="url(#pp-diya-flame)" />
        <path d="M32 18c-2 3-3 5-3 7a3 3 0 0 0 6 0c0-2-1-4-3-7z" fill="#FFFDF5" opacity="0.85" className="pp-diya-flame" />
        <path d="M8 38c4 10 44 10 48 0-3 9-12 15-24 15S11 47 8 38z" fill="url(#pp-diya-bowl)" />
        <path d="M8 38c6 4 42 4 48 0" fill="none" stroke="#7A5C17" strokeWidth="1.5" strokeLinecap="round" />
        <path d="M30 34c1-2 3-2 4 0" fill="none" stroke="#2B2118" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
      <p className="text-small font-medium text-gold-700">{label}</p>
    </div>
  );
}
