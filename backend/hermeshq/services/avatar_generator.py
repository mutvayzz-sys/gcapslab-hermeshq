"""Deterministic avatar generator – produces unique gradient + initials PNGs."""

from __future__ import annotations

import hashlib
import struct

# Try to import Pillow; fall back to SVG if unavailable
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


# Modern gradient color palettes – index selected by name hash
_PALETTES: list[tuple[tuple[int,int,int], tuple[int,int,int]]] = [
    ((99, 102, 241), (168, 85, 247)),    # Indigo → Purple
    ((59, 130, 246), (6, 182, 212)),      # Blue → Cyan
    ((16, 185, 129), (52, 211, 153)),     # Emerald → Green
    ((245, 158, 11), (251, 191, 36)),     # Amber → Yellow
    ((239, 68, 68), (248, 113, 113)),     # Red → Light Red
    ((236, 72, 153), (244, 114, 182)),    # Pink → Light Pink
    ((139, 92, 246), (192, 132, 252)),    # Violet → Light Violet
    ((14, 165, 233), (56, 189, 248)),     # Sky → Light Sky
    ((234, 88, 12), (251, 146, 60)),      # Orange → Light Orange
    ((5, 150, 105), (110, 231, 183)),     # Green → Teal
    ((217, 70, 239), (232, 121, 249)),    # Fuchsia → Light Fuchsia
    ((219, 39, 119), (244, 114, 182)),    # Rose → Pink
]


def _palette_index(name: str) -> int:
    """Deterministic palette selection from agent name."""
    digest = hashlib.sha256(name.lower().encode()).digest()
    return struct.unpack_from(">I", digest, 0)[0] % len(_PALETTES)


def _initials(name: str) -> str:
    """Extract 1-2 character initials from name."""
    parts = name.strip().split()
    if not parts:
        return "?"
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return parts[0][0].upper()


def _lerp_color(c1: tuple[int,int,int], c2: tuple[int,int,int], t: float) -> tuple[int,int,int]:
    """Linear interpolation between two RGB colors."""
    return (
        int(c1[0] + (c2[0] - c1[0]) * t),
        int(c1[1] + (c2[1] - c1[1]) * t),
        int(c1[2] + (c2[2] - c1[2]) * t),
    )


def generate_avatar_png(name: str, size: int = 256) -> bytes:
    """Generate a deterministic avatar PNG for the given name.

    Returns PNG bytes with a diagonal gradient background and white initials.
    """
    palette = _PALETTES[_palette_index(name)]
    ini = _initials(name)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Draw diagonal gradient
    for y in range(size):
        t = y / size
        color = _lerp_color(palette[0], palette[1], t)
        draw.line([(0, y), (size, y)], fill=(*color, 255))

    # Draw initials text centered
    font_size = int(size * 0.42)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except OSError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except OSError:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), ini, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) / 2
    y = (size - text_h) / 2 - bbox[1]
    draw.text((x, y), ini, fill=(255, 255, 255, 255), font=font)

    from io import BytesIO
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def generate_avatar_svg(name: str, size: int = 256) -> str:
    """Generate a deterministic avatar SVG for the given name (fallback without Pillow)."""
    palette = _PALETTES[_palette_index(name)]
    ini = _initials(name)
    c1 = palette[0]
    c2 = palette[1]

    font_size = int(size * 0.42)

    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="rgb({c1[0]},{c1[1]},{c1[2]})"/>
      <stop offset="100%" stop-color="rgb({c2[0]},{c2[1]},{c2[2]})"/>
    </linearGradient>
  </defs>
  <rect width="{size}" height="{size}" rx="{size//2}" fill="url(#bg)"/>
  <text x="50%" y="52%" dominant-baseline="central" text-anchor="middle"
        font-family="system-ui, -apple-system, sans-serif"
        font-weight="700" font-size="{font_size}" fill="white" letter-spacing="0.04em">{ini}</text>
</svg>'''


def generate_avatar(name: str, size: int = 256) -> tuple[bytes, str]:
    """Generate avatar and return (content_bytes, filename).

    Returns PNG if Pillow is available, SVG otherwise.
    """
    if HAS_PIL:
        return generate_avatar_png(name, size), "avatar.png"
    return generate_avatar_svg(name, size).encode("utf-8"), "avatar.svg"
