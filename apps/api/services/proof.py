"""Proof videos — PRD §6/§7: marker tool, per-booking clips with ffmpeg, QC sampling, WhatsApp delivery."""

import asyncio
import logging
import math
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from logging_setup import log
from models import Booking, BookingStatus, ProofClip, PujaEvent, QcStatus
from providers.media.storage import fetch_to_local, public_url, put_file
from providers.media.video import playback
from services import bookings as booking_svc
from services import notify
from services.audit import audit

logger = logging.getLogger("proof")
S = BookingStatus
INLINE_MAX_BYTES = 15 * 1024 * 1024
TAIL_MS = 2000
SHORT_CLIP_MS = 5000


class ProofError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code


async def save_markers(db: AsyncSession, ev: PujaEvent, markers: list[dict], staff_id: int) -> int:
    """markers: [{booking_id, start_ms}] in sheet order. Each clip runs to the next marker + 2 s."""
    if not ev.sankalp_video_key:
        raise ProofError("no_sankalp_video")
    ordered = sorted(markers, key=lambda m: m["start_ms"])
    for i, m in enumerate(ordered):
        b = await db.get(Booking, uuid.UUID(str(m["booking_id"])))
        if b is None or b.puja_event_id != ev.id:
            raise ProofError("booking_not_in_event", str(m["booking_id"]))
        end = ordered[i + 1]["start_ms"] + TAIL_MS if i + 1 < len(ordered) else None
        clip = (await db.execute(select(ProofClip).where(ProofClip.booking_id == b.id))).scalar_one_or_none()
        if clip is None:
            clip = ProofClip(booking_id=b.id, puja_event_id=ev.id, start_ms=m["start_ms"])
            db.add(clip)
        if clip.qc_status == QcStatus.approved:
            continue
        clip.start_ms, clip.end_ms = int(m["start_ms"]), end
        clip.r2_key = clip.thumb_key = None
        clip.size_bytes = None
        clip.qc_status = QcStatus.pending
    await audit(db, staff_id, "proof.markers_saved", "puja_event", ev.id, {"count": len(ordered)})
    return len(ordered)


async def _run(*args: str) -> str:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    if proc.returncode != 0:
        raise ProofError("ffmpeg_failed", err.decode()[-500:])
    return out.decode()


async def duration_ms(path: Path) -> int:
    out = await _run("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path))
    return int(float(out.strip()) * 1000)


async def transcode_clip(src: Path, start_ms: int, end_ms: int | None, out_dir: Path, name: str) -> tuple[Path, Path]:
    """720p H.264 + AAC MP4 (WhatsApp-compatible) and a JPEG thumbnail."""
    out = out_dir / f"{name}.mp4"
    # -ss before -i seeks fast and accurately when re-encoding; -t gives the clip length.
    args = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{start_ms / 1000:.3f}", "-i", str(src)]
    if end_ms is not None:
        args += ["-t", f"{(end_ms - start_ms) / 1000:.3f}"]
    args += ["-vf", "scale=-2:'min(720,ih)'", "-c:v", "libx264", "-preset", "veryfast", "-profile:v", "main",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)]
    await _run(*args)
    thumb = out_dir / f"{name}.jpg"
    await _run("ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", str(out), "-frames:v", "1",
               "-vf", "scale=-2:720", "-q:v", "4", str(thumb))
    return out, thumb


async def cut_event_clips(db: AsyncSession, ev: PujaEvent) -> int:
    if not ev.sankalp_video_key:
        raise ProofError("no_sankalp_video")
    src = fetch_to_local(ev.sankalp_video_key)
    total = await duration_ms(src)
    clips = (await db.execute(select(ProofClip).where(ProofClip.puja_event_id == ev.id,
                                                      ProofClip.qc_status != QcStatus.approved))).scalars().all()
    out_dir = Path(tempfile.mkdtemp())
    n = 0
    for clip in clips:
        b = await db.get(Booking, clip.booking_id)
        end = min(clip.end_ms, total) if clip.end_ms else total
        mp4, jpg = await transcode_clip(src, clip.start_ms, end, out_dir, b.code)
        key = f"proof/event-{ev.id}/{b.code}-{uuid.uuid4().hex[:8]}.mp4"
        put_file(mp4, key, "video/mp4")
        put_file(jpg, key.replace(".mp4", ".jpg"), "image/jpeg")
        clip.r2_key, clip.thumb_key = key, key.replace(".mp4", ".jpg")
        clip.size_bytes = mp4.stat().st_size
        clip.end_ms = end
        clip.qc_status = QcStatus.pending
        n += 1
    log(logger, "clips cut", event_id=ev.id, clips=n)
    return n


def required_sample(clips: list[ProofClip]) -> tuple[int, set[uuid.UUID]]:
    """QC rule: spot-check at least 1 in 10 clips, and every clip under 5 seconds."""
    short = {c.id for c in clips if c.end_ms is not None and c.end_ms - c.start_ms < SHORT_CLIP_MS}
    return max(1, math.ceil(len(clips) / 10)), short


