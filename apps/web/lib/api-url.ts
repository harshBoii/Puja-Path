/** API base URL from the API_URL env var. Accepts "api.example.com", "https://api.example.com/" etc.
 *  Shared by next.config.ts (rewrites) and server-side fetches. */
export function apiBaseUrl(): string {
  const raw = (process.env.API_URL ?? "").trim();
  if (!raw) {
    if (process.env.VERCEL || process.env.NODE_ENV === "production") {
      throw new Error("API_URL is not set. Set it to your FastAPI URL, e.g. https://pujapath-api.onrender.com");
    }
    return "http://localhost:8000";
  }
  const withScheme = /^https?:\/\//i.test(raw) ? raw : `${/^(localhost|127\.)/.test(raw) ? "http" : "https"}://${raw}`;
  return withScheme.replace(/\/+$/, "");
}
