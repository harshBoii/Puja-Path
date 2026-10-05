export type Img = { url: string; alt: string; srcset?: string; taken_on?: string } | null;
export type Money = { INR: number | null; USD: number | null };

export type SiteConfig = {
  brand: string;
  video_sla_hours_default: number;
  booking_cutoff_hours_default: number;
  support_hours: { tz: string; start: string; end: string; days: number[] };
  support_languages: string[];
  support_phone_e164: string;
  whatsapp_number_e164: string;
  gotra_fallback: Record<string, string>;
  proof_refund_after_days: number;
  refund_expected_days: string;
  reschedule_reply_hours: number;
  shipping_fee: Record<string, number>;
  dakshina_options: Record<string, number[]>;
  consent_text_version: string;
  social_links: Record<string, string>;
};

export type TempleSummary = {
  id: number; slug: string; name: string; city: string; state: string; venue_type: string;
  presiding_deity: string; photo: Img;
};

export type EventInfo = { id: number; starts_at: string; booking_cutoff_at: string; video_sla_hours: number; status: string };

export type PujaCardData = {
  id: number; slug: string; kind: "one_time" | "seva" | "chadhava"; title: string; subtitle: string | null;
  occasion_chip: string | null; image: Img; temple: TempleSummary; event: EventInfo | null;
  from_price_minor: number | null; from_prices: Money; currency: string;
  deity_tags: string[]; dosha_tags: string[]; benefit_tags: string[];
};

export type Listing = { items: PujaCardData[]; total: number; offset: number; limit: number };

export type PujaDetail = PujaCardData & {
  about_md: string | null; benefits: { title: string; line: string }[];
  rituals: { title: string; text: string; main?: boolean }[]; faqs: { q: string; a: string }[];
  meta_title: string | null; meta_description: string | null; images: Img[];
  facts: { tradition: string; duration_minutes: number; priests_count: number; sankalp_language: string };
  requires_nakshatra: boolean; video_sla_hours: number; deliverables: string[]; prasad_box: string[] | null;
  packages: { id: number; code: string; label: string; max_names: number; price_minor: number; prices: Money }[];
  addons: { id: number; name: string; description: string | null; image: Img; price_minor: number; prices: Money;
            max_qty: number; ships_home: boolean }[];
  temple_detail: TempleSummary & { history_md: string | null; address: string | null; lat: number | null;
                                   lng: number | null; photos: Img[] };
  available_locales: string[]; upcoming_events: EventInfo[];
  seva?: { rrule: string; occurrences: number; autopay_allowed: boolean; dates: EventInfo[]; bookable: boolean };
  reviews: Review[]; recommendations: PujaCardData[]; global_faqs: { q: string; a: string }[]; preview?: boolean;
};

export type Review = { rating: number; text: string | null; first_name: string; city: string | null; puja: string;
                       puja_id: number; date: string };

export type Home = {
  hero: PujaCardData[]; trust: { items: { key: string; value: number; count?: number }[]; as_of: string };
  video_sla_hours: number; upcoming: PujaCardData[]; upcoming_total: number;
  tags: { deity: string[]; dosha: string[]; benefit: string[] }; sevas: PujaCardData[]; temples: TempleSummary[];
  gallery: { url: string; alt: string; temple: string; taken_on: string }[]; testimonials: Review[];
  faqs: { q: string; a: string }[];
};

export type TempleDetail = TempleSummary & { history_md: string | null; address: string | null; lat: number | null;
  lng: number | null; photos: Img[]; pujas: PujaCardData[]; available_locales: string[] };

export type Proof = { locale: string; code: string; puja: string; temple: string; starts_at: string; names: string[];
  clip: { url: string; poster: string } | null; full_video: { type: "mp4" | "hls"; url: string } | null;
  photos: { url: string; alt: string }[]; puja_id: number };

export type SitemapData = { pujas: { id: number; slug: string; kind: string; locales: string[] }[];
  temples: { id: number; slug: string; locales: string[] }[] };
