"""Tests for /qr endpoint (pure Python — no renderer dependency)."""


def test_qr_basic_png(client):
    r = client.get("/qr?text=hello")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 100


def test_qr_svg(client):
    r = client.get("/qr?text=hello&format=svg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in r.content


def test_qr_custom_colors(client):
    r = client.get("/qr?text=hello&dark=003366&light=ffffff")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


def test_qr_missing_text_returns_422(client):
    r = client.get("/qr")
    assert r.status_code == 422


def test_qr_url_encodes_correctly(client):
    r = client.get("/qr?text=https%3A%2F%2Fxrobotix.co.za")
    assert r.status_code == 200
