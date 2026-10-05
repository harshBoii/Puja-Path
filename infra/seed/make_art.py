"""Generates the original placeholder artwork used by seed data (no third-party imagery).

- apps/web/public/images/seed/*.svg       : devotional motif illustrations per puja/temple/offering
"""

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "apps/web/public/images"
SEED = OUT / "seed"
SEED.mkdir(parents=True, exist_ok=True)


MOTIFS = {
    "lotus": '<g fill="none" stroke="#B8922E" stroke-width="6"><path d="M600 640 C540 560 540 470 600 400 C660 470 660 560 600 640Z"/><path d="M600 640 C510 600 460 520 470 440 C540 470 590 540 600 640Z"/><path d="M600 640 C690 600 740 520 730 440 C660 470 610 540 600 640Z"/><path d="M600 640 C470 640 400 590 380 520 C470 520 560 570 600 640Z"/><path d="M600 640 C730 640 800 590 820 520 C730 520 640 570 600 640Z"/></g>',
    "diya": '<g><path d="M420 600 Q600 720 780 600 Q760 660 600 680 Q440 660 420 600Z" fill="#D4AF37" stroke="#7A5C17" stroke-width="5"/><path d="M600 590 C560 520 590 450 600 400 C612 450 640 520 600 590Z" fill="#EAD9A0" stroke="#B8922E" stroke-width="5"/><circle cx="600" cy="540" r="14" fill="#B8922E"/></g>',
    "kalash": '<g stroke="#7A5C17" stroke-width="5"><path d="M500 470 Q600 440 700 470 L690 500 Q760 560 720 640 Q600 700 480 640 Q440 560 510 500Z" fill="#D4AF37"/><path d="M520 470 Q560 380 600 360 Q640 380 680 470" fill="none" stroke="#3E6B3A" stroke-width="10"/><circle cx="600" cy="345" r="34" fill="#F6EDD0"/></g>',
    "trident": '<g fill="none" stroke="#7A5C17" stroke-width="10" stroke-linecap="round"><path d="M600 700 L600 360"/><path d="M520 380 Q520 470 600 480 Q680 470 680 380"/><path d="M600 360 L585 330 L600 300 L615 330Z" fill="#D4AF37"/><circle cx="600" cy="560" r="26" fill="#EAD9A0"/></g>',
    "navagraha": "".join(f'<circle cx="{600 + 150 * math.cos(i * math.tau / 8):.0f}" cy="{520 + 150 * math.sin(i * math.tau / 8):.0f}" r="34" fill="#F6EDD0" stroke="#B8922E" stroke-width="5"/>' for i in range(8)) + '<circle cx="600" cy="520" r="52" fill="#D4AF37" stroke="#7A5C17" stroke-width="5"/>',
    "waves": '<g fill="none" stroke="#B8922E" stroke-width="6">' + "".join(f'<path d="M380 {560 + i * 40} Q440 {530 + i * 40} 500 {560 + i * 40} T620 {560 + i * 40} T740 {560 + i * 40} T860 {560 + i * 40}"/>' for i in range(3)) + '</g><g><path d="M600 500 C570 450 590 410 600 380 C610 410 630 450 600 500Z" fill="#EAD9A0" stroke="#B8922E" stroke-width="5"/></g>',
    "conch": '<g stroke="#7A5C17" stroke-width="5"><path d="M470 560 Q520 420 660 430 Q760 450 740 540 Q720 620 620 640 Q520 650 470 560Z" fill="#F6EDD0"/><path d="M560 470 Q640 470 680 520 Q660 580 600 590" fill="none" stroke="#B8922E" stroke-width="6"/><path d="M740 540 L800 560 L760 590Z" fill="#D4AF37"/></g>',
    "bell": '<g stroke="#7A5C17" stroke-width="5"><path d="M520 620 Q520 460 600 430 Q680 460 680 620 Z" fill="#D4AF37"/><rect x="500" y="615" width="200" height="22" rx="10" fill="#B8922E"/><circle cx="600" cy="660" r="16" fill="#7A5C17"/><path d="M600 430 L600 380" stroke-width="8"/></g>',
    "temple": '<g stroke="#7A5C17" stroke-width="5" fill="#F6EDD0"><path d="M450 680 L450 520 L750 520 L750 680Z"/><path d="M480 520 L520 440 L680 440 L720 520Z" fill="#EAD9A0"/><path d="M530 440 L560 380 L640 380 L670 440Z" fill="#D4AF37"/><path d="M575 380 L600 320 L625 380Z" fill="#B8922E"/><path d="M570 680 L570 590 Q600 560 630 590 L630 680Z" fill="#B8922E"/></g>',
    "oil": '<g stroke="#7A5C17" stroke-width="5"><path d="M540 440 L660 440 L680 660 Q600 690 520 660Z" fill="#B8922E"/><rect x="565" y="400" width="70" height="44" fill="#EAD9A0"/><path d="M560 560 Q600 520 640 560" fill="none" stroke="#F6EDD0" stroke-width="6"/></g>',
    "cloth": '<g stroke="#2B2118" stroke-width="5"><path d="M460 460 L740 460 L760 640 L440 640Z" fill="#5E5246"/><path d="M460 500 L740 500 M450 560 L750 560" stroke="#B8922E" stroke-width="6"/></g>',
    "seeds": "".join(f'<ellipse cx="{560 + (i % 6) * 18}" cy="{560 + (i // 6) * 14}" rx="7" ry="4" fill="#2B2118"/>' for i in range(30)) + '<path d="M480 600 Q600 690 720 600" fill="none" stroke="#B8922E" stroke-width="8"/>',
}

