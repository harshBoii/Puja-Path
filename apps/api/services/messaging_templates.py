"""WhatsApp templates — PRD §7. Defined once here, mapped per provider in `message_templates`.

Copy is factual about the ritual; no promised outcomes. Bodies use WhatsApp's {{n}} positional syntax.
"""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import MessageTemplate

TEMPLATE_SPECS: dict[str, dict] = {
    "otp_login": {
        "category": "authentication", "variables": ["code"], "buttons": "copy_code",
        "body": {
            "en": "{{1}} is your verification code. Do not share it with anyone.",
            "hi": "{{1}} आपका सत्यापन कोड है। इसे किसी के साथ साझा न करें।",
            "ta": "{{1}} உங்கள் சரிபார்ப்புக் குறியீடு. இதை யாருடனும் பகிர வேண்டாம்.",
            "te": "{{1}} మీ ధృవీకరణ కోడ్. దీన్ని ఎవరితోనూ పంచుకోవద్దు.",
        },
    },
    "booking_confirmed": {
        "category": "utility", "variables": ["name", "puja", "temple", "datetime_ist", "package", "booking_code"],
        "buttons": "url:view_booking",
        "body": {
            "en": "Namaste {{1}}, your booking for {{2}} at {{3}} on {{4}} is confirmed. Package: {{5}}. Booking ID: {{6}}. The sankalp will be taken in the names you gave us.",
            "hi": "नमस्ते {{1}}, {{3}} में {{4}} को होने वाली {{2}} की आपकी बुकिंग की पुष्टि हो गई है। पैकेज: {{5}}। बुकिंग आईडी: {{6}}। संकल्प आपके दिए गए नामों से लिया जाएगा।",
            "ta": "வணக்கம் {{1}}, {{3}} இல் {{4}} அன்று நடைபெறும் {{2}} க்கான உங்கள் முன்பதிவு உறுதி செய்யப்பட்டது. தொகுப்பு: {{5}}. முன்பதிவு எண்: {{6}}. நீங்கள் கொடுத்த பெயர்களில் சங்கல்பம் செய்யப்படும்.",
            "te": "నమస్తే {{1}}, {{3}}లో {{4}}న జరిగే {{2}} కోసం మీ బుకింగ్ నిర్ధారించబడింది. ప్యాకేజీ: {{5}}. బుకింగ్ ఐడి: {{6}}. మీరు ఇచ్చిన పేర్లతో సంకల్పం చేయబడుతుంది.",
        },
    },
    "payment_link": {
        "category": "utility", "variables": ["name", "puja", "amount", "expiry"], "buttons": "url:pay",
        "body": {
            "en": "Namaste {{1}}, here is the payment link for {{2}}. Amount: {{3}}. The link is valid until {{4}}. Thank you.",
            "hi": "नमस्ते {{1}}, {{2}} के लिए भुगतान लिंक यह है। राशि: {{3}}। लिंक {{4}} तक मान्य है।",
            "ta": "வணக்கம் {{1}}, {{2}} க்கான கட்டண இணைப்பு இதோ. தொகை: {{3}}. இந்த இணைப்பு {{4}} வரை செல்லுபடியாகும்.",
            "te": "నమస్తే {{1}}, {{2}} కోసం చెల్లింపు లింక్ ఇదిగో. మొత్తం: {{3}}. ఈ లింక్ {{4}} వరకు చెల్లుతుంది.",
        },
    },
    "puja_reminder": {
        "category": "utility", "variables": ["name", "puja", "temple", "datetime_ist"], "buttons": None,
        "body": {
            "en": "Namaste {{1}}, a reminder that {{2}} at {{3}} is scheduled for {{4}}. The sankalp will include the names in your booking.",
            "hi": "नमस्ते {{1}}, याद दिला दें कि {{3}} में {{2}} {{4}} को निर्धारित है। संकल्प में आपकी बुकिंग के नाम शामिल होंगे।",
            "ta": "வணக்கம் {{1}}, {{3}} இல் {{2}} {{4}} அன்று நடைபெறவுள்ளது என்பதை நினைவூட்டுகிறோம். சங்கல்பத்தில் உங்கள் முன்பதிவில் உள்ள பெயர்கள் சேர்க்கப்படும்.",
            "te": "నమస్తే {{1}}, {{3}}లో {{2}} {{4}}న జరగనుందని గుర్తు చేస్తున్నాము. సంకల్పంలో మీ బుకింగ్‌లోని పేర్లు ఉంటాయి.",
        },
    },
    "puja_started": {
        "category": "utility", "variables": ["puja", "temple"], "buttons": None,
        "body": {
            "en": "Update: {{1}} has begun at {{2}}. The priests are now taking the sankalp.",
            "hi": "सूचना: {{2}} में {{1}} आरंभ हो गई है। पुजारी अब संकल्प ले रहे हैं।",
            "ta": "அறிவிப்பு: {{2}} இல் {{1}} தொடங்கியது. அர்ச்சகர்கள் இப்போது சங்கல்பம் செய்கிறார்கள்.",
            "te": "సమాచారం: {{2}}లో {{1}} ప్రారంభమైంది. పూజారులు ఇప్పుడు సంకల్పం చేస్తున్నారు.",
        },
    },
    "proof_video": {
        "category": "utility", "variables": ["name", "puja", "temple", "date"], "buttons": "url:proof",
        "header": "video",
        "body": {
            "en": "Namaste {{1}}, {{2}} at {{3}} was performed on {{4}}. Your sankalp clip is above. Tap below for the full ritual video and photos.",
            "hi": "नमस्ते {{1}}, {{3}} में {{2}} {{4}} को संपन्न हुई। आपका संकल्प क्लिप ऊपर है। पूरे अनुष्ठान का वीडियो और फ़ोटो देखने के लिए नीचे टैप करें।",
            "ta": "வணக்கம் {{1}}, {{3}} இல் {{2}} {{4}} அன்று நடைபெற்றது. உங்கள் சங்கல்பக் காணொளி மேலே உள்ளது. முழு சடங்குக் காணொளி மற்றும் புகைப்படங்களுக்குக் கீழே தட்டவும்.",
            "te": "నమస్తే {{1}}, {{3}}లో {{2}} {{4}}న నిర్వహించబడింది. మీ సంకల్ప క్లిప్ పైన ఉంది. పూర్తి పూజ వీడియో మరియు ఫోటోల కోసం క్రింద నొక్కండి.",
        },
    },
    "proof_delayed": {
        "category": "utility", "variables": ["puja", "new_eta"], "buttons": None,
        "body": {
            "en": "We are sorry: the video for {{1}} is taking longer than promised. We now expect to send it by {{2}}. Thank you.",
            "hi": "क्षमा करें: {{1}} का वीडियो वादे से अधिक समय ले रहा है। अब हम इसे {{2}} तक भेजने की उम्मीद करते हैं।",
            "ta": "மன்னிக்கவும்: {{1}} இன் காணொளி உறுதியளித்ததை விட தாமதமாகிறது. {{2}} க்குள் அனுப்புவோம் என எதிர்பார்க்கிறோம்.",
            "te": "క్షమించండి: {{1}} వీడియో చెప్పిన సమయం కంటే ఆలస్యమవుతోంది. {{2}} లోపు పంపుతామని ఆశిస్తున్నాము.",
        },
    },
    "prasad_shipped": {
        "category": "utility", "variables": ["puja", "courier", "awb"], "buttons": "url:track",
        "body": {
            "en": "The prasad from {{1}} has been shipped with {{2}}. Tracking number: {{3}}. Thank you.",
            "hi": "सूचना: {{1}} का प्रसाद {{2}} से भेज दिया गया है। ट्रैकिंग नंबर: {{3}}। धन्यवाद।",
            "ta": "அறிவிப்பு: {{1}} இன் பிரசாதம் {{2}} மூலம் அனுப்பப்பட்டது. கண்காணிப்பு எண்: {{3}}. நன்றி.",
            "te": "సమాచారం: {{1}} ప్రసాదం {{2}} ద్వారా పంపబడింది. ట్రాకింగ్ నంబర్: {{3}}. ధన్యవాదాలు.",
        },
    },
    "prasad_out_for_delivery": {
        "category": "utility", "variables": ["courier", "awb"], "buttons": "url:track",
        "body": {
            "en": "Your prasad is out for delivery today with {{1}}. Tracking number: {{2}}. Thank you.",
            "hi": "आपका प्रसाद आज {{1}} द्वारा डिलीवरी के लिए निकला है। ट्रैकिंग नंबर: {{2}}। धन्यवाद।",
            "ta": "உங்கள் பிரசாதம் இன்று {{1}} மூலம் டெலிவரிக்கு வெளியே உள்ளது. கண்காணிப்பு எண்: {{2}}. நன்றி.",
            "te": "మీ ప్రసాదం ఈరోజు {{1}} ద్వారా డెలివరీకి బయలుదేరింది. ట్రాకింగ్ నంబర్: {{2}}. ధన్యవాదాలు.",
        },
    },
    "prasad_delivered": {
        "category": "utility", "variables": ["puja"], "buttons": None,
        "body": {
            "en": "The prasad from {{1}} has been delivered.",
            "hi": "सूचना: {{1}} का प्रसाद पहुँचा दिया गया है।",
            "ta": "அறிவிப்பு: {{1}} இன் பிரசாதம் வழங்கப்பட்டது.",
            "te": "సమాచారం: {{1}} ప్రసాదం అందజేయబడింది.",
        },
    },
    "booking_cancelled": {
        "category": "utility", "variables": ["puja", "booking_code", "refund_amount"], "buttons": None,
        "body": {
            "en": "Your booking {{2}} for {{1}} has been cancelled. Refund amount: {{3}}. Thank you.",
            "hi": "सूचना: {{1}} के लिए आपकी बुकिंग {{2}} रद्द कर दी गई है। रिफ़ंड राशि: {{3}}। धन्यवाद।",
            "ta": "அறிவிப்பு: {{1}} க்கான உங்கள் முன்பதிவு {{2}} ரத்து செய்யப்பட்டது. திருப்பித் தரப்படும் தொகை: {{3}}. நன்றி.",
            "te": "సమాచారం: {{1}} కోసం మీ బుకింగ్ {{2}} రద్దు చేయబడింది. రీఫండ్ మొత్తం: {{3}}. ధన్యవాదాలు.",
        },
    },
    "refund_processed": {
        "category": "utility", "variables": ["amount", "reference", "expected_days"], "buttons": None,
        "body": {
            "en": "A refund of {{1}} has been processed to your original payment method. Reference: {{2}}. It usually reaches you in {{3}} working days.",
            "hi": "सूचना: {{1}} का रिफ़ंड आपके मूल भुगतान माध्यम पर कर दिया गया है। संदर्भ: {{2}}। यह आमतौर पर {{3}} कार्यदिवसों में पहुँचता है।",
            "ta": "அறிவிப்பு: {{1}} திருப்பித் தரப்பட்டது, உங்கள் அசல் கட்டண முறைக்கு. குறிப்பு: {{2}}. இது வழக்கமாக {{3}} வேலை நாட்களில் வந்து சேரும்.",
            "te": "సమాచారం: {{1}} రీఫండ్ మీ అసలు చెల్లింపు పద్ధతికి ప్రాసెస్ చేయబడింది. రిఫరెన్స్: {{2}}. ఇది సాధారణంగా {{3}} పని దినాల్లో అందుతుంది.",
        },
    },
    "puja_rescheduled": {
        "category": "utility", "variables": ["puja", "old_date", "new_date"], "buttons": "quick:accept,refund",
        "body": {
            "en": "Update: {{1}}, planned for {{2}}, cannot take place that day. It is moved to {{3}}. Reply Accept to keep your booking, or Refund for a full refund. If we do not hear back in 48 hours, your booking moves to the new date.",
            "hi": "सूचना: {{2}} को निर्धारित {{1}} उस दिन नहीं हो पाएगी। इसे {{3}} पर स्थानांतरित किया गया है। बुकिंग रखने के लिए Accept, या पूरा रिफ़ंड पाने के लिए Refund चुनें। 48 घंटे में उत्तर न मिलने पर बुकिंग नई तारीख पर चली जाएगी।",
            "ta": "அறிவிப்பு: {{2}} அன்று திட்டமிடப்பட்ட {{1}} அன்று நடைபெற இயலாது. இது {{3}} க்கு மாற்றப்பட்டுள்ளது. முன்பதிவைத் தொடர Accept, முழுப் பணம் திரும்பப் பெற Refund என பதிலளிக்கவும். 48 மணி நேரத்தில் பதில் வராவிட்டால் முன்பதிவு புதிய தேதிக்கு மாறும்.",
            "te": "సమాచారం: {{2}}న జరగాల్సిన {{1}} ఆ రోజు జరగదు. దీన్ని {{3}}కి మార్చాము. బుకింగ్ ఉంచుకోవడానికి Accept, పూర్తి రీఫండ్ కోసం Refund ఎంచుకోండి. 48 గంటల్లో సమాధానం రాకపోతే బుకింగ్ కొత్త తేదీకి మారుతుంది.",
        },
    },
    "seva_predebit": {
        "category": "utility", "variables": ["seva", "amount", "date", "mandate_reference"], "buttons": "url:manage",
        "body": {
            "en": "Upcoming UPI AutoPay debit for {{1}}: {{2}} on {{3}}. Mandate reference: {{4}}. You can cancel anytime from My Subscriptions.",
            "hi": "सूचना: {{1}} के लिए आगामी UPI AutoPay कटौती: {{3}} को {{2}}। मैंडेट संदर्भ: {{4}}। आप कभी भी My Subscriptions से रद्द कर सकते हैं।",
            "ta": "அறிவிப்பு: {{1}} க்கான வரவிருக்கும் UPI AutoPay பிடித்தம்: {{3}} அன்று {{2}}. மேண்டேட் குறிப்பு: {{4}}. My Subscriptions இல் எப்போது வேண்டுமானாலும் ரத்து செய்யலாம்.",
            "te": "సమాచారం: {{1}} కోసం రాబోయే UPI AutoPay డెబిట్: {{3}}న {{2}}. మాండేట్ రిఫరెన్స్: {{4}}. My Subscriptions నుండి ఎప్పుడైనా రద్దు చేయవచ్చు.",
        },
    },
    "seva_payment_failed": {
        "category": "utility", "variables": ["seva", "date", "amount"], "buttons": "url:pay_now",
        "body": {
            "en": "The AutoPay debit of {{3}} for {{1}} on {{2}} did not go through. Tap below to pay now and keep this date.",
            "hi": "सूचना: {{2}} की {{1}} के लिए {{3}} की AutoPay कटौती सफल नहीं हुई। यह तारीख बनाए रखने के लिए नीचे टैप करके अभी भुगतान करें।",
            "ta": "அறிவிப்பு: {{2}} அன்று {{1}} க்கான {{3}} AutoPay பிடித்தம் நடைபெறவில்லை. இந்தத் தேதியைத் தக்கவைக்க கீழே தட்டி இப்போது செலுத்தவும்.",
            "te": "సమాచారం: {{2}}న {{1}} కోసం {{3}} AutoPay డెబిట్ జరగలేదు. ఈ తేదీని ఉంచుకోవడానికి క్రింద నొక్కి ఇప్పుడే చెల్లించండి.",
        },
    },
    "feedback_request": {
        "category": "marketing", "variables": ["name", "puja"], "buttons": "quick:1,2,3,4,5",
        "body": {
            "en": "Namaste {{1}}, how was your experience with {{2}}? Please rate us from 1 to 5.",
            "hi": "नमस्ते {{1}}, {{2}} के साथ आपका अनुभव कैसा रहा? कृपया हमें 1 से 5 तक रेटिंग दें।",
            "ta": "வணக்கம் {{1}}, {{2}} உடனான உங்கள் அனுபவம் எப்படி இருந்தது? 1 முதல் 5 வரை மதிப்பிடவும்.",
            "te": "నమస్తే {{1}}, {{2}}తో మీ అనుభవం ఎలా ఉంది? దయచేసి 1 నుండి 5 వరకు రేటింగ్ ఇవ్వండి.",
        },
    },
    "checkout_reminder": {
        "category": "marketing", "variables": ["name", "puja"], "buttons": "url:resume",
        "body": {
            "en": "Namaste {{1}}, your booking for {{2}} is not complete yet. Tap below to continue where you left off.",
            "hi": "नमस्ते {{1}}, {{2}} की आपकी बुकिंग अभी पूरी नहीं हुई है। जहाँ छोड़ा था वहीं से जारी रखने के लिए नीचे टैप करें।",
            "ta": "வணக்கம் {{1}}, {{2}} க்கான உங்கள் முன்பதிவு இன்னும் முடியவில்லை. விட்ட இடத்திலிருந்து தொடர கீழே தட்டவும்.",
            "te": "నమస్తే {{1}}, {{2}} కోసం మీ బుకింగ్ ఇంకా పూర్తి కాలేదు. ఆపిన చోట నుండి కొనసాగించడానికి క్రింద నొక్కండి.",
        },
    },
    "festival_offer": {
        "category": "marketing", "variables": ["festival", "puja"], "buttons": "url:book",
        "body": {
            "en": "For {{1}}, {{2}} is open for booking. Tap below to see the date and details.",
            "hi": "सूचना: {{1}} के अवसर पर {{2}} की बुकिंग खुली है। तारीख और विवरण देखने के लिए नीचे टैप करें।",
            "ta": "அறிவிப்பு: {{1}} முன்னிட்டு {{2}} க்கான முன்பதிவு திறந்துள்ளது. தேதி மற்றும் விவரங்களைக் காண கீழே தட்டவும்.",
            "te": "సమాచారం: {{1}} సందర్భంగా {{2}} బుకింగ్ తెరిచి ఉంది. తేదీ మరియు వివరాల కోసం క్రింద నొక్కండి.",
        },
    },
}

