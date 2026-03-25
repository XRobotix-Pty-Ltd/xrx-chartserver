"""Tests for /graphviz endpoint."""

import shutil

import pytest

SIMPLE_DOT = "digraph { A -> B }"

graphviz_installed = pytest.mark.skipif(
    shutil.which("dot") is None,
    reason="graphviz not installed",
)


@graphviz_installed
def test_graphviz_get_png(client):
    r = client.get(f"/graphviz?graph={SIMPLE_DOT}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert len(r.content) > 100


@graphviz_installed
def test_graphviz_get_svg(client):
    r = client.get(f"/graphviz?graph={SIMPLE_DOT}&format=svg")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"
    assert b"<svg" in r.content


@graphviz_installed
def test_graphviz_post_png(client):
    r = client.post("/graphviz", json={"graph": SIMPLE_DOT})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"


@graphviz_installed
def test_graphviz_post_svg(client):
    r = client.post("/graphviz", json={"graph": SIMPLE_DOT, "format": "svg"})
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/svg+xml"


def test_graphviz_missing_graph_returns_422(client):
    r = client.get("/graphviz")
    assert r.status_code == 422


def test_graphviz_post_missing_graph_returns_400(client):
    r = client.post("/graphviz", json={})
    assert r.status_code == 400
