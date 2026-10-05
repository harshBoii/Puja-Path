"use client";
import { useState } from "react";

import { PageTitle, Table, fmtDate, useApi } from "@/components/admin/ui";

type A = { id: number; actor: string; action: string; entity: string; entity_id: string; diff: unknown; at: string };

export default function Audit() {
  const [entity, setEntity] = useState("");
  const { data } = useApi<A[]>(`/admin/audit${entity ? `?entity=${entity}` : ""}`);
  return (
    <>
      <PageTitle actions={<select className="pp-input w-auto" value={entity} onChange={(e) => setEntity(e.target.value)} aria-label="Entity">
        <option value="">All</option>{["booking", "puja", "puja_event", "temple", "site_config", "staff_user", "review", "campaign"].map((x) => <option key={x}>{x}</option>)}
      </select>}>Audit log</PageTitle>
      <Table head={["At", "Actor", "Action", "Entity", "Diff"]} rows={(data ?? []).map((a) => [fmtDate(a.at), a.actor, a.action, `${a.entity} ${a.entity_id}`,
        <details key="d"><summary className="cursor-pointer text-small">view</summary><pre className="max-w-xl overflow-auto text-small">{JSON.stringify(a.diff, null, 2)}</pre></details>])} />
    </>
  );
}
