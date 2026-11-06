"""Who can reach what. Every API route has to be listed here, or the first test fails.

When a ticket adds an office route, add it to OFFICE_ROUTES with the roles allowed to use it.
Driver routes get their own list in the ticket that adds them.
"""

import pytest
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
NO_ID = "00000000-0000-0000-0000-000000000000"
BILLING_ONLY = {Role.BILLING_EXECUTIVE}

OFFICE_ROUTES = [
    ("GET", "/api/auth/me", "/api/auth/me", set(Role)),
    ("GET", "/api/review/queue", "/api/review/queue", BILLING_ONLY),
    ("GET", f"/api/review/trips/{NO_ID}", "/api/review/trips/{trip_id}", BILLING_ONLY),
    (
        "GET",
        f"/api/review/attempts/{NO_ID}/photo",
        "/api/review/attempts/{attempt_id}/photo",
        BILLING_ONLY,
    ),
    (
        "PATCH",
        f"/api/review/trips/{NO_ID}/fields/lr_number",
        "/api/review/trips/{trip_id}/fields/{field}",
        BILLING_ONLY,
    ),
    *(
        ("POST", f"/api/review/trips/{NO_ID}/{action}", f"/api/review/trips/{{trip_id}}/{action}", BILLING_ONLY)
        for action in ("approve", "retake", "dispute", "pull-back", "reveal")
    ),
    ("GET", "/api/billing/queue", "/api/billing/queue", BILLING_ONLY),
    ("GET", "/api/billing/exports", "/api/billing/exports", BILLING_ONLY),
    ("POST", "/api/billing/exports", "/api/billing/exports", BILLING_ONLY),
    *(
        ("GET", f"/api/billing/exports/{NO_ID}/{file}", f"/api/billing/exports/{{batch_id}}/{file}", BILLING_ONLY)
        for file in ("xml", "photos")
    ),
    ("GET", "/api/dashboard", "/api/dashboard", set(Role)),
    ("GET", "/api/dashboard/counts", "/api/dashboard/counts", set(Role)),
    (
        "POST",
        f"/api/dashboard/trips/{NO_ID}/resend-link",
        "/api/dashboard/trips/{trip_id}/resend-link",
        set(Role),
    ),
]

# Each of these takes a driver token, and opens only that token's trip. test_driver.py covers
# valid tokens; here a route only has to refuse a request without one.
DRIVER_ROUTES = [
    ("GET", "/api/driver/trip", "/api/driver/trip"),
    ("POST", "/api/driver/attempts", "/api/driver/attempts"),
    (
        "GET",
        "/api/driver/attempts/00000000-0000-0000-0000-000000000000",
        "/api/driver/attempts/{attempt_id}",
    ),
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
