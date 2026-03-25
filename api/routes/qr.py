"""
/qr — Premium QR code generation.

Supports:
- Module shapes: square, rounded, circle, dots, bars (via qrcode StyledPilImage)
- Gradient fills: radial, horizontal, vertical, square
- Custom eye/finder pattern color
- Logo embedding (URL or base64)
- Background image overlay / artistic QR (via qrcode-artistic + segno)
- Animated GIF output
- SVG output (via segno)
"""

import base64
import io
import re
from typing import Optional

import httpx
import qrcode
import qrcode.image.svg
import segno
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from PIL import Image
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import (
    HorizontalGradiantColorMask,
    RadialGradiantColorMask,
    SolidFillColorMask,
    SquareGradiantColorMask,
    VerticalGradiantColorMask,
)
from qrcode.image.styles.moduledrawers import (
    CircleModuleDrawer,
    GappedSquareModuleDrawer,
    HorizontalBarsDrawer,
    RoundedModuleDrawer,
    SquareModuleDrawer,
    VerticalBarsDrawer,
)

router = APIRouter()

MODULE_DRAWERS = {
    "square": SquareModuleDrawer,
    "rounded": RoundedModuleDrawer,
    "circle": CircleModuleDrawer,
    "dots": GappedSquareModuleDrawer,
    "bars": HorizontalBarsDrawer,
    "vbars": VerticalBarsDrawer,
}

ERROR_CORRECTION = {
    "L": qrcode.constants.ERROR_CORRECT_L,
    "M": qrcode.constants.ERROR_CORRECT_M,
    "Q": qrcode.constants.ERROR_CORRECT_Q,
    "H": qrcode.constants.ERROR_CORRECT_H,
}


