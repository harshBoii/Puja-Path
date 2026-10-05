"use client";
import { Badge, Card, Field, PageTitle, Table, fmtDate, statusTone, useAction, useApi, useStaff } from "@/components/admin/ui";
import { api } from "@/lib/client";

type T = { key: string; locale: string; category: string; ref: string; status: string; variables: string[]; body: string | null };
type Stats = Record<string, Record<string, number | null>>;
type In = { from: string; text: string | null; button: string | null; booking_id: string | null; at: string };
type Camp = { id: number; template: string; locale: string; interest_tag: string | null; recipients: number; skipped_cap: number; at: string };

export default function Messaging() {
  const staff = useStaff();
  const isAdmin = staff?.role === "admin";
  const tpl = useApi<{ provider: string; templates: T[] }>("/admin/templates");
  const stats = useApi<Stats>("/admin/messages/stats");
  const inbound = useApi<In[]>("/admin/inbound");
  const camps = useApi<Camp[]>(isAdmin ? "/admin/campaigns" : null);
  const pujas = useApi<{ id: number; title: string; status: string }[]>("/admin/pujas");
  const { run, busy, view } = useAction();
  return (
    <>
      <PageTitle actions={isAdmin && <button className="pp-btn pp-btn-secondary" disabled={busy}
        onClick={() => run(async () => { const r = await api("/admin/templates/sync", { method: "POST" }); tpl.reload(); return r; }, "Synced from provider.")}>Sync templates</button>}>
        Messaging <span className="text-h3 text-ink-600">· {tpl.data?.provider}</span>
      </PageTitle>
      {view}
      <Card title="Delivery and read rates (last 30 days)">
        <Table head={["Template", "Sent", "Delivered", "Read", "Failed", "Delivery rate", "Read rate"]} rows={Object.entries(stats.data ?? {}).map(([k, s]) => [
          k, s.sent, s.delivered, s.read, s.failed, s.delivery_rate == null ? "—" : `${Math.round((s.delivery_rate ?? 0) * 100)}%`,
          s.read_rate == null ? "—" : `${Math.round((s.read_rate ?? 0) * 100)}%`])} />
      </Card>
      <Card title="Test send to a staff number">
        <form className="grid gap-2 sm:grid-cols-4" onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          run(async () => { const r = await api<{ preview: string }>("/admin/templates/test-send", { method: "POST", json: {
            template_key: fd.get("key"), locale: fd.get("locale"), to_e164: fd.get("to") } }); return r; }, "Queued.");
        }}>
          <select name="key" className="pp-input">{[...new Set((tpl.data?.templates ?? []).map((t) => t.key))].map((k) => <option key={k}>{k}</option>)}</select>
          <select name="locale" className="pp-input">{["en", "hi", "ta", "te"].map((l) => <option key={l}>{l}</option>)}</select>
          <input name="to" className="pp-input" placeholder="+91…" required />
          <button className="pp-btn pp-btn-primary" disabled={busy}>Send test</button>
        </form>
      </Card>
      {isAdmin && (
        <Card title="Marketing campaign (opted-in devotees only, max 2 per devotee per week)">
          <form className="grid gap-2 sm:grid-cols-5" onSubmit={(e) => {
            e.preventDefault();
            const fd = new FormData(e.currentTarget);
            if (!window.confirm("Send this campaign to every opted-in devotee in the segment?")) return;
            run(async () => { const r = await api("/admin/campaigns", { method: "POST", json: { template_key: "festival_offer", locale: fd.get("locale"),
              festival: fd.get("festival"), puja_id: Number(fd.get("puja")), interest_tag: fd.get("tag") || null } }); camps.reload(); return r; }, "Campaign queued.");
          }}>
            <Field label="Locale"><select name="locale" className="pp-input">{["te", "hi", "ta", "en"].map((l) => <option key={l}>{l}</option>)}</select></Field>
            <Field label="Festival"><input name="festival" required className="pp-input" /></Field>
            <Field label="Puja"><select name="puja" className="pp-input">{(pujas.data ?? []).filter((p) => p.status === "published").map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></Field>
            <Field label="Interest tag (optional)"><input name="tag" className="pp-input" placeholder="e.g. shiva" /></Field>
            <button className="pp-btn pp-btn-primary self-end" disabled={busy}>Send</button>
          </form>
          <div className="mt-3"><Table head={["When", "Locale", "Segment", "Recipients", "Skipped (cap)"]} rows={(camps.data ?? []).map((c) => [
            fmtDate(c.at), c.locale, c.interest_tag ?? "all", c.recipients, c.skipped_cap])} empty="No campaigns yet." /></div>
        </Card>
      )}
      <Card title="Templates">
        <Table head={["Key", "Locale", "Category", "Provider ref", "Status", "Body"]} rows={(tpl.data?.templates ?? []).map((t) => [
          t.key, t.locale, t.category, <code key="r" className="text-small">{t.ref}</code>, <Badge key="s" tone={statusTone(t.status)}>{t.status}</Badge>,
          <span key="b" lang={t.locale} className="text-small">{t.body}</span>])} />
      </Card>
      <Card title="Inbound (latest)">
        <Table head={["At", "From", "Text / button", "Booking"]} rows={(inbound.data ?? []).map((m) => [fmtDate(m.at), m.from, m.text ?? m.button, m.booking_id ?? "—"])} />
      </Card>
    </>
  );
}
