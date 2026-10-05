"""Ops: events, today's queue, sankalp sheets, resumable uploads, marker tool, QC, SLA board, shipping."""

import json
import shutil
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from db import get_db
from deps import require_role
from models import (
    Booking,
    BookingStatus,
    MediaAsset,
    ProofClip,
    Puja,
    PujaEvent,
    Shipment,
    StaffRole,
    StaffUser,
)
from providers.media.images import process_image
from providers.media.storage import fetch_to_local, public_url, put_file
from providers.media.video import ingest, playback
from services import events as event_svc
from services import notify, site_config, sla
from services import proof as proof_svc
from services import shipping as shipping_svc
from services.audit import audit
from services.bookings import BookingError
from services.catalog import puja_title, temple_name
from services.i18n import IST, utcnow
from services.jobs import enqueue
from services.revalidate import puja_tags, revalidate

router = APIRouter(prefix="/v1/admin", tags=["admin"])
ops = require_role(StaffRole.ops_coordinator)
events_role = require_role(StaffRole.ops_coordinator, StaffRole.catalog_editor)
UPLOAD_DIR = settings.local_media_dir.parent / "uploads"
S = BookingStatus


async def _event_row(db: AsyncSession, ev: PujaEvent) -> dict:
    counts = dict((await db.execute(
        select(Booking.status, func.count()).where(Booking.puja_event_id == ev.id).group_by(Booking.status)
    )).all())
    paid = sum(v for k, v in counts.items() if k not in (S.draft, S.pending_payment, S.cancelled, S.refunded))
    return {"id": ev.id, "puja_id": ev.puja_id, "title": await puja_title(db, ev.puja_id, "en"),
            "temple": await temple_name(db, ev.puja.temple_id, "en"), "starts_at": ev.starts_at.isoformat(),
            "booking_cutoff_at": ev.booking_cutoff_at.isoformat(), "video_sla_hours": ev.video_sla_hours,
            "sla_due_at": sla.due_at(ev).isoformat(), "status": ev.status.value, "booking_count": paid,
            "locked": ev.locked_at is not None, "sankalp_sheet_url": public_url(ev.sankalp_sheet_key),
            "sankalp_video": bool(ev.sankalp_video_key), "full_video": playback(ev.full_video_stream_id),
            "photos": [{"url": public_url(p.get("key")), **p} for p in (ev.photos or [])],
            "rescheduled_to_event_id": ev.rescheduled_to_event_id}


# ------------------------------------------------------------------ events
@router.get("/events")
async def list_events(puja_id: int | None = None, upcoming: bool = True, db: AsyncSession = Depends(get_db),
                      _: StaffUser = Depends(events_role)):
    stmt = select(PujaEvent).order_by(PujaEvent.starts_at)
    if puja_id:
        stmt = stmt.where(PujaEvent.puja_id == puja_id)
    if upcoming:
        stmt = stmt.where(PujaEvent.starts_at > utcnow() - timedelta(days=2))
    return [await _event_row(db, e) for e in (await db.execute(stmt.limit(300))).scalars()]


class EventIn(BaseModel):
    puja_id: int
    starts_at: datetime  # naive = IST
    cutoff_hours: int | None = Field(default=None, ge=1, le=240)
    video_sla_hours: int | None = Field(default=None, ge=1, le=720)


@router.post("/events", status_code=201)
async def create_event(body: EventIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(events_role)):
    puja = await db.get(Puja, body.puja_id)
    if puja is None:
        raise HTTPException(404, "not_found")
    starts = body.starts_at if body.starts_at.tzinfo else body.starts_at.replace(tzinfo=IST)
    cutoff_h = body.cutoff_hours or await site_config.get(db, "booking_cutoff_hours_default")
    sla_h = body.video_sla_hours or puja.video_sla_hours or await site_config.get(db, "video_sla_hours_default")
    ev = PujaEvent(puja_id=puja.id, starts_at=starts, booking_cutoff_at=starts - timedelta(hours=cutoff_h),
                   video_sla_hours=sla_h)
    db.add(ev)
    await db.flush()
    await audit(db, staff.id, "event.create", "puja_event", ev.id, body.model_dump())
    await db.commit()
    await revalidate(puja_tags(puja.id))
    return await _event_row(db, await db.get(PujaEvent, ev.id))


