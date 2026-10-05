import { revalidateTag } from "next/cache";
import { NextResponse, type NextRequest } from "next/server";

/** Called by the API when the admin publishes, and by the worker at each booking cutoff. */
export async function POST(req: NextRequest) {
  if (req.headers.get("x-revalidate-secret") !== process.env.REVALIDATE_SECRET) {
    return NextResponse.json({ ok: false }, { status: 401 });
  }
  const { tags } = (await req.json()) as { tags: string[] };
  // expire: 0 -> the next request renders fresh content (published changes appear immediately)
  for (const tag of tags ?? []) revalidateTag(tag, { expire: 0 });
  return NextResponse.json({ ok: true, revalidated: tags });
}
