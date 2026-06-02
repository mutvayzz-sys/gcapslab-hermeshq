"""Tests for core.structured_errors – StructuredErrorMiddleware."""
from __future__ import annotations

import pytest
from unittest.mock import patch
from starlette.testclient import TestClient
from fastapi import FastAPI, HTTPException


@pytest.fixture()
def app():
    _app = FastAPI()

    @_app.get("/ok")
    async def ok():
        return {"status": "ok"}

    @_app.get("/raise-http")
    async def raise_http():
        raise HTTPException(status_code=403, detail="Forbidden zone")

    @_app.get("/raise-unhandled")
    async def raise_unhandled():
        raise RuntimeError("boom")

    return _app


class TestStructuredErrorMiddleware:
    def test_success_response_unchanged(self, app):
        from hermeshq.core.structured_errors import StructuredErrorMiddleware
        app.add_middleware(StructuredErrorMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/ok")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_http_exception_has_json_detail(self, app):
        from hermeshq.core.structured_errors import StructuredErrorMiddleware
        app.add_middleware(StructuredErrorMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/raise-http")
        assert resp.status_code == 403
        data = resp.json()
        assert "detail" in data
        assert data["detail"] == "Forbidden zone"

    def test_unhandled_exception_returns_500(self, app):
        from hermeshq.core.structured_errors import StructuredErrorMiddleware
        app.add_middleware(StructuredErrorMiddleware)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.get("/raise-unhandled")
        assert resp.status_code == 500
        data = resp.json()
        assert data["detail"] == "Internal server error"
        assert data["status_code"] == 500
        assert "/raise-unhandled" in data["path"]

    def test_error_body_structure(self):
        from hermeshq.core.structured_errors import _error_body
        body = _error_body("Not found", 404, "/api/agents")
        assert body == {
            "detail": "Not found",
            "status_code": 404,
            "path": "/api/agents",
        }

    def test_error_body_with_extra(self):
        from hermeshq.core.structured_errors import _error_body
        body = _error_body("Bad", 400, "/x", extra={"field": "name"})
        assert body["field"] == "name"
        assert body["detail"] == "Bad"
