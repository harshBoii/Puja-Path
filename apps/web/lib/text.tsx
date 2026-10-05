/** Minimal rich text for CMS fields: paragraphs and line breaks (server-rendered, no JS). */
export function Paragraphs({ text, className }: { text: string | null | undefined; className?: string }) {
  if (!text) return null;
  return (
    <div className={`pp-prose ${className ?? ""}`}>
      {text.split(/\n{2,}/).map((p, i) => <p key={i} className="whitespace-pre-line">{p}</p>)}
    </div>
  );
}
