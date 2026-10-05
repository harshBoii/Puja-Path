import type { Meta, StoryObj } from "@storybook/react-vite";

const COLORS = ["marble-50", "marble-100", "marble-200", "marble-400", "surface", "ink-900", "ink-600", "gold-100", "gold-300",
  "gold-500", "gold-600", "gold-700", "sindoor-600", "tulsi-600"];
const TYPE = [["Display", "text-display font-display"], ["H1", "text-h1 font-display"], ["H2", "text-h2 font-display"],
  ["H3", "text-h3 font-display"], ["Body", "text-body"], ["Small", "text-small"]];
const SAMPLE: Record<string, string> = { en: "Sankalp in your name and gotra", hi: "आपके नाम और गोत्र से संकल्प",
  ta: "உங்கள் பெயர் மற்றும் கோத்திரத்தில் சங்கல்பம்", te: "మీ పేరు మరియు గోత్రంతో సంకల్పం" };

const meta: Meta = { title: "Foundations/Tokens" };
export default meta;

export const Colours: StoryObj = {
  render: () => (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {COLORS.map((c) => (
        <div key={c} className="pp-card overflow-hidden">
          <div className="h-16 border-b border-marble-200" style={{ background: `var(--${c})` }} />
          <p className="p-2 text-small font-semibold">{c}</p>
        </div>
      ))}
      <div className="pp-card overflow-hidden"><div className="h-16" style={{ background: "var(--gold-foil)" }} /><p className="p-2 text-small font-semibold">gold-foil (decorative)</p></div>
    </div>
  ),
};

export const Typography: StoryObj = {
  render: (_, { globals }) => (
    <div className="space-y-3">
      {TYPE.map(([name, cls]) => <p key={name} className={cls}><span className="mr-3 text-small text-ink-600">{name}</span>{SAMPLE[globals.locale as string]}</p>)}
      <p className="pp-foil-text font-display text-display">{SAMPLE[globals.locale as string]}</p>
    </div>
  ),
};

export const Buttons: StoryObj = {
  render: () => (
    <div className="flex flex-wrap gap-3">
      <button className="pp-btn pp-btn-primary">Primary</button>
      <button className="pp-btn pp-btn-secondary">Secondary</button>
      <button className="pp-btn pp-btn-whatsapp">WhatsApp</button>
      <a className="pp-link" href="#x">Text link</a>
      <button className="pp-btn pp-btn-primary" disabled>Disabled</button>
      <span className="pp-chip">Chip</span><span className="pp-chip" data-selected="true">Selected chip</span>
    </div>
  ),
};

export const Surfaces: StoryObj = {
  render: () => (
    <div className="grid gap-4 sm:grid-cols-3">
      <div className="pp-marble pp-card p-6">Marble texture (6–8%)</div>
      <div className="pp-card border pp-hairline p-6">Gold hairline</div>
      <div className="pp-card pp-foil-border p-6">Gold-foil border (selected)</div>
    </div>
  ),
};
