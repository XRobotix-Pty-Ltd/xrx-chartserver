"""
/graphviz — Render Graphviz DOT language diagrams to PNG or SVG.
"""

import subprocess

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

router = APIRouter()


def _render_dot(dot_source: str, fmt: str) -> bytes:
    """Render DOT source to PNG or SVG using the system graphviz binary."""
    try:
        result = subprocess.run(
            ["dot", f"-T{fmt}"],
            input=dot_source.encode(),
            capture_output=True,
            timeout=15,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Graphviz is not installed. Install it with: apt-get install graphviz",
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Graphviz rendering timed out.")

    if result.returncode != 0:
        raise HTTPException(
            status_code=422,
            detail=f"Graphviz error: {result.stderr.decode(errors='replace')}",
        )
    return result.stdout


@router.get("/graphviz")
async def graphviz_get(
    graph: str = Query(..., description="DOT language graph definition"),
    format: str = Query(default="png", description="png | svg"),
):
    fmt = "svg" if format == "svg" else "png"
    content = _render_dot(graph, fmt)
    media = "image/svg+xml" if fmt == "svg" else "image/png"
    return Response(content=content, media_type=media)


@router.post("/graphviz")
async def graphviz_post(request: Request):
    body = await request.json()
    graph = body.get("graph") or body.get("dot")
    if not graph:
        raise HTTPException(status_code=400, detail="Missing 'graph' field.")
    fmt = "svg" if body.get("format") == "svg" else "png"
    content = _render_dot(graph, fmt)
    media = "image/svg+xml" if fmt == "svg" else "image/png"
    return Response(content=content, media_type=media)
