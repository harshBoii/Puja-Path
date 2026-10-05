"use client";
import { Countdown } from "@pujapath/ui";

export default function CountdownText({ deadlineIso, initialRemainingMs, template }: {
  deadlineIso: string; initialRemainingMs: number; template: string;
}) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return (
    <Countdown deadlineIso={deadlineIso} initialRemainingMs={initialRemainingMs}
      format={({ d, h, m, s }) => template.replace("{time}", `${d > 0 ? `${d}d ` : ""}${pad(h)}:${pad(m)}:${pad(s)}`)} />
  );
}
