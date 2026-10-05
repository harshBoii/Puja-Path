import { ImageResponse } from "next/og";

import { getConfig, getPuja } from "@/lib/api";
import { idFromSlug } from "@/lib/format";
import { SITE } from "@/lib/seo";

export const ogSize = { width: 1200, height: 630 };

/** 1200x630 OG image generated from the puja hero: marble ground, gold frame, the hero in an arch. */
export async function renderOg(locale: string, slug: string) {
  const id = idFromSlug(slug);
  const [p, config] = await Promise.all([id ? getPuja(locale, id) : null, getConfig()]);
  const hero = p?.images[0]?.url;
  const src = hero ? (hero.startsWith("http") ? hero : `${SITE}${hero}`) : null;
  let dataUrl: string | null = null;
  if (src) {
    try {
      const res = await fetch(src);
      const type = res.headers.get("content-type") ?? "image/svg+xml";
      if (/svg|png|jpe?g/.test(type)) dataUrl = `data:${type};base64,${Buffer.from(await res.arrayBuffer()).toString("base64")}`;
    } catch { /* fall back to the plain frame */ }
  }
  return new ImageResponse(
    (
      <div style={{ width: "100%", height: "100%", display: "flex", background: "#FBF9F5", padding: 28 }}>
        <div style={{ flex: 1, display: "flex", border: "3px solid #B8922E", borderRadius: 24, alignItems: "center",
          justifyContent: "space-between", padding: "0 64px", background: "linear-gradient(135deg,#FBF9F5,#F4F0E8)" }}>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <div style={{ fontSize: 30, color: "#7A5C17", letterSpacing: 4 }}>{config.brand.toUpperCase()}</div>
            <div style={{ width: 120, height: 3, background: "#D4AF37", marginTop: 18 }} />
          </div>
          {dataUrl && (
            <div style={{ display: "flex", width: 380, height: 494, borderTopLeftRadius: 190, borderTopRightRadius: 190,
              overflow: "hidden", border: "4px solid #D4AF37" }}>
              <img src={dataUrl} width={380} height={494} style={{ objectFit: "cover" }} alt="" />
            </div>
          )}
        </div>
      </div>
    ),
    ogSize,
  );
}
