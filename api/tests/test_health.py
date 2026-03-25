"""Tests for /healthcheck endpoint."""


def test_healthcheck_returns_200(client):
    r = client.get("/healthcheck")
    assert r.status_code == 200


def test_healthcheck_shape(client):
    data = client.get("/healthcheck").json()
    assert data["success"] is True
    assert "renderer" in data
    assert "version" in data


def test_healthcheck_version(client):
    data = client.get("/healthcheck").json()
    assert data["version"] == "1.0.0"
