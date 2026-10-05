"""PDFs: sankalp sheet for the priest, invoice for the devotee. fpdf2 + HarfBuzz shaping for Indic scripts."""

import tempfile
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from config import API_DIR, settings
from services.i18n import fmt_dt_ist

FONTS = API_DIR / "assets" / "fonts"
_FAMILIES = {
    "latin": "NotoSans", "deva": "NotoSansDevanagari", "telu": "NotoSansTelugu", "taml": "NotoSansTamil",
    "knda": "NotoSansKannada",
}
_RANGES = [(0x0900, 0x097F, "deva"), (0x0C00, 0x0C7F, "telu"), (0x0B80, 0x0BFF, "taml"), (0x0C80, 0x0CFF, "knda")]


def _script(text: str) -> str:
    for ch in text or "":
        for lo, hi, s in _RANGES:
            if lo <= ord(ch) <= hi:
                return s
    return "latin"


class _Doc(FPDF):
    def __init__(self):
        super().__init__(format="A4")
        self.set_auto_page_break(True, margin=15)
        self.available: set[str] = set()
        for key, fam in _FAMILIES.items():
            reg, bold = FONTS / f"{fam}-Regular.ttf", FONTS / f"{fam}-Bold.ttf"
            if reg.exists():
                self.add_font(key, "", str(reg))
                self.add_font(key, "B", str(bold if bold.exists() else reg))
                self.available.add(key)
        try:
            self.set_text_shaping(True)
        except Exception:  # noqa: BLE001  (uharfbuzz missing -> unshaped fallback)
            pass

    def font_for(self, text: str, style: str = "", size: float = 11) -> None:
        s = _script(text)
        fam = s if s in self.available else ("latin" if "latin" in self.available else "helvetica")
        self.set_font(fam, style, size)

    def txt(self, text: str, w: float = 0, h: float = 6, style: str = "", size: float = 11, ln: bool = True,
            align: str = "L") -> None:
        self.font_for(text, style, size)
        if ln:
            self.multi_cell(w, h, text, align=align, new_x="LMARGIN", new_y="NEXT")
        else:
            self.cell(w, h, text, align=align)


def _out(doc: FPDF, name: str) -> Path:
    path = Path(tempfile.mkdtemp()) / name
    doc.output(str(path))
    return path


def sankalp_sheet_pdf(*, title: str, temple: str, starts_at: datetime, language: str, rows: list[dict]) -> Path:
    doc = _Doc()
    doc.add_page()
    doc.txt(f"Sankalp sheet — {title}", style="B", size=15)
    doc.txt(f"{temple} · {fmt_dt_ist(starts_at, 'en')} · Sankalp language: {language}", size=10)
    doc.txt(f"{len(rows)} bookings, read in this order.", size=10)
    doc.ln(3)
    for r in rows:
        doc.set_draw_color(184, 146, 46)
        doc.line(doc.l_margin, doc.get_y(), doc.w - doc.r_margin, doc.get_y())
        doc.ln(1.5)
        doc.txt(f"{r['position']}.  Booking {r['code']}", style="B", size=11)
        for n in r["names"]:
            doc.txt(n["name_sankalp"] or n["name"], size=14, style="B", h=8)
            meta = f"{n['name']}"
            if n.get("relation"):
                meta += f" ({n['relation']})"
            doc.txt(meta, size=9)
            gotra_line = n["gotra_sankalp"] or n["gotra"] or ""
            if gotra_line:
                doc.txt(gotra_line, size=12)
                doc.txt(f"Gotra: {n['gotra']}" + (" (fallback)" if n.get("gotra_unknown") else ""), size=9)
            if n.get("nakshatra"):
                doc.txt(f"Nakshatra: {n['nakshatra']}", size=9)
        if r.get("wish"):
            doc.txt(r["wish"], size=10)
        doc.ln(2)
    return _out(doc, "sankalp-sheet.pdf")


def invoice_pdf(*, booking: dict, lines: list[tuple[str, str]], total: str, invoice_no: str, issued: str,
                tax_note: str | None) -> Path:
    doc = _Doc()
    doc.add_page()
    doc.txt(settings.brand, style="B", size=18)
    doc.txt(f"Invoice {invoice_no}", style="B", size=13)
    doc.txt(f"Issued {issued} · Booking {booking['code']}", size=10)
    doc.ln(3)
    doc.txt(booking["puja"], style="B", size=12)
    doc.txt(f"{booking['temple']} · {booking['datetime']}", size=10)
    doc.txt(f"Billed to: {booking['name']} · {booking['phone']}", size=10)
    doc.ln(4)
    for label, amount in lines:
        y = doc.get_y()
        doc.font_for(label, "", 11)
        doc.cell(130, 7, label)
        doc.set_xy(doc.l_margin + 130, y)
        doc.font_for(amount, "", 11)
        doc.cell(0, 7, amount, align="R", new_x="LMARGIN", new_y="NEXT")
    doc.set_draw_color(184, 146, 46)
    doc.line(doc.l_margin, doc.get_y() + 1, doc.w - doc.r_margin, doc.get_y() + 1)
    doc.ln(3)
    y = doc.get_y()
    doc.font_for("Total", "B", 12)
    doc.cell(130, 8, "Total paid")
    doc.set_xy(doc.l_margin + 130, y)
    doc.font_for(total, "B", 12)
    doc.cell(0, 8, total, align="R", new_x="LMARGIN", new_y="NEXT")
    if tax_note:
        doc.ln(4)
        doc.txt(tax_note, size=9)
    return _out(doc, f"invoice-{booking['code']}.pdf")