class SeriesIn(BaseModel):
    puja_id: int
    rrule: str
    first_starts_at: datetime
    count: int = Field(ge=1, le=104)
    cutoff_hours: int | None = None
    video_sla_hours: int | None = None


@router.post("/events/series", status_code=201)
async def create_series(body: SeriesIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(events_role)):
    try:
        evs = await event_svc.generate_series(db, puja_id=body.puja_id, rrule=body.rrule,
                                              first_start_ist=body.first_starts_at, count=body.count,
                                              video_sla_hours=body.video_sla_hours, cutoff_hours=body.cutoff_hours)
    except ValueError as e:
        raise HTTPException(400, "bad_rrule") from e
    await audit(db, staff.id, "event.series", "puja", body.puja_id, body.model_dump())
    await db.commit()
    await revalidate(puja_tags(body.puja_id))
    return {"created": [e.id for e in evs]}


@router.get("/events/{event_id}")
async def get_event(event_id: int, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(events_role)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    return await _event_row(db, ev)


@router.get("/today")
async def today(day: date | None = None, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(ops)):
    d = day or utcnow().astimezone(IST).date()
    lo = datetime.combine(d, datetime.min.time(), tzinfo=IST)
    rows = (await db.execute(select(PujaEvent).where(PujaEvent.starts_at >= lo,
                                                     PujaEvent.starts_at < lo + timedelta(days=1))
                             .order_by(PujaEvent.starts_at))).scalars().all()
    # Events performed earlier whose proof is still pending stay on the queue.
    pending = (await db.execute(
        select(PujaEvent).join(Booking, Booking.puja_event_id == PujaEvent.id)
        .where(PujaEvent.starts_at < lo, PujaEvent.starts_at > lo - timedelta(days=10),
               Booking.status.in_([S.locked, S.performed])).distinct()
    )).scalars().all()
    return {"date": d.isoformat(), "events": [await _event_row(db, e) for e in rows],
            "carry_over": [await _event_row(db, e) for e in pending if e not in rows]}


@router.get("/events/{event_id}/sheet")
async def sheet(event_id: int, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    return {"event": await _event_row(db, ev), "sankalp_language": ev.puja.sankalp_language,
            "rows": await event_svc.sheet_rows(db, ev)}


@router.get("/events/{event_id}/sheet.pdf")
async def sheet_pdf(event_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    if not ev.sankalp_sheet_key:
        if ev.locked_at is None:
            raise HTTPException(409, "not_locked_yet")
        await event_svc.render_sheet(db, ev)
        await db.commit()
    return FileResponse(fetch_to_local(ev.sankalp_sheet_key), media_type="application/pdf",
                        filename=f"sankalp-sheet-{ev.id}.pdf")


@router.post("/events/{event_id}/lock")
async def lock(event_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    if ev.locked_at is None:
        await event_svc.lock_now(db, ev)
        await audit(db, staff.id, "event.lock", "puja_event", ev.id)
        await db.commit()
    return await _event_row(db, ev)


@router.post("/events/{event_id}/started")
async def started(event_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    try:
        n = await event_svc.mark_started(db, ev, staff.id)
    except BookingError as e:
        raise HTTPException(409, e.code) from e
    await notify.commit_and_dispatch(db)
    await revalidate(puja_tags(ev.puja_id))
    return {"notified": n}


@router.post("/events/{event_id}/performed")
async def performed(event_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    try:
        n = await event_svc.mark_performed(db, ev, staff.id)
    except BookingError as e:
        raise HTTPException(409, e.code) from e
    await db.commit()
    return {"performed": n}


class DisruptIn(BaseModel):
    action: str = Field(pattern="^(reschedule|refund)$")
    new_starts_at: datetime | None = None


@router.post("/events/{event_id}/disrupt")
async def disrupt(event_id: int, body: DisruptIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    new = body.new_starts_at
    if new and new.tzinfo is None:
        new = new.replace(tzinfo=IST)
    try:
        result = await event_svc.disrupt(db, ev, action=body.action, staff_id=staff.id, new_starts_at=new)
    except BookingError as e:
        raise HTTPException(409, e.code) from e
    await notify.commit_and_dispatch(db)
    await revalidate(puja_tags(ev.puja_id))
    return result


# ------------------------------------------------------------------ resumable uploads
class UploadInit(BaseModel):
    filename: str
    size: int = Field(gt=0, le=20 * 1024**3)
    content_type: str


def _meta_path(upload_id: str) -> Path:
    return UPLOAD_DIR / f"{upload_id}.json"


def _part_path(upload_id: str) -> Path:
    return UPLOAD_DIR / f"{upload_id}.part"


@router.post("/uploads", status_code=201)
async def upload_init(body: UploadInit, staff: StaffUser = Depends(require_role(
        StaffRole.ops_coordinator, StaffRole.catalog_editor))):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    upload_id = uuid.uuid4().hex
    _meta_path(upload_id).write_text(json.dumps({**body.model_dump(), "staff_id": staff.id}))
    _part_path(upload_id).touch()
    return {"upload_id": upload_id, "offset": 0, "chunk_size": 8 * 1024 * 1024}


@router.get("/uploads/{upload_id}")
async def upload_status(upload_id: str, _: StaffUser = Depends(require_role(
        StaffRole.ops_coordinator, StaffRole.catalog_editor))):
    if not _meta_path(upload_id).exists():
        raise HTTPException(404, "not_found")
    meta = json.loads(_meta_path(upload_id).read_text())
    return {"upload_id": upload_id, "offset": _part_path(upload_id).stat().st_size, "size": meta["size"]}


@router.put("/uploads/{upload_id}")
async def upload_chunk(upload_id: str, request: Request, offset: int = Query(ge=0),
                       _: StaffUser = Depends(require_role(StaffRole.ops_coordinator, StaffRole.catalog_editor))):
    part = _part_path(upload_id)
    if not part.exists():
        raise HTTPException(404, "not_found")
    current = part.stat().st_size
    if offset != current:
        raise HTTPException(409, {"code": "offset_mismatch", "offset": current})
    with part.open("ab") as f:
        async for chunk in request.stream():
            f.write(chunk)
    return {"offset": part.stat().st_size}


class UploadComplete(BaseModel):
    purpose: str = Field(pattern="^(sankalp_video|full_video|event_photo|image|clips_bulk)$")
    event_id: int | None = None
    temple_id: int | None = None
    taken_on: date | None = None
    alt: dict[str, str] = Field(default_factory=dict)
    in_gallery: bool = False


@router.post("/uploads/{upload_id}/complete")
async def upload_complete(upload_id: str, body: UploadComplete, db: AsyncSession = Depends(get_db),
                          staff: StaffUser = Depends(require_role(StaffRole.ops_coordinator,
                                                                  StaffRole.catalog_editor))):
    meta_p, part = _meta_path(upload_id), _part_path(upload_id)
    if not meta_p.exists():
        raise HTTPException(404, "not_found")
    meta = json.loads(meta_p.read_text())
    if part.stat().st_size != meta["size"]:
        raise HTTPException(409, {"code": "incomplete", "offset": part.stat().st_size})
    ext = Path(meta["filename"]).suffix.lower() or ".bin"
    ev = await db.get(PujaEvent, body.event_id) if body.event_id else None
    result: dict = {}

    if body.purpose in ("sankalp_video", "full_video"):
        if ev is None:
            raise HTTPException(400, "event_required")
        key = f"events/{ev.id}/{body.purpose}-{upload_id[:8]}{ext}"
        put_file(part, key, meta["content_type"])
        if body.purpose == "sankalp_video":
            ev.sankalp_video_key = key
            ev.sankalp_video_stream_id = await ingest(key)
        else:
            ev.full_video_stream_id = await ingest(key)
        result = {"key": key}
    elif body.purpose in ("event_photo", "image"):
        if body.purpose == "event_photo" and ev is None:
            raise HTTPException(400, "event_required")
        temple_id = body.temple_id or (ev.puja.temple_id if ev else None)
        taken_on = body.taken_on or (ev.starts_at.astimezone(IST).date() if ev else None)
        if body.in_gallery and (temple_id is None or taken_on is None):
            raise HTTPException(400, "gallery_requires_temple_and_date")
        if not any((v or "").strip() for v in body.alt.values()):
            raise HTTPException(400, "alt_text_required")
        base = f"images/{upload_id}"
        processed = process_image(part, base)
        asset = MediaAsset(key=processed["key"], kind="image", temple_id=temple_id,
                           puja_event_id=ev.id if ev else None, taken_on=taken_on, alt=body.alt,
                           width=processed["width"], height=processed["height"], in_gallery=body.in_gallery)
        db.add(asset)
        if ev is not None:
            ev.photos = [*(ev.photos or []), {"key": processed["key"], "alt": body.alt,
                                              "taken_on": taken_on.isoformat() if taken_on else None}]
        result = {"key": processed["key"], "url": public_url(processed["key"]), "width": processed["width"],
                  "height": processed["height"]}
    elif body.purpose == "clips_bulk":
        if ev is None:
            raise HTTPException(400, "event_required")
        # A single bulk upload carries one clip named {booking_code}.mp4.
        tmp = UPLOAD_DIR / meta["filename"]
        shutil.copyfile(part, tmp)
        result = await proof_svc.bulk_match(db, ev, [(meta["filename"], tmp)], staff.id)
    await audit(db, staff.id, f"upload.{body.purpose}", "upload", upload_id,
                {"filename": meta["filename"], "event_id": body.event_id})
    await db.commit()
    meta_p.unlink(missing_ok=True)
    part.unlink(missing_ok=True)
    return result


# ------------------------------------------------------------------ marker tool + QC
@router.get("/events/{event_id}/clips")
async def clips(event_id: int, db: AsyncSession = Depends(get_db), _: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    rows = (await db.execute(select(ProofClip, Booking).join(Booking, ProofClip.booking_id == Booking.id)
                             .where(ProofClip.puja_event_id == ev.id).order_by(ProofClip.start_ms))).all()
    items = [{"id": str(c.id), "booking_id": str(b.id), "code": b.code, "position": b.sheet_position,
              "start_ms": c.start_ms, "end_ms": c.end_ms, "url": public_url(c.r2_key),
              "poster": public_url(c.thumb_key), "size_bytes": c.size_bytes, "qc_status": c.qc_status.value,
              "booking_status": b.status.value,
              "short": c.end_ms is not None and c.end_ms - c.start_ms < proof_svc.SHORT_CLIP_MS} for c, b in rows]
    pending = [c for c, _ in rows if c.qc_status.value == "pending" and c.r2_key]
    need, short = proof_svc.required_sample(pending) if pending else (0, set())
    return {"sankalp_video_url": public_url(ev.sankalp_video_key), "clips": items,
            "qc": {"required_sample": need, "short_clip_ids": [str(x) for x in short]}}


class MarkersIn(BaseModel):
    markers: list[dict]


@router.put("/events/{event_id}/markers")
async def markers(event_id: int, body: MarkersIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    try:
        n = await proof_svc.save_markers(db, ev, body.markers, staff.id)
    except proof_svc.ProofError as e:
        raise HTTPException(409, e.code) from e
    await db.commit()
    return {"saved": n}


@router.post("/events/{event_id}/cut-clips")
async def cut_clips(event_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None or not ev.sankalp_video_key:
        raise HTTPException(409, "no_sankalp_video")
    await audit(db, staff.id, "proof.cut_requested", "puja_event", ev.id)
    await db.commit()
    await enqueue("cut_clips", event_id, _job_id=f"cut:{event_id}:{int(utcnow().timestamp())}")
    return {"queued": True}


class QcIn(BaseModel):
    reviewed_ids: list[str]
    rejected_ids: list[str] = Field(default_factory=list)


@router.post("/events/{event_id}/qc-approve")
async def qc_approve(event_id: int, body: QcIn, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    try:
        result = await proof_svc.approve_batch(db, ev, body.reviewed_ids, body.rejected_ids, staff.id)
    except proof_svc.ProofError as e:
        raise HTTPException(409, {"code": e.code, "detail": str(e)}) from e
    await notify.commit_and_dispatch(db)
    return result


# ------------------------------------------------------------------ SLA board
@router.get("/sla")
async def sla_board(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(require_role(
        StaffRole.ops_coordinator, StaffRole.support_agent))):
    return await sla.board(db)


class EscalateIn(BaseModel):
    note: str = Field(min_length=2, max_length=500)


@router.post("/sla/{event_id}/escalate")
async def escalate(event_id: int, body: EscalateIn, db: AsyncSession = Depends(get_db),
                   staff: StaffUser = Depends(ops)):
    from services.alerts import ops_alert

    ev = await db.get(PujaEvent, event_id)
    if ev is None:
        raise HTTPException(404, "not_found")
    await ops_alert("SLA escalation", f"Event {event_id} ({await puja_title(db, ev.puja_id, 'en')}): {body.note} "
                    f"— escalated by {staff.name}", event_id=event_id)
    await audit(db, staff.id, "sla.escalate", "puja_event", event_id, body.model_dump())
    await db.commit()
    return {"ok": True}


# ------------------------------------------------------------------ shipping
@router.get("/shipping")
async def shipments(event_id: int | None = None, status: str | None = None, db: AsyncSession = Depends(get_db),
                    _: StaffUser = Depends(ops)):
    stmt = (select(Shipment, Booking).join(Booking, Shipment.booking_id == Booking.id)
            .where(Booking.status.not_in([S.draft, S.pending_payment, S.cancelled, S.refunded])))
    if event_id:
        stmt = stmt.where(Booking.puja_event_id == event_id)
    if status:
        stmt = stmt.where(Shipment.status == status)
    rows = (await db.execute(stmt.order_by(Booking.created_at.desc()).limit(500))).all()
    return [{"id": str(s.id), "booking_id": str(b.id), "code": b.code, "event_id": b.puja_event_id,
             "status": s.status.value, "awb": s.awb, "courier": s.courier, "tracking_url": s.tracking_url,
             "label_url": s.label_url, "address": s.address, "events": s.events} for s, b in rows]


@router.post("/shipping/events/{event_id}/bulk-create")
async def bulk_create(event_id: int, db: AsyncSession = Depends(get_db), staff: StaffUser = Depends(ops)):
    result = await shipping_svc.bulk_create(db, event_id, staff.id)
    await db.commit()
    return result


# ------------------------------------------------------------------ media library
@router.get("/media")
async def media(db: AsyncSession = Depends(get_db), _: StaffUser = Depends(require_role(
        StaffRole.catalog_editor, StaffRole.ops_coordinator))):
    rows = (await db.execute(select(MediaAsset).order_by(MediaAsset.created_at.desc()).limit(300))).scalars()
    return [{"id": m.id, "key": m.key, "url": public_url(m.key), "kind": m.kind, "temple_id": m.temple_id,
             "event_id": m.puja_event_id, "taken_on": m.taken_on.isoformat() if m.taken_on else None, "alt": m.alt,
             "in_gallery": m.in_gallery} for m in rows]


class MediaPatch(BaseModel):
    in_gallery: bool | None = None
    alt: dict[str, str] | None = None


@router.patch("/media/{media_id}")
async def media_patch(media_id: int, body: MediaPatch, db: AsyncSession = Depends(get_db),
                      staff: StaffUser = Depends(require_role(StaffRole.catalog_editor))):
    m = await db.get(MediaAsset, media_id)
    if m is None:
        raise HTTPException(404, "not_found")
    if body.in_gallery and (m.temple_id is None or m.taken_on is None):
        raise HTTPException(400, "gallery_requires_temple_and_date")
    if body.in_gallery is not None:
        m.in_gallery = body.in_gallery
    if body.alt is not None:
        m.alt = body.alt
    await audit(db, staff.id, "media.update", "media_asset", m.id, body.model_dump(exclude_none=True))
    await db.commit()
    await revalidate(["home"])
    return {"ok": True}
