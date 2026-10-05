"use client";
import { useState } from "react";

import { Card, PageTitle, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

/** The single source for every promise on the site (PRD §9). Every change is audited and revalidates the storefront. */
export default function SiteConfigPage() {
  const { data, reload } = useApi<Record<string, unknown>>("/admin/config");
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const { run, busy, view } = useAction();
  if (!data) return <p>Loading…</p>;
  return (
    <>
      <PageTitle>Site config</PageTitle>
      {view}
      {Object.entries(data).map(([key, value]) => {
        const text = drafts[key] ?? JSON.stringify(value, null, 2);
        return (
          <Card key={key} title={<code>{key}</code>} actions={drafts[key] !== undefined && (
            <button className="pp-btn pp-btn-primary min-h-10" disabled={busy} onClick={() => run(async () => {
              await api(`/admin/config/${key}`, { method: "PUT", json: { value: JSON.parse(text) } });
              setDrafts((d) => Object.fromEntries(Object.entries(d).filter(([k]) => k !== key)));
              reload();
            }, `${key} saved.`)}>Save</button>
          )}>
            <textarea className="pp-input min-h-20 font-mono text-small" value={text} spellCheck={false}
              onChange={(e) => setDrafts({ ...drafts, [key]: e.target.value })} aria-label={key} />
          </Card>
        );
      })}
    </>
  );
}
