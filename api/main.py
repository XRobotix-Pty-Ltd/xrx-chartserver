"""ChartServer — Apache 2.0 chart rendering service by XRobotix Pty Ltd."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routes import chart, qr, graphviz, health

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Close the shared httpx client on shutdown
    from rendering_client import _client
    if _client:
        await _client.aclose()


app = FastAPI(
    title="ChartServer",
    description="High-performance chart image rendering service by XRobotix Pty Ltd",
    version=VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chart.router)
app.include_router(qr.router)
app.include_router(graphviz.router)