# polished white-marble grounds (white theme)
BG = [("#FFFFFF", "#F7F6F3"), ("#FFFFFF", "#FBF7EC"), ("#FDFDFC", "#F3F2EE"), ("#FFFFFF", "#F9F6EE")]


def svg(name: str, motif: str, variant: int = 0) -> None:
    a, b = BG[variant % len(BG)]
    body = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 900" width="1200" height="900" role="img">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>
<radialGradient id="r" cx="0.5" cy="0.55" r="0.5"><stop offset="0" stop-color="#FFFFFF" stop-opacity="0.9"/><stop offset="1" stop-color="#FFFFFF" stop-opacity="0"/></radialGradient></defs>
<rect width="1200" height="900" fill="url(#g)"/><circle cx="600" cy="520" r="330" fill="url(#r)"/>
<circle cx="600" cy="520" r="300" fill="none" stroke="#E7E1D6" stroke-width="2"/>
<circle cx="600" cy="520" r="270" fill="none" stroke="#EAD9A0" stroke-width="1.5" stroke-dasharray="4 10"/>
{MOTIFS[motif]}
<path d="M300 780 L900 780" stroke="#B8922E" stroke-width="2"/><circle cx="600" cy="780" r="7" fill="#D4AF37"/>
</svg>'''
    (SEED / f"{name}.svg").write_text(body)


ART = {
    "rudrabhishekam": ("trident", 0), "rudrabhishekam-2": ("bell", 1), "navagraha": ("navagraha", 2),
    "navagraha-2": ("diya", 3), "pitru-tarpan": ("waves", 0), "pitru-tarpan-2": ("lotus", 2),
    "lakshmi-kubera": ("lotus", 1), "lakshmi-kubera-2": ("kalash", 0), "rahu-ketu": ("navagraha", 3),
    "satyanarayana": ("conch", 1), "satyanarayana-2": ("kalash", 3), "shani-chadhava": ("oil", 2),
    "hanuman-seva": ("bell", 0), "deepa-seva": ("diya", 1), "temple-mallikarjuna": ("temple", 0),
    "temple-yagashala": ("diya", 2), "temple-ghat": ("waves", 3), "temple-lakshmi": ("temple", 1),
    "addon-oil": ("oil", 0), "addon-cloth": ("cloth", 1), "addon-til": ("seeds", 2), "addon-diya": ("diya", 3),
    "addon-flowers": ("lotus", 0), "addon-coconut": ("kalash", 1),
}

if __name__ == "__main__":
    for name, (motif, v) in ART.items():
        svg(name, motif, v)
    print(len(ART), "svgs")
