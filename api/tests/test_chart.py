"""Tests for /chart and /chart/embed endpoints."""

from unittest.mock import AsyncMock, patch

import pytest

SIMPLE_CHART = '{"type":"bar","data":{"labels":["A","B"],"datasets":[{"data":[1,2]}]}}'
SIMPLE_PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100  # minimal fake PNG bytes


# --- Static rendering ---

@patch("routes.chart.render", new_callable=AsyncMock, return_value=SIMPLE_PNG)
def test_chart_get_png(mock_render, client):
    r = client.get(f"/chart?c={SIMPLE_CHART}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    mock_render.assert_awaited_once()


@patch("routes.chart.render", new_callable=AsyncMock, return_value=b"<svg/>")
def test_chart_get_svg(mock_render, client):
    r = client.get(f"/chart?c={SIMPLE_CHART}&format=svg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"


@patch("routes.chart.render", new_callable=AsyncMock, return_value=SIMPLE_PNG)
def test_chart_post(mock_render, client):
    r = client.post("/chart", json={"chart": {"type": "bar"}, "provider": "chartjs"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_chart_missing_c_returns_400(client):
    r = client.get("/chart")
    assert r.status_code == 400


# --- Embed ---

def test_embed_echarts_returns_html(client):
    r = client.get('/chart/embed?provider=echarts&c={"series":[]}')
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "echarts" in r.text.lower()


def test_embed_chartjs_returns_html(client):
    r = client.get(f"/chart/embed?provider=chartjs&c={SIMPLE_CHART}")
    assert r.status_code == 200
    assert "chart.js" in r.text.lower()


def test_embed_mermaid_returns_html(client):
    r = client.get("/chart/embed?provider=mermaid&c=graph+LR%0A++A-->B")
    assert r.status_code == 200
    assert "mermaid" in r.text.lower()
    assert "graph LR" in r.text or "graph+LR" in r.text or "A" in r.text


@patch("routes.chart.render", new_callable=AsyncMock, return_value=b"<svg></svg>")
def test_embed_plantuml_returns_html(mock_render, client):
    r = client.get("/chart/embed?provider=plantuml&c=%40startuml%0AA->B%0A%40enduml")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "<svg" in r.text
