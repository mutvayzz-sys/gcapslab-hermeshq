"""Tests for the admin user-update endpoint's username/email linking support."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hermeshq.core.security import require_admin
from hermeshq.database import get_db_session
from hermeshq.routers.users import router


def _user(id_="u1", username="alice", email=None, role="user", is_active=True):
    return SimpleNamespace(
        id=id_,
        username=username,
        email=email,
        display_name=username,
        role=role,
        is_active=is_active,
        avatar_filename=None,
        updated_at=None,
        telegram_id=None,
        whatsapp_user=None,
        teams_id=None,
        google_chat_email=None,
        kapso_id=None,
        kapso_number=None,
    )


class FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return SimpleNamespace(all=lambda: self._value or [])


class FakeDb:
    """Minimal AsyncSession stand-in: `users` maps id -> user, `by_field` answers uniqueness checks."""

    def __init__(self, users, taken_usernames=(), taken_emails=()):
        self.users = users
        self.taken_usernames = set(taken_usernames)
        self.taken_emails = set(taken_emails)

    async def get(self, _model, user_id):
        return self.users.get(user_id)

    async def execute(self, stmt):
        # update_user() issues `select(User).where(User.username == x)` or `.email == x` for
        # uniqueness checks — read the bound parameter value back off the compiled statement
        # rather than string-matching SQL text.
        params = stmt.compile().params
        column = stmt.whereclause.left.name
        value = next(iter(params.values()), None)
        taken = self.taken_usernames if column == "username" else self.taken_emails
        return FakeResult(SimpleNamespace() if value in taken else None)

    async def commit(self):
        return None

    async def refresh(self, _user):
        return None


def _client(db: FakeDb, admin) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api")

    async def _fake_db_session():
        yield db

    app.dependency_overrides[get_db_session] = _fake_db_session
    app.dependency_overrides[require_admin] = lambda: admin
    return TestClient(app)


def test_admin_can_relink_username_and_email():
    admin = _user(id_="admin-1", username="admin", role="admin")
    target = _user(id_="u2", username="bootstrap-admin", email=None, role="admin")
    db = FakeDb(users={"admin-1": admin, "u2": target})
    client = _client(db, admin)

    response = client.put(
        "/api/users/u2",
        json={"username": "admin@gcaplabs.com", "email": "admin@gcaplabs.com"},
    )

    assert response.status_code == 200, response.text
    assert target.username == "admin@gcaplabs.com"
    assert target.email == "admin@gcaplabs.com"


def test_username_conflict_returns_409():
    admin = _user(id_="admin-1", username="admin", role="admin")
    target = _user(id_="u2", username="bob")
    db = FakeDb(
        users={"admin-1": admin, "u2": target},
        taken_usernames={"admin@gcaplabs.com"},
    )
    client = _client(db, admin)

    response = client.put("/api/users/u2", json={"username": "admin@gcaplabs.com"})

    assert response.status_code == 409
    assert target.username == "bob"


def test_email_conflict_returns_409():
    admin = _user(id_="admin-1", username="admin", role="admin")
    target = _user(id_="u2", username="bob", email=None)
    db = FakeDb(
        users={"admin-1": admin, "u2": target},
        taken_emails={"admin@gcaplabs.com"},
    )
    client = _client(db, admin)

    response = client.put("/api/users/u2", json={"email": "admin@gcaplabs.com"})

    assert response.status_code == 409
    assert target.email is None


def test_self_username_change_does_not_trip_demote_guard():
    admin = _user(id_="admin-1", username="admin", role="admin")
    db = FakeDb(users={"admin-1": admin})
    client = _client(db, admin)

    response = client.put("/api/users/admin-1", json={"username": "admin@gcaplabs.com"})

    assert response.status_code == 200, response.text
    assert admin.username == "admin@gcaplabs.com"
