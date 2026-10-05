"use client";
// Resumable chunked upload to /v1/admin/uploads: survives flaky temple Wi-Fi by resuming from the server's offset.
import { api } from "@/lib/client";

export type UploadPurpose = "sankalp_video" | "full_video" | "event_photo" | "image" | "clips_bulk";

export async function resumableUpload(file: File, complete: { purpose: UploadPurpose; event_id?: number; temple_id?: number;
  taken_on?: string; alt?: Record<string, string>; in_gallery?: boolean }, onProgress?: (pct: number) => void) {
  const key = `pp_upload:${file.name}:${file.size}:${file.lastModified}`;
  let id = localStorage.getItem(key);
  let offset = 0;
  let chunk = 8 * 1024 * 1024;
  if (id) {
    try { offset = (await api<{ offset: number }>(`/admin/uploads/${id}`)).offset; } catch { id = null; }
  }
  if (!id) {
    const init = await api<{ upload_id: string; chunk_size: number }>("/admin/uploads", { method: "POST",
      json: { filename: file.name, size: file.size, content_type: file.type || "application/octet-stream" } });
    id = init.upload_id;
    chunk = init.chunk_size;
    localStorage.setItem(key, id);
  }
  while (offset < file.size) {
    const body = file.slice(offset, offset + chunk);
    let tries = 0;
    for (;;) {
      try {
        const r = await fetch(`/api/v1/admin/uploads/${id}?offset=${offset}`, { method: "PUT", body, credentials: "same-origin" });
        if (r.status === 409) { offset = (await r.json()).detail.offset; break; }
        if (!r.ok) throw new Error(`upload ${r.status}`);
        offset = (await r.json()).offset;
        break;
      } catch (e) {
        if (++tries > 5) throw e;
        await new Promise((res) => setTimeout(res, 1000 * 2 ** tries));
      }
    }
    onProgress?.(Math.round((offset / file.size) * 100));
  }
  const result = await api<Record<string, unknown>>(`/admin/uploads/${id}/complete`, { method: "POST", json: complete });
  localStorage.removeItem(key);
  return result;
}