MARKETING_KEYS = {k for k, v in TEMPLATE_SPECS.items() if v["category"] == "marketing"}
# PRD §7: these two go only to devotees with marketing opt-in. feedback_request is tied to a booking.
OPT_IN_REQUIRED = {"checkout_reminder", "festival_offer"}
LOCALES = ("en", "hi", "ta", "te")
PROVIDERS = ("fake", "wati", "gupshup")


def render_body(key: str, locale: str, params: list[str]) -> str:
    body = TEMPLATE_SPECS[key]["body"].get(locale) or TEMPLATE_SPECS[key]["body"]["en"]
    for i, p in enumerate(params, start=1):
        body = body.replace("{{" + str(i) + "}}", str(p))
    return body


async def seed_templates(db: AsyncSession) -> None:
    for key, spec in TEMPLATE_SPECS.items():
        for locale in LOCALES:
            for provider in PROVIDERS:
                ref = f"pp_{key}_{locale}" if provider != "gupshup" else f"unsynced:pp_{key}_{locale}"
                stmt = insert(MessageTemplate).values(
                    key=key, locale=locale, category=spec["category"], provider=provider,
                    provider_template_ref=ref, variables=spec["variables"],
                    status="approved" if provider == "fake" else "pending", body=spec["body"][locale],
                )
                await db.execute(stmt.on_conflict_do_update(
                    index_elements=["key", "locale", "provider"],
                    set_={"body": spec["body"][locale], "variables": spec["variables"], "category": spec["category"]},
                ))
