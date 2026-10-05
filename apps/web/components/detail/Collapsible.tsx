"use client";
import { useState } from "react";

/** About text collapsed after 6 lines with "Read more". */
export default function Collapsible({ children, more, less }: { children: React.ReactNode; more: string; less: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div>
      <div className={open ? "" : "pp-clamp-6"}>{children}</div>
      <button type="button" className="pp-link mt-2 min-h-12" aria-expanded={open} onClick={() => setOpen(!open)}>
        {open ? less : more}
      </button>
    </div>
  );
}
