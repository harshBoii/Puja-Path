import type { Instrumentation } from "next";

export function register() {}

/** Server render errors: always a structured JSON log line; also sent to Sentry when SENTRY_DSN is set.
 *  Uses Sentry's envelope endpoint directly so no SDK ships in the client bundle (PRD §12 JS budget). */
export const onRequestError: Instrumentation.onRequestError = async (err, request, context) => {
  const error = err instanceof Error ? err : new Error(String(err));
  const digest = typeof err === "object" && err !== null && "digest" in err ? String((err as { digest: unknown }).digest) : undefined;
  console.error(JSON.stringify({ level: "error", msg: "render error", path: request.path, method: request.method,
    route: context.routePath, type: context.routeType, digest, error: error.message }));
  const dsn = process.env.SENTRY_DSN;
  if (!dsn) return;
  try {
    const u = new URL(dsn);
    const project = u.pathname.replace(/\//g, "");
    const eventId = crypto.randomUUID().replace(/-/g, "");
    const event = {
      event_id: eventId, timestamp: Date.now() / 1000, platform: "javascript", level: "error",
      environment: process.env.APP_ENV ?? "production", server_name: "web",
      transaction: context.routePath, tags: { route_type: context.routeType, digest },
      request: { url: request.path, method: request.method },
      exception: { values: [{ type: error.name, value: error.message,
        stacktrace: { frames: (error.stack ?? "").split("\n").slice(1, 30).reverse().map((l) => ({ function: l.trim() })) } }] },
    };
    const body = `${JSON.stringify({ event_id: eventId, dsn })}\n${JSON.stringify({ type: "event" })}\n${JSON.stringify(event)}`;
    await fetch(`${u.protocol}//${u.host}/api/${project}/envelope/`, {
      method: "POST", body,
      headers: { "Content-Type": "application/x-sentry-envelope",
        "X-Sentry-Auth": `Sentry sentry_version=7, sentry_key=${u.username}, sentry_client=pujapath-web/1.0` },
    });
  } catch { /* never let reporting break a response */ }
};
