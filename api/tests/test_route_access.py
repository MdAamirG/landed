"""Who can reach what. Every API route has to be listed here, or the first test fails.

When a ticket adds an office route, add it to OFFICE_ROUTES with the roles allowed to use it.
Driver routes get their own list in the ticket that adds them.
"""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import require_role
from app.main import app
from app.models import Role
from tests.factories import make_user

PUBLIC_ROUTES = {
    ("GET", "/api/ping"),
    ("GET", "/api/health"),
    ("GET", "/api/auth/options"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/demo-login"),
    ("POST", "/api/auth/logout"),
}

# (method, path with any IDs filled in, the path as the router declares it, roles allowed)
OFFICE_ROUTES = [
    ("GET", "/api/auth/me", "/api/auth/me", set(Role)),
]

# Each of these takes a driver token, and opens only that token's trip. test_driver.py covers
# valid tokens; here a route only has to refuse a request without one.
DRIVER_ROUTES = [
    ("GET", "/api/driver/trip", "/api/driver/trip"),
]

PASSWORD = "correct horse battery"


def signed_in_as(client, db, role: Role) -> None:
    user = make_user(db, role, password=PASSWORD)
    response = client.post("/api/auth/login", json={"email": user.email, "password": PASSWORD})
    assert response.status_code == 200


def test_every_api_route_is_listed_here():
    declared = {
        (method.upper(), path)
        for path, operations in app.openapi()["paths"].items()
        for method in operations
    }
    listed = (
        PUBLIC_ROUTES
        | {(method, path) for method, _, path, _ in OFFICE_ROUTES}
        | {(method, path) for method, _, path in DRIVER_ROUTES}
    )

    assert declared == listed


@pytest.mark.parametrize(("method", "url", "_path", "_roles"), OFFICE_ROUTES)
def test_office_routes_refuse_anyone_not_signed_in(api_client, method, url, _path, _roles):
    assert api_client.request(method, url).status_code == 401


@pytest.mark.parametrize(("method", "url", "_path", "allowed"), OFFICE_ROUTES)
@pytest.mark.parametrize("role", list(Role))
def test_office_routes_check_the_role(api_client, db, role, method, url, _path, allowed):
    signed_in_as(api_client, db, role)

    response = api_client.request(method, url)

    if role in allowed:
        assert response.status_code not in (401, 403)
    else:
        assert response.status_code == 403


@pytest.mark.parametrize(("method", "url", "_path"), DRIVER_ROUTES)
def test_driver_routes_refuse_a_request_without_a_token(api_client, method, url, _path):
    assert api_client.request(method, url).status_code == 401


def test_an_office_session_does_not_open_a_driver_route(api_client, db):
    signed_in_as(api_client, db, Role.BILLING_EXECUTIVE)

    for method, url, _path in DRIVER_ROUTES:
        assert api_client.request(method, url).status_code == 401


def test_require_role_gives_403_to_the_wrong_role_and_lets_the_right_one_through(api_client, db):
    # No real route is limited to one role yet, so this builds one. It runs the real dependency
    # against a real session cookie. Once such a route exists, OFFICE_ROUTES covers it as well.
    limited = FastAPI()

    @limited.get("/billing-only", dependencies=[Depends(require_role(Role.BILLING_EXECUTIVE))])
    def billing_only() -> dict[str, bool]:
        return {"ok": True}

    signed_in_as(api_client, db, Role.OPERATIONS_HEAD)
    with TestClient(limited, cookies=dict(api_client.cookies)) as client:
        assert client.get("/billing-only").status_code == 403

    api_client.cookies.clear()
    signed_in_as(api_client, db, Role.BILLING_EXECUTIVE)
    with TestClient(limited, cookies=dict(api_client.cookies)) as client:
        assert client.get("/billing-only").status_code == 200

    with TestClient(limited) as client:
        assert client.get("/billing-only").status_code == 401
