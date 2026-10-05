"use client";

import { useCallback, useEffect, useId, useRef, useState, type ButtonHTMLAttributes, type MouseEvent, type ReactNode } from "react";

import { IconChevronLeft, IconChevronRight, IconMinus, IconPlus, IconX } from "./icons";
import { cx } from "./static";

// ---------------------------------------------------------------- buttons with a loading spinner
/** A button whose onClick may return a promise: while it is pending the button shows a spinner (via
 *  aria-busy, styled in tokens.css) and ignores further clicks. Only this button spins, not its neighbours. */
export function AsyncButton({ onClick, loading, disabled, children, ...rest }:
  Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onClick"> & {
    onClick?: (e: MouseEvent<HTMLButtonElement>) => unknown; loading?: boolean;
  }) {
  const [pending, setPending] = useState(false);
  const busy = Boolean(loading || pending);
  return (
    <button type="button" {...rest} disabled={disabled || busy} aria-busy={busy || undefined}
      onClick={async (e) => {
        const result = onClick?.(e);
        if (result && typeof (result as Promise<unknown>).then === "function") {
          setPending(true);
          try { await result; } finally { setPending(false); }
        }
      }}>
      {children}
    </button>
  );
}

// ---------------------------------------------------------------- package selector (radio cards)
export function PackageSelector({ options, value, onChange, legend }: {
  options: { id: number; label: string; namesLabel: string; priceLabel: ReactNode }[];
  value: number | null; onChange: (id: number) => void; legend: string;
}) {
  const name = useId();
  return (
    <fieldset className="@container">
      <legend className="mb-3 text-h3">{legend}</legend>
      <div className="grid gap-3 @lg:grid-cols-3">
        {options.map((o) => {
          const selected = o.id === value;
          return (
            <label key={o.id}
              className={cx("relative flex min-h-12 cursor-pointer items-center justify-between gap-3 rounded-card p-4",
                selected ? "pp-foil-border shadow-card" : "border border-gold-line bg-surface")}>
              <input type="radio" name={name} value={o.id} checked={selected} onChange={() => onChange(o.id)}
                className="peer sr-only" />
              <span>
                <span className="block font-semibold">{o.label}</span>
                <span className="block text-small text-ink-600">{o.namesLabel}</span>
              </span>
              <span className="font-semibold tabular-nums">{o.priceLabel}</span>
              <span className="pointer-events-none absolute inset-0 rounded-card peer-focus-visible:outline peer-focus-visible:outline-3 peer-focus-visible:outline-gold-600" />
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}

// ---------------------------------------------------------------- quantity stepper
export function QtyStepper({ value, max, onChange, label, decLabel, incLabel }: {
  value: number; max: number; onChange: (n: number) => void; label: string; decLabel: string; incLabel: string;
}) {
  return (
    <div className="inline-flex shrink-0 items-center rounded-btn border border-gold-600 bg-surface" role="group" aria-label={label}>
      <button type="button" className="flex h-12 w-12 items-center justify-center text-gold-700 disabled:text-marble-400"
        onClick={() => onChange(Math.max(0, value - 1))} disabled={value <= 0} aria-label={decLabel}><IconMinus /></button>
      <output className="w-8 text-center font-semibold tabular-nums" aria-live="polite">{value}</output>
      <button type="button" className="flex h-12 w-12 items-center justify-center text-gold-700 disabled:text-marble-400"
        onClick={() => onChange(Math.min(max, value + 1))} disabled={value >= max} aria-label={incLabel}><IconPlus /></button>
    </div>
  );
}

// ---------------------------------------------------------------- bottom sheet (mobile filters)
export function BottomSheet({ open, onClose, title, children, footer, closeLabel }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; closeLabel: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} onClose={onClose} onCancel={onClose} aria-label={title}
      className="m-0 mt-auto max-h-[85vh] w-full max-w-none rounded-t-[20px] bg-surface p-0 text-ink-900 backdrop:bg-ink-900/40 md:m-auto md:max-w-lg md:rounded-card">
      <div className="flex items-center justify-between border-b border-gold-line px-4 py-3">
        <h2 className="text-h3">{title}</h2>
        <button type="button" onClick={onClose} className="flex h-12 w-12 items-center justify-center" aria-label={closeLabel}>
          <IconX />
        </button>
      </div>
      <div className="max-h-[60vh] overflow-y-auto px-4 py-4">{children}</div>
      {footer && <div className="flex gap-3 border-t border-gold-line px-4 py-3">{footer}</div>}
    </dialog>
  );
}

// ---------------------------------------------------------------- toast
export function Toast({ message, tone = "info", onDone }: { message: string | null; tone?: "info" | "error" | "success"; onDone: () => void }) {
  useEffect(() => {
    if (!message) return;
    const t = setTimeout(onDone, 5000);
    return () => clearTimeout(t);
  }, [message, onDone]);
  if (!message) return null;
  return (
    <div role={tone === "error" ? "alert" : "status"}
      className={cx("fixed inset-x-4 bottom-24 z-50 mx-auto max-w-md rounded-btn px-4 py-3 font-medium shadow-card md:bottom-8",
        tone === "error" ? "bg-sindoor-600 text-surface" : tone === "success" ? "bg-tulsi-600 text-surface" : "bg-ink-900 text-gold-100")}>
      {message}
    </div>
  );
}

// ---------------------------------------------------------------- countdown (real deadline only)
function parts(ms: number) {
  const s = Math.max(0, Math.floor(ms / 1000));
  return { d: Math.floor(s / 86400), h: Math.floor((s % 86400) / 3600), m: Math.floor((s % 3600) / 60), s: s % 60 };
}

/** Counts down to a real `booking_cutoff_at` passed from the server render; hides itself at zero. */
export function Countdown({ deadlineIso, initialRemainingMs, format }: {
  deadlineIso: string; initialRemainingMs: number; format: (p: { d: number; h: number; m: number; s: number }) => string;
}) {
  const deadline = new Date(deadlineIso).getTime();
  const [remaining, setRemaining] = useState(initialRemainingMs);
  useEffect(() => {
    const tick = () => setRemaining(deadline - Date.now());
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, [deadline]);
  if (remaining <= 0) return null;
  return <span className="tabular-nums" suppressHydrationWarning>{format(parts(remaining))}</span>;
}

// ---------------------------------------------------------------- hero carousel
export function HeroCarousel({ slides, prevLabel, nextLabel, label }: {
  slides: ReactNode[]; prevLabel: string; nextLabel: string; label: string;
}) {
  const [i, setI] = useState(0);
  const [paused, setPaused] = useState(false);
  const touchX = useRef<number | null>(null);
  const n = slides.length;
  const go = useCallback((d: number) => setI((x) => (x + d + n) % n), [n]);
  useEffect(() => {
    if (paused || n < 2) return;
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const t = setInterval(() => go(1), 6000);
    return () => clearInterval(t);
  }, [paused, n, go]);
  if (!n) return null;
  return (
    <section aria-roledescription="carousel" aria-label={label} className="relative"
      onTouchStart={(e) => { setPaused(true); touchX.current = e.touches[0].clientX; }}
      onTouchEnd={(e) => {
        if (touchX.current === null) return;
        const dx = e.changedTouches[0].clientX - touchX.current;
        if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
        touchX.current = null;
      }}
      onMouseEnter={() => setPaused(true)} onMouseLeave={() => setPaused(false)} onFocus={() => setPaused(true)}>
      <div className="relative">
        {slides.map((s, k) => (
          <div key={k} aria-roledescription="slide" aria-hidden={k !== i}
            className={cx("transition-opacity duration-[400ms]", k === i ? "relative opacity-100" : "pointer-events-none absolute inset-0 opacity-0")}
            {...(k !== i ? { inert: true } : {})}>
            {s}
          </div>
        ))}
      </div>
      {n > 1 && (
        <div className="mt-4 flex items-center justify-center gap-2">
          <button type="button" onClick={() => go(-1)} aria-label={prevLabel}
            className="flex h-12 w-12 items-center justify-center rounded-full border border-gold-600 bg-surface text-gold-700"><IconChevronLeft /></button>
          {slides.map((_, k) => (
            <button key={k} type="button" onClick={() => setI(k)} aria-label={`${k + 1} / ${n}`} aria-current={k === i}
              className="flex h-12 w-6 items-center justify-center">
              <span className={cx("block h-2.5 rounded-full transition-all", k === i ? "w-6 bg-gold-600" : "w-2.5 bg-marble-400")} />
            </button>
          ))}
          <button type="button" onClick={() => go(1)} aria-label={nextLabel}
            className="flex h-12 w-12 items-center justify-center rounded-full border border-gold-600 bg-surface text-gold-700"><IconChevronRight /></button>
        </div>
      )}
    </section>
  );
}

// ---------------------------------------------------------------- sticky section nav
export function SectionNav({ sections, label }: { sections: { id: string; label: string }[]; label: string }) {
  const [active, setActive] = useState(sections[0]?.id);
  useEffect(() => {
    const obs = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible[0]) setActive(visible[0].target.id);
      },
      { rootMargin: "-120px 0px -60% 0px" },
    );
    sections.forEach((s) => { const el = document.getElementById(s.id); if (el) obs.observe(el); });
    return () => obs.disconnect();
  }, [sections]);
  return (
    <nav aria-label={label} className="sticky top-16 z-20 -mx-4 border-b border-gold-line bg-surface/90 px-4 backdrop-blur-none md:top-20">
      <ul className="pp-scroll-x flex gap-2 py-2">
        {sections.map((s) => (
          <li key={s.id} className="snap-start">
            <a href={`#${s.id}`} className="pp-chip no-underline" aria-current={active === s.id}>{s.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

/** Mobile sticky bar under a gold hairline: selected package, price, primary action. */
export function StickyBookBar({ title, price, action }: { title: string; price: ReactNode; action: ReactNode }) {
  return (
    <div className="fixed inset-x-0 bottom-[calc(4rem+env(safe-area-inset-bottom))] z-30 border-t pp-hairline bg-surface px-4 py-2 md:hidden">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-small text-ink-600">{title}</p>
          <p className="font-semibold tabular-nums">{price}</p>
        </div>
        {action}
      </div>
    </div>
  );
}
