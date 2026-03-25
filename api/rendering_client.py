"""HTTP client for communicating with the Node.js rendering service."""

import httpx
from fastapi import HTTPException

RENDERER_URL = "http://127.0.0.1:3401"

# Persistent connection pool — avoids per-request TCP handshakes under load.
_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            base_url=RENDERER_URL,
            timeout=30.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def render(
    *,
    provider: str,
    chart,
    format: str = "png",
    width: int = 500,
    height: int = 300,
    background: str | None = None,
    device_pixel_ratio: float = 2.0,
    version: str = "2",
) -> bytes:
    """Send a render request to the Node.js renderer and return the image bytes."""
    payload = {
        "provider": provider,
        "chart": chart,
        "format": format,
        "width": width,
        "height": height,
        "devicePixelRatio": device_pixel_ratio,
        "version": version,
    }
    if background:
        payload["backgroundColor"] = background

    client = get_client()
    try:
        resp = await client.post("/render", json=payload)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="Rendering service unavailable. Is the renderer running on port 3401?",
        )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Rendering service timed out.")

    if resp.status_code != 200:
        try:
            detail = resp.json().get("error", resp.text)
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=422, detail=detail)

    return resp.content