def _hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex string (with or without #) to (R, G, B) tuple."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


async def _fetch_image(source: str) -> Image.Image:
    """Load an image from a URL or base64 data URI."""
    if source.startswith("data:"):
        _, data = source.split(",", 1)
        raw = base64.b64decode(data)
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(source)
        resp.raise_for_status()
        return Image.open(io.BytesIO(resp.content)).convert("RGBA")


def _embed_logo(qr_img: Image.Image, logo: Image.Image, logo_size: float) -> Image.Image:
    """Paste a logo centred on the QR code image."""
    qr_w, qr_h = qr_img.size
    logo_side = int(min(qr_w, qr_h) * logo_size)
    logo = logo.resize((logo_side, logo_side), Image.LANCZOS)

    qr_rgba = qr_img.convert("RGBA")
    pos = ((qr_w - logo_side) // 2, (qr_h - logo_side) // 2)
    qr_rgba.paste(logo, pos, mask=logo if logo.mode == "RGBA" else None)
    return qr_rgba


@router.get("/qr")
async def qr_endpoint(
    text: str = Query(..., description="Data to encode"),
    format: str = Query(default="png", description="png | svg | gif"),
    size: int = Query(default=300, ge=50, le=2000, description="Output size in pixels"),
    dark: str = Query(default="000000", description="Dark module colour (hex)"),
    light: str = Query(default="ffffff", description="Light module colour (hex, or 'transparent')"),
    style: str = Query(default="square", description="square | rounded | circle | dots | bars | vbars"),
    gradient: Optional[str] = Query(default=None, description="radial | horizontal | vertical | square"),
    gradient_start: str = Query(default="000000"),
    gradient_end: str = Query(default="4e78a7"),
    eye_color: Optional[str] = Query(default=None, description="Finder pattern colour (hex)"),
    logo: Optional[str] = Query(default=None, description="Logo URL or base64 data URI"),
    logo_size: float = Query(default=0.3, ge=0.1, le=0.4),
    background: Optional[str] = Query(default=None, description="Background image URL or base64 for artistic QR"),
    error_correction: str = Query(default="M", description="L | M | Q | H"),
):
    fmt = format.lower()
    ec_level = error_correction.upper()

    # Auto-upgrade error correction to H when embedding a logo
    if logo and ec_level not in ("Q", "H"):
        ec_level = "H"

    ec = ERROR_CORRECTION.get(ec_level, qrcode.constants.ERROR_CORRECT_M)

    # --- SVG output via segno ---
    if fmt == "svg":
        qr = segno.make(text, error="H" if logo else ec_level.lower(), micro=False)
        buf = io.BytesIO()
        dark_color = f"#{dark.lstrip('#')}"
        light_color = None if light == "transparent" else f"#{light.lstrip('#')}"
        qr.save(
            buf,
            kind="svg",
            scale=max(1, size // (qr.symbol_size()[0] or 21)),
            dark=dark_color,
            light=light_color,
        )
        svg_bytes = buf.getvalue()

        if logo:
            # Embed logo as a centred <image> element in the SVG
            logo_img = await _fetch_image(logo)
            logo_buf = io.BytesIO()
            logo_img.save(logo_buf, format="PNG")
            logo_b64 = base64.b64encode(logo_buf.getvalue()).decode()
            logo_side = int(size * logo_size)
            cx = (size - logo_side) // 2
            cy = (size - logo_side) // 2
            logo_tag = (
                f'<image x="{cx}" y="{cy}" width="{logo_side}" height="{logo_side}" '
                f'href="data:image/png;base64,{logo_b64}" />'
            )
            svg_str = svg_bytes.decode()
            svg_str = svg_str.replace("</svg>", f"{logo_tag}</svg>")
            svg_bytes = svg_str.encode()

        return Response(content=svg_bytes, media_type="image/svg+xml")

    # --- Artistic / animated GIF output via segno + qrcode-artistic ---
    if fmt == "gif" or background:
        import qrcode_artistic  # noqa: F401 — imported for side effects on segno

        qr = segno.make(text, error="h" if logo else ec_level.lower(), micro=False)
        buf = io.BytesIO()

        if background:
            bg_img = await _fetch_image(background)
            bg_buf = io.BytesIO()
            bg_img.save(bg_buf, format="GIF" if fmt == "gif" else "PNG")
            bg_buf.seek(0)

            out_fmt = "gif" if fmt == "gif" else "png"
            qr.to_artistic(
                background=bg_buf,
                target=buf,
                kind=out_fmt,
                scale=max(1, size // (qr.symbol_size()[0] or 21)),
                dark=f"#{dark.lstrip('#')}",
            )
        else:
            qr.save(
                buf,
                kind="gif",
                scale=max(1, size // (qr.symbol_size()[0] or 21)),
                dark=f"#{dark.lstrip('#')}",
                light=None if light == "transparent" else f"#{light.lstrip('#')}",
            )

        content = buf.getvalue()
        media = "image/gif" if fmt == "gif" else "image/png"
        return Response(content=content, media_type=media)

    # --- PNG output via qrcode StyledPilImage ---
    drawer_cls = MODULE_DRAWERS.get(style, SquareModuleDrawer)

    dark_rgb = _hex_to_rgb(dark)
    light_is_transparent = light == "transparent"
    light_rgb = (255, 255, 255) if light_is_transparent else _hex_to_rgb(light)
    back_color = (255, 255, 255, 0) if light_is_transparent else (*light_rgb, 255)

    if gradient:
        start_rgb = _hex_to_rgb(gradient_start)
        end_rgb = _hex_to_rgb(gradient_end)
        mask_map = {
            "radial": RadialGradiantColorMask,
            "horizontal": HorizontalGradiantColorMask,
            "vertical": VerticalGradiantColorMask,
            "square": SquareGradiantColorMask,
        }
        mask_cls = mask_map.get(gradient, RadialGradiantColorMask)
        color_mask = mask_cls(
            back_color=back_color,
            center_color=start_rgb,
            edge_color=end_rgb,
        )
    else:
        color_mask = SolidFillColorMask(
            back_color=back_color,
            front_color=dark_rgb,
        )

    qr = qrcode.QRCode(error_correction=ec, box_size=10, border=4)
    qr.add_data(text)
    qr.make(fit=True)

    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=drawer_cls(),
        color_mask=color_mask,
    ).convert("RGBA")

    img = img.resize((size, size), Image.LANCZOS)

    if logo:
        logo_img = await _fetch_image(logo)
        img = _embed_logo(img, logo_img, logo_size)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(content=buf.getvalue(), media_type="image/png")
