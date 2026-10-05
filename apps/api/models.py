"""Data model — PRD section 9 is the source of truth.

Tables/columns not listed in the PRD are marked `# ext:` with the feature that needs them.
"""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def created_at() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def pg_enum(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, values_callable=lambda e: [m.value for m in e])


# ---------------------------------------------------------------- enums
class StaffRole(enum.StrEnum):
    admin = "admin"
    catalog_editor = "catalog_editor"
    ops_coordinator = "ops_coordinator"
    support_agent = "support_agent"
    finance = "finance"


class VenueType(enum.StrEnum):
    temple = "temple"
    yagashala = "yagashala"
    ghat = "ghat"
    kund = "kund"


class PujaKind(enum.StrEnum):
    one_time = "one_time"
    seva = "seva"
    chadhava = "chadhava"


class PublishStatus(enum.StrEnum):
    draft = "draft"
    published = "published"
    archived = "archived"


class PackageCode(enum.StrEnum):
    individual = "individual"
    couple = "couple"
    family = "family"


class EventStatus(enum.StrEnum):
    scheduled = "scheduled"
    started = "started"
    performed = "performed"
    disrupted = "disrupted"
    cancelled = "cancelled"


class BookingStatus(enum.StrEnum):
    draft = "draft"
    pending_payment = "pending_payment"
    confirmed = "confirmed"
    locked = "locked"
    performed = "performed"
    proof_ready = "proof_ready"
    proof_sent = "proof_sent"
    completed = "completed"
    cancelled = "cancelled"
    refunded = "refunded"
    rescheduled = "rescheduled"


class PaymentMode(enum.StrEnum):
    full = "full"
    autopay = "autopay"


class SubscriptionStatus(enum.StrEnum):
    active = "active"
    cancelled = "cancelled"
    completed = "completed"
    mandate_failed = "mandate_failed"


class QcStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ShipmentStatus(enum.StrEnum):
    pending = "pending"
    packed = "packed"
    shipped = "shipped"
    out_for_delivery = "out_for_delivery"
    delivered = "delivered"
    returned = "returned"


class MessageStatus(enum.StrEnum):
    queued = "queued"
    sent = "sent"
    delivered = "delivered"
    read = "read"
    failed = "failed"


class ReviewStatus(enum.StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


# ---------------------------------------------------------------- people
class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = uuid_pk()
    phone_e164: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(120))
    email: Mapped[str | None] = mapped_column(String(200))
    locale: Mapped[str] = mapped_column(String(2), default="en", nullable=False)
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    marketing_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deletion_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ext: account delete flow
    timezone: Mapped[str | None] = mapped_column(String(64))  # ext: quiet hours / local time
    created_at: Mapped[datetime] = created_at()


class FamilyMember(Base):
    __tablename__ = "family_members"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    relation: Mapped[str | None] = mapped_column(String(60))
    gotra: Mapped[str | None] = mapped_column(String(80))
    nakshatra: Mapped[str | None] = mapped_column(String(40))


class StaffUser(Base):
    __tablename__ = "staff_users"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[StaffRole] = mapped_column(pg_enum(StaffRole, "staff_role"))
    totp_secret: Mapped[str | None] = mapped_column(String(64))
    totp_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # ext: 2FA enrolment
    password_hash: Mapped[str] = mapped_column(String(200))  # ext: PRD says email + password + TOTP
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class OtpCode(Base):  # ext: OTP login + 5/hour rate limit
    __tablename__ = "otp_codes"
    id: Mapped[uuid.UUID] = uuid_pk()
    phone_e164: Mapped[str] = mapped_column(String(20), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(10))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()


# ---------------------------------------------------------------- catalog
class Temple(Base):
    __tablename__ = "temples"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(80))
    lat: Mapped[float | None]
    lng: Mapped[float | None]
    presiding_deity: Mapped[str] = mapped_column(String(120))
    venue_type: Mapped[VenueType] = mapped_column(pg_enum(VenueType, "venue_type"))
    photos: Mapped[list] = mapped_column(JSONB, default=list)  # [{key, alt:{locale:..}, taken_on}]
    translations: Mapped[list["TempleTranslation"]] = relationship(
        back_populates="temple", lazy="selectin", cascade="all, delete-orphan"
    )


