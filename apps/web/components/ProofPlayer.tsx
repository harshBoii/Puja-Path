"use client";
import { useEffect, useRef } from "react";

/** MP4 or HLS (Cloudflare Stream signed URL). Never autoplays with sound. */
export default function ProofPlayer({ src, type, poster, label }: { src: string; type: "mp4" | "hls"; poster?: string; label: string }) {
  const ref = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    const v = ref.current;
    if (!v || type !== "hls") return;
    if (v.canPlayType("application/vnd.apple.mpegurl")) { v.src = src; return; }
    let hls: { destroy: () => void } | null = null;
    import("hls.js").then(({ default: Hls }) => {
      if (Hls.isSupported()) { const h = new Hls(); h.loadSource(src); h.attachMedia(v); hls = h; }
    });
    return () => hls?.destroy();
  }, [src, type]);
  return (
    <video ref={ref} controls playsInline preload="metadata" poster={poster} aria-label={label}
      className="aspect-video w-full rounded-card bg-ink-900" src={type === "mp4" ? src : undefined} />
  );
}
