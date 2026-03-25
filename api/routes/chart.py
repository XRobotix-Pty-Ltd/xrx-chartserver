"""
/chart        — static image rendering (PNG/SVG)
/chart/embed  — interactive HTML embed
"""

import html
import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, Response

from rendering_client import render

router = APIRouter()

_tpl_dir = Path(__file__).parent.parent / "templates"

EMBED_TEMPLATE          = (_tpl_dir / "embed.html").read_text()
MERMAID_EMBED_TEMPLATE  = (_tpl_dir / "mermaid_embed.html").read_text()
PLANTUML_EMBED_TEMPLATE = (_tpl_dir / "plantuml_embed.html").read_text()

CONTENT_TYPES = {
    "png": "image/png",
    "svg": "image/svg+xml",
}

PROVIDER_CDN = {
    "echarts": "https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js",
    "chartjs": "https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js",
    "mermaid": "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js",
}


def _parse_chart(c: str):
    """Return chart config as parsed JSON if possible, otherwise as a raw string."""
    if not c:
        return None
    try:
        return json.loads(c)
    except ValueError:
        return c


@router.get("/chart")
async def chart_get(
    c:                  Annotated[str | None, Query(alias="c")]                     = None,
    provider:           Annotated[str,        Query()]                              = "chartjs",
    format:             Annotated[str,        Query()]                              = "png",
    width:              Annotated[int,        Query()]                              = 500,
    height:             Annotated[int,        Query()]                              = 300,
    bkg:                Annotated[str | None, Query()]                              = None,
    background:         Annotated[str | None, Query()]                              = None,
    device_pixel_ratio: Annotated[float,      Query(alias="devicePixelRatio")]      = 2.0,
    version:            Annotated[str,        Query()]                              = "2",
):
    chart_config = _parse_chart(c)
    if chart_config is None:
        return Response(content=b"", status_code=400, media_type="text/plain")

    fmt = format if format in CONTENT_TYPES else "png"

    image_bytes = await render(
        provider=provider,
        chart=chart_config,
        format=fmt,
        width=width,
        height=height,
        background=bkg or background,
        device_pixel_ratio=device_pixel_ratio,
        version=version,
    )
    return Response(content=image_bytes, media_type=CONTENT_TYPES[fmt])


@router.post("/chart")
async def chart_post(request: Request):
    body = await request.json()
    chart_config = body.get("chart") or body.get("c")
    provider = body.get("provider", "chartjs")
    fmt = body.get("format", "png")
    if fmt not in CONTENT_TYPES:
        fmt = "png"

    image_bytes = await render(
        provider=provider,
        chart=chart_config,
        format=fmt,
        width=int(body.get("width", 500)),
        height=int(body.get("height", 300)),
        background=body.get("backgroundColor") or body.get("bkg"),
        device_pixel_ratio=float(body.get("devicePixelRatio", 2.0)),
        version=str(body.get("version", "2")),
    )
    return Response(content=image_bytes, media_type=CONTENT_TYPES[fmt])


@router.get("/chart/embed", response_class=HTMLResponse)
async def chart_embed(
    c:          Annotated[str | None, Query(alias="c")] = None,
    provider:   Annotated[str,        Query()]          = "echarts",
    width:      Annotated[int,        Query()]          = 600,
    height:     Annotated[int,        Query()]          = 400,
    background: Annotated[str,        Query()]          = "transparent",
):
    """Return a self-contained HTML snippet with the chart rendered client-side
    (or, for PlantUML, server-side SVG embedded inline)."""

    # --- Mermaid: interactive CDN embed ---
    if provider == "mermaid":
        definition = c or "graph LR\n  A --> B"
        html_out = MERMAID_EMBED_TEMPLATE.format(
            cdn=PROVIDER_CDN["mermaid"],
            definition=html.escape(definition),
            width=width,
            height=height,
            background=background,
        )
        return HTMLResponse(content=html_out)

    # --- PlantUML: render SVG server-side, embed inline ---
    if provider == "plantuml":
        definition = c or "@startuml\nA -> B : hello\n@enduml"
        svg_bytes = await render(
            provider="plantuml",
            chart=definition,
            format="svg",
            width=width,
            height=height,
        )
        html_out = PLANTUML_EMBED_TEMPLATE.format(
            svg_content=svg_bytes.decode("utf-8"),
            background=background,
        )
        return HTMLResponse(content=html_out)

    # --- Chart.js / ECharts: client-side JS embed ---
    cdn = PROVIDER_CDN.get(provider, PROVIDER_CDN["echarts"])
    config_json = c or "{}"

    try:
        parsed = json.loads(config_json)
        config_str = json.dumps(parsed)
        init_call = f"chart.setOption({config_str});"
    except ValueError:
        init_call = f"chart.setOption(eval('(' + {json.dumps(config_json)} + ')'));"

    html_out = EMBED_TEMPLATE.format(
        cdn=cdn,
        provider=provider,
        width=width,
        height=height,
        background=background,
        init_call=init_call,
    )
    return HTMLResponse(content=html_out)