async def approve_batch(db: AsyncSession, ev: PujaEvent, reviewed_ids: list[str], rejected_ids: list[str],
                        staff_id: int) -> dict:
    clips = (await db.execute(select(ProofClip).where(ProofClip.puja_event_id == ev.id,
                                                      ProofClip.qc_status == QcStatus.pending,
                                                      ProofClip.r2_key.is_not(None)))).scalars().all()
    if not clips:
        raise ProofError("no_clips")
    reviewed = {uuid.UUID(x) for x in reviewed_ids}
    rejected = {uuid.UUID(x) for x in rejected_ids}
    need, short = required_sample(clips)
    if len(reviewed & {c.id for c in clips}) < need:
        raise ProofError("sample_too_small", f"review at least {need} clips")
    if not short <= reviewed:
        raise ProofError("short_clips_unreviewed", f"{len(short - reviewed)} short clips not reviewed")
    approved = 0
    for c in clips:
        if c.id in rejected:
            c.qc_status = QcStatus.rejected
            continue
        c.qc_status = QcStatus.approved
        b = await db.get(Booking, c.booking_id)
        if b.status == S.locked:
            await booking_svc.transition(db, b, S.performed)
        if b.status == S.performed:
            await booking_svc.transition(db, b, S.proof_ready)
            await queue_proof_message(db, b, c)
        approved += 1
    await audit(db, staff_id, "proof.qc_approved", "puja_event", ev.id,
                {"approved": approved, "rejected": len(rejected), "reviewed": len(reviewed)})
    return {"approved": approved, "rejected": len(rejected)}


async def queue_proof_message(db: AsyncSession, b: Booking, clip: ProofClip) -> None:
    c = await booking_svc.ctx(db, b)
    inline = bool(clip.size_bytes and clip.size_bytes <= INLINE_MAX_BYTES)
    clip.sent_inline = inline
    header = public_url(clip.r2_key if inline else clip.thumb_key)
    await notify.queue(db, template_key="proof_video", to=b.whatsapp_e164, locale=b.locale, booking=b,
                       params=[c["name"], c["puja"], c["temple"], c["date"]], header_media_url=header,
                       button_params=[booking_svc.proof_path(b)])


async def bulk_match(db: AsyncSession, ev: PujaEvent, files: list[tuple[str, Path]], staff_id: int) -> dict:
    """Fallback for small events: files named {booking_code}.mp4 are matched automatically."""
    matched, unmatched = [], []
    out_dir = Path(tempfile.mkdtemp())
    for filename, path in files:
        code = Path(filename).stem.upper().strip()
        b = (await db.execute(select(Booking).where(Booking.code == code, Booking.puja_event_id == ev.id))
             ).scalar_one_or_none()
        if b is None:
            unmatched.append(filename)
            continue
        total = await duration_ms(path)
        mp4, jpg = await transcode_clip(path, 0, total, out_dir, code)
        key = f"proof/event-{ev.id}/{code}-{uuid.uuid4().hex[:8]}.mp4"
        put_file(mp4, key, "video/mp4")
        put_file(jpg, key.replace(".mp4", ".jpg"), "image/jpeg")
        clip = (await db.execute(select(ProofClip).where(ProofClip.booking_id == b.id))).scalar_one_or_none()
        if clip is None:
            clip = ProofClip(booking_id=b.id, puja_event_id=ev.id, start_ms=0)
            db.add(clip)
        clip.start_ms, clip.end_ms, clip.r2_key, clip.thumb_key = 0, total, key, key.replace(".mp4", ".jpg")
        clip.size_bytes, clip.qc_status = mp4.stat().st_size, QcStatus.pending
        matched.append(code)
    await audit(db, staff_id, "proof.bulk_upload", "puja_event", ev.id, {"matched": matched, "unmatched": unmatched})
    return {"matched": matched, "unmatched": unmatched}


async def proof_page(db: AsyncSession, token: str) -> dict | None:
    b = (await db.execute(select(Booking).where(Booking.proof_token == token))).scalar_one_or_none()
    if b is None or b.status not in (S.proof_ready, S.proof_sent, S.completed):
        return None
    clip = (await db.execute(select(ProofClip).where(ProofClip.booking_id == b.id,
                                                     ProofClip.qc_status == QcStatus.approved))).scalar_one_or_none()
    c = await booking_svc.ctx(db, b)
    ev = c["event"]
    return {
        "locale": b.locale, "code": b.code, "puja": c["puja"], "temple": c["temple"],
        "starts_at": ev.starts_at.isoformat(), "names": [n.name for n in b.names],
        "clip": {"url": public_url(clip.r2_key), "poster": public_url(clip.thumb_key)} if clip else None,
        "full_video": playback(ev.full_video_stream_id),
        "photos": [{"url": public_url(p.get("key")), "alt": (p.get("alt") or {}).get(b.locale, "")}
                   for p in (ev.photos or [])],
        "puja_id": ev.puja_id,
    }
