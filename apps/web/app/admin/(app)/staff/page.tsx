"use client";
import { Badge, Card, Field, PageTitle, Table, useAction, useApi } from "@/components/admin/ui";
import { api } from "@/lib/client";

type S = { id: number; email: string; name: string; role: string; active: boolean; totp_enrolled: boolean; two_factor: boolean };
const ROLES = ["admin", "catalog_editor", "ops_coordinator", "support_agent", "finance"];

export default function Staff() {
  const { data, reload } = useApi<S[]>("/admin/staff");
  const twoFactor = Boolean(data?.[0]?.two_factor);
  const { run, busy, view } = useAction();
  return (
    <>
      <PageTitle>Staff</PageTitle>
      {view}
      <Card title="Add staff member">
        <form className="grid gap-2 sm:grid-cols-5" onSubmit={(e) => {
          e.preventDefault();
          const form = e.currentTarget;
          const fd = new FormData(form);
          run(async () => { await api("/admin/staff", { method: "POST", json: Object.fromEntries(fd) }); form.reset(); reload(); }, "Added. They enrol 2FA at first sign-in.");
        }}>
          <Field label="Name"><input name="name" required className="pp-input" /></Field>
          <Field label="Email"><input name="email" type="email" required className="pp-input" /></Field>
          <Field label="Role"><select name="role" className="pp-input">{ROLES.map((r) => <option key={r}>{r}</option>)}</select></Field>
          <Field label="Initial password"><input name="password" type="password" minLength={10} required className="pp-input" /></Field>
          <button className="pp-btn pp-btn-primary self-end" disabled={busy}>Add</button>
        </form>
      </Card>
      <Table head={["Name", "Email", "Role", ...(twoFactor ? ["2FA"] : []), "Active", ""]} rows={(data ?? []).map((s) => [s.name, s.email,
        <select key="r" className="pp-input min-h-9 py-1" defaultValue={s.role} onChange={(e) => run(async () => { await api(`/admin/staff/${s.id}`, { method: "PATCH", json: { role: e.target.value } }); reload(); }, "Role updated.")}>
          {ROLES.map((r) => <option key={r}>{r}</option>)}</select>,
        ...(twoFactor ? [<Badge key="t" tone={s.totp_enrolled ? "green" : "grey"}>{s.totp_enrolled ? "enrolled" : "pending"}</Badge>] : []),
        <Badge key="a" tone={s.active ? "green" : "red"}>{s.active ? "active" : "disabled"}</Badge>,
        <span key="x" className="flex gap-3">
          <button className="pp-link" onClick={() => run(async () => { await api(`/admin/staff/${s.id}`, { method: "PATCH", json: { active: !s.active } }); reload(); })}>{s.active ? "Disable" : "Enable"}</button>
          {twoFactor && <button className="pp-link" onClick={() => run(async () => { await api(`/admin/staff/${s.id}`, { method: "PATCH", json: { reset_totp: true } }); reload(); }, "2FA reset.")}>Reset 2FA</button>}
        </span>])} />
    </>
  );
}