class TempleTranslation(Base):
    __tablename__ = "temple_translations"
    __table_args__ = (PrimaryKeyConstraint("temple_id", "locale"),)
    temple_id: Mapped[int] = mapped_column(ForeignKey("temples.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(2))
    name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    history_md: Mapped[str | None] = mapped_column(Text)
    temple: Mapped[Temple] = relationship(back_populates="translations")


class Puja(Base):
    __tablename__ = "pujas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    temple_id: Mapped[int] = mapped_column(ForeignKey("temples.id"), index=True)
    slug: Mapped[str] = mapped_column(String(160))  # ext: /{id}-{slug} URLs
    kind: Mapped[PujaKind] = mapped_column(pg_enum(PujaKind, "puja_kind"))
    deity_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    dosha_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    benefit_tags: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    tradition: Mapped[str] = mapped_column(String(120), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    priests_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sankalp_language: Mapped[str] = mapped_column(String(40), nullable=False)
    requires_nakshatra: Mapped[bool] = mapped_column(Boolean, default=False)
    video_sla_hours: Mapped[int | None] = mapped_column(Integer)
    deliverables: Mapped[list] = mapped_column(JSONB, nullable=False)
    prasad_box: Mapped[list | None] = mapped_column(JSONB)
    images: Mapped[list] = mapped_column(JSONB, default=list)  # ext: gallery [{key, alt:{locale}}]
    status: Mapped[PublishStatus] = mapped_column(pg_enum(PublishStatus, "publish_status"), default=PublishStatus.draft)
    created_at: Mapped[datetime] = created_at()
    temple: Mapped[Temple] = relationship(lazy="selectin")
    translations: Mapped[list["PujaTranslation"]] = relationship(
        back_populates="puja", lazy="selectin", cascade="all, delete-orphan"
    )
    packages: Mapped[list["Package"]] = relationship(lazy="selectin", order_by="Package.max_names")


class PujaTranslation(Base):
    __tablename__ = "puja_translations"
    __table_args__ = (PrimaryKeyConstraint("puja_id", "locale"),)
    puja_id: Mapped[int] = mapped_column(ForeignKey("pujas.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(2))
    title: Mapped[str] = mapped_column(String(200))
    subtitle: Mapped[str | None] = mapped_column(String(300))
    occasion_chip: Mapped[str | None] = mapped_column(String(80))
    about_md: Mapped[str | None] = mapped_column(Text)
    benefits: Mapped[list] = mapped_column(JSONB, default=list)  # [{title, line}]
    rituals: Mapped[list] = mapped_column(JSONB, default=list)  # [{title, text, main}]
    faqs: Mapped[list] = mapped_column(JSONB, default=list)  # [{q, a}]
    meta_title: Mapped[str | None] = mapped_column(String(200))
    meta_description: Mapped[str | None] = mapped_column(String(320))
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    puja: Mapped[Puja] = relationship(back_populates="translations")


class Package(Base):
    __tablename__ = "packages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    puja_id: Mapped[int] = mapped_column(ForeignKey("pujas.id", ondelete="CASCADE"), index=True)
    code: Mapped[PackageCode] = mapped_column(pg_enum(PackageCode, "package_code"))
    max_names: Mapped[int] = mapped_column(Integer)
    price_inr_minor: Mapped[int] = mapped_column(Integer)
    price_usd_minor: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class AddonItem(Base):
    __tablename__ = "addon_items"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    puja_id: Mapped[int | None] = mapped_column(ForeignKey("pujas.id", ondelete="CASCADE"), index=True)
    image_key: Mapped[str | None] = mapped_column(String(300))
    price_inr_minor: Mapped[int] = mapped_column(Integer)
    price_usd_minor: Mapped[int] = mapped_column(Integer)
    max_qty: Mapped[int] = mapped_column(Integer, default=1)
    ships_home: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    translations: Mapped[list["AddonItemTranslation"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class AddonItemTranslation(Base):
    __tablename__ = "addon_item_translations"
    __table_args__ = (PrimaryKeyConstraint("addon_item_id", "locale"),)
    addon_item_id: Mapped[int] = mapped_column(ForeignKey("addon_items.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(2))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)


class SevaPlan(Base):
    __tablename__ = "seva_plans"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    puja_id: Mapped[int] = mapped_column(ForeignKey("pujas.id", ondelete="CASCADE"), unique=True)
    rrule: Mapped[str] = mapped_column(Text)
    occurrences: Mapped[int] = mapped_column(Integer)
    autopay_allowed: Mapped[bool] = mapped_column(Boolean, default=True)


class PujaEvent(Base):
    __tablename__ = "puja_events"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    puja_id: Mapped[int] = mapped_column(ForeignKey("pujas.id", ondelete="CASCADE"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    booking_cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    video_sla_hours: Mapped[int] = mapped_column(Integer)
    status: Mapped[EventStatus] = mapped_column(pg_enum(EventStatus, "event_status"), default=EventStatus.scheduled)
    sankalp_sheet_key: Mapped[str | None] = mapped_column(String(300))
    sankalp_video_stream_id: Mapped[str | None] = mapped_column(String(300))
    full_video_stream_id: Mapped[str | None] = mapped_column(String(300))
    sankalp_video_key: Mapped[str | None] = mapped_column(String(300))  # ext: source file in R2 for clipping
    photos: Mapped[list] = mapped_column(JSONB, default=list)  # ext: real event photos for proof + gallery
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ext: cutoff job ran
    disrupted_action: Mapped[str | None] = mapped_column(String(20))  # ext: reschedule | refund
    rescheduled_to_event_id: Mapped[int | None] = mapped_column(ForeignKey("puja_events.id"))  # ext
    puja: Mapped[Puja] = relationship(lazy="selectin")


class FaqEntry(Base):  # ext: "8 questions per locale from the CMS"
    __tablename__ = "faq_entries"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    locale: Mapped[str] = mapped_column(String(2), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    question: Mapped[str] = mapped_column(Text)
    answer_md: Mapped[str] = mapped_column(Text)


class MediaAsset(Base):  # ext: media library; images need temple + date taken
    __tablename__ = "media_assets"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(300), unique=True)
    kind: Mapped[str] = mapped_column(String(20))  # image | video
    temple_id: Mapped[int | None] = mapped_column(ForeignKey("temples.id"))
    puja_event_id: Mapped[int | None] = mapped_column(ForeignKey("puja_events.id"))
    taken_on: Mapped[date | None] = mapped_column(Date)
    alt: Mapped[dict] = mapped_column(JSONB, default=dict)
    width: Mapped[int | None]
    height: Mapped[int | None]
    in_gallery: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at()


# ---------------------------------------------------------------- bookings
class Booking(Base):
    __tablename__ = "bookings"
    id: Mapped[uuid.UUID] = uuid_pk()
    code: Mapped[str] = mapped_column(String(12), unique=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), index=True)
    puja_event_id: Mapped[int] = mapped_column(ForeignKey("puja_events.id"), index=True)
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id"))
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    locale: Mapped[str] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3))
    subtotal_minor: Mapped[int] = mapped_column(Integer, default=0)
    addons_minor: Mapped[int] = mapped_column(Integer, default=0)
    shipping_minor: Mapped[int] = mapped_column(Integer, default=0)
    dakshina_minor: Mapped[int] = mapped_column(Integer, default=0)  # ext: optional dakshina chips
    tax_minor: Mapped[int] = mapped_column(Integer, default=0)
    total_minor: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[BookingStatus] = mapped_column(pg_enum(BookingStatus, "booking_status"), index=True)
    whatsapp_e164: Mapped[str | None] = mapped_column(String(20))
    wish: Mapped[str | None] = mapped_column(String(140))
    consent_whatsapp_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consent_text_version: Mapped[str | None] = mapped_column(String(20))
    consent_marketing_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ext
    proof_token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = created_at()
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # ext columns below
    cancel_reason: Mapped[str | None] = mapped_column(String(60))
    payment_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    performed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    proof_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sla_breach_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reschedule_from_event_id: Mapped[int | None] = mapped_column(ForeignKey("puja_events.id"))
    reschedule_deadline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    needs_call_reason: Mapped[str | None] = mapped_column(String(120))  # ops call queue
    assisted_by_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    sheet_position: Mapped[int | None] = mapped_column(Integer)

    names: Mapped[list["BookingName"]] = relationship(
        lazy="selectin", order_by="BookingName.position", cascade="all, delete-orphan"
    )
    addons: Mapped[list["BookingAddon"]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    event: Mapped[PujaEvent] = relationship(lazy="selectin", foreign_keys=[puja_event_id])
    package: Mapped[Package] = relationship(lazy="selectin")


class BookingName(Base):
    __tablename__ = "booking_names"
    id: Mapped[uuid.UUID] = uuid_pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    relation: Mapped[str | None] = mapped_column(String(60))
    gotra: Mapped[str | None] = mapped_column(String(80))
    gotra_unknown: Mapped[bool] = mapped_column(Boolean, default=False)
    nakshatra: Mapped[str | None] = mapped_column(String(40))


class BookingAddon(Base):
    __tablename__ = "booking_addons"
    __table_args__ = (PrimaryKeyConstraint("booking_id", "addon_item_id"),)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"))
    addon_item_id: Mapped[int] = mapped_column(ForeignKey("addon_items.id"))
    qty: Mapped[int] = mapped_column(Integer)
    unit_price_minor: Mapped[int] = mapped_column(Integer)
    item: Mapped[AddonItem] = relationship(lazy="selectin")


class BookingNote(Base):  # ext: admin "add a note"
    __tablename__ = "booking_notes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), index=True)
    staff_id: Mapped[int] = mapped_column(ForeignKey("staff_users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at()


class Subscription(Base):
    __tablename__ = "subscriptions"
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    seva_plan_id: Mapped[int] = mapped_column(ForeignKey("seva_plans.id"))
    package_id: Mapped[int] = mapped_column(ForeignKey("packages.id"))
    payment_mode: Mapped[PaymentMode] = mapped_column(pg_enum(PaymentMode, "payment_mode"))
    mandate_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("mandates.id", use_alter=True, name="fk_subscriptions_mandate")
    )
    status: Mapped[SubscriptionStatus] = mapped_column(pg_enum(SubscriptionStatus, "subscription_status"))
    next_occurrence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()  # ext
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ext


class WishlistItem(Base):  # ext: wishlist sync on login
    __tablename__ = "wishlist_items"
    __table_args__ = (PrimaryKeyConstraint("user_id", "puja_id"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    puja_id: Mapped[int] = mapped_column(ForeignKey("pujas.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = created_at()


class CallbackRequest(Base):  # ext: "Call to book" outside staffed hours
    __tablename__ = "callback_requests"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    phone_e164: Mapped[str] = mapped_column(String(20))
    name: Mapped[str | None] = mapped_column(String(120))
    puja_id: Mapped[int | None] = mapped_column(ForeignKey("pujas.id"))
    locale: Mapped[str] = mapped_column(String(2))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = created_at()


# ---------------------------------------------------------------- money
class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = uuid_pk()
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"), index=True)
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_order_id: Mapped[str | None] = mapped_column(String(100), index=True)
    provider_payment_id: Mapped[str | None] = mapped_column(String(100), index=True)
    amount_minor: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20))  # created | captured | failed
    raw: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()  # ext
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # ext: reconciliation


class Mandate(Base):
    __tablename__ = "mandates"
    id: Mapped[uuid.UUID] = uuid_pk()
    subscription_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    token: Mapped[str | None] = mapped_column(String(120))
    max_amount_minor: Mapped[int] = mapped_column(Integer)
    frequency: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))  # created | active | cancelled | failed


class Refund(Base):
    __tablename__ = "refunds"
    id: Mapped[uuid.UUID] = uuid_pk()
    payment_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("payments.id"), index=True)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id"), index=True)  # ext
    amount_minor: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(120))
    provider_refund_id: Mapped[str | None] = mapped_column(String(100), index=True)
    status: Mapped[str] = mapped_column(String(20))  # requested | processed | failed
    created_at: Mapped[datetime] = created_at()  # ext


class ReconciliationItem(Base):  # ext: finance mismatch view
    __tablename__ = "reconciliation_items"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_date: Mapped[date] = mapped_column(Date, index=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str | None] = mapped_column(String(100))
    payment_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("payments.id"))
    kind: Mapped[str] = mapped_column(String(40))  # missing_in_db | amount_mismatch | not_settled
    detail: Mapped[dict] = mapped_column(JSONB, default=dict)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


# ---------------------------------------------------------------- fulfilment
class ProofClip(Base):
    __tablename__ = "proof_clips"
    id: Mapped[uuid.UUID] = uuid_pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), unique=True)
    puja_event_id: Mapped[int] = mapped_column(ForeignKey("puja_events.id"), index=True)
    start_ms: Mapped[int] = mapped_column(Integer)
    end_ms: Mapped[int | None] = mapped_column(Integer)
    stream_id: Mapped[str | None] = mapped_column(String(300))
    r2_key: Mapped[str | None] = mapped_column(String(300))
    thumb_key: Mapped[str | None] = mapped_column(String(300))  # ext: header fallback image
    size_bytes: Mapped[int | None] = mapped_column(BigInteger)
    qc_status: Mapped[QcStatus] = mapped_column(pg_enum(QcStatus, "qc_status"), default=QcStatus.pending)
    sent_inline: Mapped[bool] = mapped_column(Boolean, default=False)


class Shipment(Base):
    __tablename__ = "shipments"
    id: Mapped[uuid.UUID] = uuid_pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), unique=True)
    address: Mapped[dict] = mapped_column(JSONB)
    provider: Mapped[str | None] = mapped_column(String(20))
    provider_order_id: Mapped[str | None] = mapped_column(String(100))
    awb: Mapped[str | None] = mapped_column(String(60), index=True)
    courier: Mapped[str | None] = mapped_column(String(80))
    tracking_url: Mapped[str | None] = mapped_column(String(300))
    label_url: Mapped[str | None] = mapped_column(String(300))  # ext: printed labels
    status: Mapped[ShipmentStatus] = mapped_column(pg_enum(ShipmentStatus, "shipment_status"))
    events: Mapped[list] = mapped_column(JSONB, default=list)


# ---------------------------------------------------------------- messaging
class MessageTemplate(Base):
    __tablename__ = "message_templates"
    __table_args__ = (PrimaryKeyConstraint("key", "locale", "provider"),)
    key: Mapped[str] = mapped_column(String(60))
    locale: Mapped[str] = mapped_column(String(2))
    category: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20))
    provider_template_ref: Mapped[str] = mapped_column(String(120))
    variables: Mapped[list[str]] = mapped_column(ARRAY(Text))
    status: Mapped[str] = mapped_column(String(20))  # approved | pending | rejected
    body: Mapped[str | None] = mapped_column(Text)  # ext: copy for preview + fake provider


class MessageLog(Base):
    __tablename__ = "message_log"
    __table_args__ = (
        UniqueConstraint("booking_id", "template_key", "occurrence_key", name="uq_message_log_booking_tpl_occ"),
        Index("ix_message_log_due", "status", "scheduled_for"),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    template_key: Mapped[str] = mapped_column(String(60))
    occurrence_key: Mapped[str] = mapped_column(String(80), default="")
    to_e164: Mapped[str] = mapped_column(String(20))
    provider: Mapped[str] = mapped_column(String(20))
    provider_message_id: Mapped[str | None] = mapped_column(String(120), index=True)
    status: Mapped[MessageStatus] = mapped_column(pg_enum(MessageStatus, "message_status"))
    error_code: Mapped[str | None] = mapped_column(String(60))
    created_at: Mapped[datetime] = created_at()
    # ext columns below
    locale: Mapped[str] = mapped_column(String(2), default="en")
    params: Mapped[list] = mapped_column(JSONB, default=list)
    button_params: Mapped[list | None] = mapped_column(JSONB)
    header_media_url: Mapped[str | None] = mapped_column(String(500))
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    campaign_id: Mapped[int | None] = mapped_column(ForeignKey("campaigns.id"))


class InboundMessage(Base):
    __tablename__ = "inbound_messages"
    id: Mapped[uuid.UUID] = uuid_pk()
    from_e164: Mapped[str] = mapped_column(String(20), index=True)
    text: Mapped[str | None] = mapped_column(Text)
    button_payload: Mapped[str | None] = mapped_column(String(200))
    matched_booking_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("bookings.id", ondelete="SET NULL"))
    received_at: Mapped[datetime] = created_at()


class Campaign(Base):  # ext: marketing campaigns from admin
    __tablename__ = "campaigns"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    template_key: Mapped[str] = mapped_column(String(60))
    locale: Mapped[str] = mapped_column(String(2))
    interest_tag: Mapped[str | None] = mapped_column(String(60))
    params: Mapped[list] = mapped_column(JSONB, default=list)
    puja_id: Mapped[int | None] = mapped_column(ForeignKey("pujas.id"))
    created_by: Mapped[int] = mapped_column(ForeignKey("staff_users.id"))
    recipients: Mapped[int] = mapped_column(Integer, default=0)
    skipped_cap: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = created_at()


# ---------------------------------------------------------------- trust, config, audit
class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[uuid.UUID] = uuid_pk()
    booking_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bookings.id", ondelete="CASCADE"), unique=True)
    rating: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(2))
    status: Mapped[ReviewStatus] = mapped_column(pg_enum(ReviewStatus, "review_status"), default=ReviewStatus.pending)
    created_at: Mapped[datetime] = created_at()  # ext


class SiteConfig(Base):
    __tablename__ = "site_config"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict | list | str | int | None] = mapped_column(JSONB)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"
    id: Mapped[uuid.UUID] = uuid_pk()
    provider: Mapped[str] = mapped_column(String(30))
    event_type: Mapped[str] = mapped_column(String(80))
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True)
    payload: Mapped[dict] = mapped_column(JSONB)
    received_at: Mapped[datetime] = created_at()
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_staff_id: Mapped[int | None] = mapped_column(ForeignKey("staff_users.id"))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str] = mapped_column(String(80))
    diff: Mapped[dict | None] = mapped_column(JSONB)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class FakeProviderCall(Base):  # PRD §3: fake adapters record calls to a table
    __tablename__ = "fake_provider_calls"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(20))  # messaging | payments | shipping | sms
    method: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = created_at()
