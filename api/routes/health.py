from fastapi import APIRouter
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()


@router.get("/healthcheck")
async def healthcheck():
    renderer_ok = False
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            r = await client.get("http://127.0.0.1:3401/health")
            renderer_ok = r.status_code == 200
    except Exception:
        pass
    return JSONResponse({"success": True, "renderer": renderer_ok, "version": "1.0.0"})
