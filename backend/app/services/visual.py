"""Basic Visual Inspector (Module 3, Round 2 scope): dominant-colour palette compliance and WCAG contrast.

Honest scope: this analyses pixel colours only. It does not recognise logos, read text (no OCR) or
judge layout — those are Round 3 work. Contrast between dominant colours is a heuristic proxy and is
always marked as needing human confirmation.
"""
from __future__ import annotations

import io
import math

from PIL import Image, UnidentifiedImageError

from .errors import DomainError

MAX_IMAGE_MB = 5
MAX_PIXELS = 40_000_000


def hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise DomainError(f"Invalid hex colour '#{h}'.", 422)
    try:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError as exc:
        raise DomainError(f"Invalid hex colour '#{h}'.", 422) from exc


def rgb_to_hex(rgb) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb[:3])


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_lin(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _rgb_to_lab(rgb):
    r, g, b = (_lin(v) for v in rgb[:3])
    x = (r * 0.4124 + g * 0.3576 + b * 0.1805) / 0.95047
    y = (r * 0.2126 + g * 0.7152 + b * 0.0722)
    z = (r * 0.0193 + g * 0.1192 + b * 0.9505) / 1.08883

    def f(t):
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a, b) -> float:
    """CIE76 colour difference (simple, adequate for palette deviation triage)."""
    la, lb = _rgb_to_lab(a), _rgb_to_lab(b)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(la, lb)))


def check_pair(fg: str, bg: str) -> dict:
    ratio = contrast_ratio(hex_to_rgb(fg), hex_to_rgb(bg))
    return {"foreground": fg.upper(), "background": bg.upper(), "ratio": round(ratio, 2),
            "aa_normal": ratio >= 4.5, "aa_large": ratio >= 3.0, "aaa_normal": ratio >= 7.0}


def inspect_image(data: bytes, palette: list[dict], tolerance: float = 12.0) -> dict:
    if not data:
        raise DomainError("The image is empty.", 422)
    if len(data) > MAX_IMAGE_MB * 1024 * 1024:
        raise DomainError(f"Image exceeds the {MAX_IMAGE_MB} MB limit.", 413)
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ("PNG", "JPEG", "WEBP"):
            raise DomainError("Unsupported image format. Use PNG, JPEG or WEBP.", 415)
        if img.width * img.height > MAX_PIXELS:
            raise DomainError("Image dimensions are too large.", 413)
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise DomainError("The file is not a readable image.", 415) from exc
    w, h = img.size
    rgb = img.convert("RGB")
    rgb.thumbnail((240, 240))
    q = rgb.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
    pal = q.getpalette() or []
    counts = sorted(q.getcolors() or [], reverse=True)
    total = sum(c for c, _ in counts) or 1
    brand = [(p, hex_to_rgb(p["hex"])) for p in palette if p.get("hex")]
    dominant = []
    for c, idx in counts:
        col = tuple(pal[idx * 3: idx * 3 + 3])
        share = c / total
        if share < 0.02:
            continue
        nearest, de = None, None
        for p, prgb in brand:
            d = delta_e(col, prgb)
            if de is None or d < de:
                nearest, de = p, d
        dominant.append({"hex": rgb_to_hex(col), "share": round(share * 100, 1),
                         "nearest_brand": nearest["name"] if nearest else None,
                         "nearest_hex": nearest["hex"].upper() if nearest else None,
                         "delta_e": round(de, 1) if de is not None else None,
                         "on_palette": de is not None and de <= tolerance})
    findings = []
    off = [d for d in dominant if not d["on_palette"] and d["share"] >= 8]
    for d in off:
        findings.append({
            "id": f"VIS-PALETTE-{d['hex'][1:]}", "category": "visual", "severity": "medium" if d["share"] >= 20 else "low",
            "title": f"Off-palette colour {d['hex']} covers {d['share']}% of the creative",
            "explanation": (f"Closest approved colour is {d['nearest_brand']} {d['nearest_hex']} (ΔE {d['delta_e']}, "
                            f"tolerance {tolerance:g}). Confirm whether this colour is permitted (e.g. photography)."),
            "evidence": [{"id": f"PALETTE:{d['nearest_hex']}", "label": f"{d['nearest_brand']} {d['nearest_hex']}"}] if d["nearest_hex"] else [],
            "needs_human_confirmation": True,
        })
    primary = next((p for p in palette if p.get("role") == "primary"), None)
    if primary and not any(d["nearest_hex"] == primary["hex"].upper() and d["on_palette"] for d in dominant):
        findings.append({
            "id": "VIS-PRIMARY-MISSING", "category": "visual", "severity": "low",
            "title": f"Primary brand colour {primary['name']} not detected",
            "explanation": "Guidelines expect the primary colour in brand creatives. It may be present in small areas below detection.",
            "evidence": [{"id": f"PALETTE:{primary['hex'].upper()}", "label": f"{primary['name']} {primary['hex'].upper()}"}],
            "needs_human_confirmation": True,
        })
    contrast = None
    if len(dominant) >= 2:
        a, b = dominant[0], dominant[1]
        ratio = contrast_ratio(hex_to_rgb(a["hex"]), hex_to_rgb(b["hex"]))
        contrast = {"colours": [a["hex"], b["hex"]], "ratio": round(ratio, 2), "aa_normal": ratio >= 4.5}
        if ratio < 4.5:
            findings.append({
                "id": "VIS-CONTRAST", "category": "accessibility", "severity": "medium" if ratio < 3 else "low",
                "title": f"Possible low contrast between dominant colours ({ratio:.2f}:1)",
                "explanation": ("The two most dominant colours fall below WCAG AA 4.5:1. If text uses these colours it may be "
                                "hard to read. Heuristic — text is not detected; confirm manually."),
                "evidence": [], "needs_human_confirmation": True,
            })
    return {"width": w, "height": h, "dominant_colours": dominant, "contrast": contrast, "findings": findings,
            "tolerance": tolerance,
            "scope_note": "Colour and contrast analysis only. Logo matching, typography and layout checks are planned for Round 3."}
