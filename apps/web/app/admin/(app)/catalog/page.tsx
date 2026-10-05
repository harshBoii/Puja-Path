"use client";
import { DiyaLoader } from "@pujapath/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Badge, Card, Field, PageTitle, Table, statusTone, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

type Row = { id: number; title: string; kind: string; status: string; temple: string; locales: Record<string, boolean> };
type Temple = { id: number; name: string };

export default function Catalog() {
  const router = useRouter();
  const { data } = useApi<Row[]>("/admin/pujas");
  const temples = useApi<Temple[]>("/admin/temples");
  const { run, busy, view } = useAction();
  return (
    <>
      <PageTitle>Catalog</PageTitle>
      <Card title="New puja">
        {view}
        <form className="grid gap-3 sm:grid-cols-3" onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          // Required facts start empty: there are no CMS defaults (PRD §12).
          run(async () => {
            const p = await api<{ id: number }>("/admin/pujas", { method: "POST", json: {
              temple_id: Number(fd.get("temple")), kind: fd.get("kind"), slug: fd.get("slug") || null } });
            router.push(`/admin/catalog/${p.id}`);
          });
        }}>
          <Field label="Temple"><select name="temple" className="pp-input" required>{(temples.data ?? []).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
          <Field label="Kind"><select name="kind" className="pp-input"><option value="one_time">One-time puja</option><option value="seva">Seva (recurring)</option><option value="chadhava">Chadhava</option></select></Field>
          <Field label="Slug (optional)"><input name="slug" className="pp-input" /></Field>
          <button className="pp-btn pp-btn-primary sm:col-span-3 sm:w-fit" disabled={busy}>Create draft</button>
        </form>
      </Card>
      {!data ? <DiyaLoader label="Loading…" /> : (
        <Table head={["Title", "Kind", "Temple", "Status", "Locales (published)"]} rows={data.map((p) => [
          <Link key="t" href={`/admin/catalog/${p.id}`} className="pp-link font-semibold">{p.title}</Link>, p.kind, p.temple,
          <Badge key="s" tone={statusTone(p.status)}>{p.status}</Badge>,
          <span key="l" className="flex gap-1">{Object.entries(p.locales).map(([l, pub]) => <Badge key={l} tone={pub ? "green" : "grey"}>{l}</Badge>)}</span>])} />
      )}
    </>
  );
}
