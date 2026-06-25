from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermeshq.core.security import get_current_user
from hermeshq.routers.desktop_runtime import router
from hermeshq.services.desktop_runtime import capabilities_for_role


def _client_for_user(user: SimpleNamespace | None = None) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")
    if user is not None:
        app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_provision_requires_auth() -> None:
    client = _client_for_user()

    response = client.post(
        "/api/desktop/provision",
        json={"client": "headmaster_desktop", "version": "0.2.1", "platform": "win32"},
    )

    assert response.status_code == 401


def test_inactive_user_cannot_provision() -> None:
    from hermeshq.core.security import get_current_user as auth_dependency

    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def inactive_dependency():
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication credentials")

    app.dependency_overrides[auth_dependency] = inactive_dependency
    client = TestClient(app)

    response = client.post(
        "/api/desktop/provision",
        json={"client": "headmaster_desktop", "version": "0.2.1", "platform": "win32"},
    )

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("admin", {"chat", "terminal", "local_files", "cowork", "model_selection", "runtime_settings"}),
        ("user", {"chat", "terminal", "local_files", "cowork", "model_selection", "runtime_settings"}),
        ("staff", {"chat", "terminal", "local_files", "cowork", "model_selection", "runtime_settings"}),
        ("student", {"chat", "cowork", "model_selection"}),
        ("unknown", {"chat", "terminal", "local_files", "cowork", "model_selection", "runtime_settings"}),
    ],
)
def test_role_to_capability_mapping(role: str, expected: set[str]) -> None:
    assert set(capabilities_for_role(role)) == expected


def test_runtime_validation_allows_permitted_capability() -> None:
    client = _client_for_user(SimpleNamespace(id="user-1", username="demo1", role="user", is_active=True))

    response = client.post(
        "/api/desktop/runtime/validate",
        json={"runtime_id": "local-hermes", "requested_capability": "terminal"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["allowed"] is True
    assert "terminal" in data["capabilities"]
    assert data["ttl_seconds"] == 300


def test_runtime_validation_rejects_forbidden_capability() -> None:
    client = _client_for_user(SimpleNamespace(id="student-1", username="student", role="student", is_active=True))

    response = client.post(
        "/api/desktop/runtime/validate",
        json={"runtime_id": "local-hermes", "requested_capability": "terminal"},
    )

    assert response.status_code == 403
