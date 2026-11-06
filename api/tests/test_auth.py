"""Office sign-in, through the HTTP API."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from sqlalchemy import select

from app import auth
from app.auth import DEMO_EMAILS, SESSION_COOKIE
from app.config import settings
from app.models import Role, User
from tests.factories import make_user

PASSWORD = "correct horse battery"


def sign_in(client, user: User, password: str = PASSWORD):
    return client.post("/api/auth/login", json={"email": user.email, "password": password})


def session_cookie_header(response) -> str:
    return next(
        header
        for header in response.headers.get_list("set-cookie")
        if header.startswith(SESSION_COOKIE)
    )


def token_for(user: User, secret: str = settings.session_secret, **claims) -> str:
    now = datetime.now(UTC)
    values = {"sub": str(user.id), "iat": now, "exp": now + timedelta(minutes=5)}
    return jwt.encode(values | claims, secret, algorithm="HS256")


def test_right_password_signs_in_and_me_returns_the_user(api_client, db):
    user = make_user(db, Role.OPERATIONS_HEAD, password=PASSWORD)

    response = sign_in(api_client, user)

    assert response.status_code == 200
    assert response.json() == {"name": user.name, "email": user.email, "role": "operations_head"}
    assert api_client.get("/api/auth/me").json()["email"] == user.email


def test_email_is_matched_whatever_its_case_or_surrounding_spaces(api_client, db):
    user = make_user(db, password=PASSWORD)

    response = api_client.post(
        "/api/auth/login", json={"email": f"  {user.email.upper()} ", "password": PASSWORD}
    )

    assert response.status_code == 200


def test_wrong_password_and_unknown_email_get_the_same_refusal(api_client, db):
    user = make_user(db, password=PASSWORD)

    wrong_password = sign_in(api_client, user, password="not the password")
    unknown_email = api_client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert "set-cookie" not in wrong_password.headers


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"email": "a@example.com"},
        {"email": "", "password": "x"},
        {"email": "a@example.com", "password": "x" * 129},
    ],
)
def test_malformed_sign_in_is_rejected_by_validation(api_client, body):
    assert api_client.post("/api/auth/login", json=body).status_code == 422


def test_password_is_stored_hashed(db):
    user = make_user(db, password=PASSWORD)

    assert PASSWORD not in user.password_hash
    assert user.password_hash.startswith("$argon2")


def test_session_is_an_http_only_short_lived_cookie(api_client, db):
    cookie = session_cookie_header(sign_in(api_client, make_user(db, password=PASSWORD)))

    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Max-Age=28800" in cookie  # Eight hours.


def test_cookie_is_secure_when_the_web_app_is_on_https(api_client, db, monkeypatch):
    monkeypatch.setattr(settings, "web_origin", "https://landed.example.com")

    cookie = session_cookie_header(sign_in(api_client, make_user(db, password=PASSWORD)))

    assert "Secure" in cookie


def test_sign_out_ends_the_browser_session(api_client, db):
    sign_in(api_client, make_user(db, password=PASSWORD))

    response = api_client.post("/api/auth/logout")

    assert response.status_code == 204
    assert api_client.get("/api/auth/me").status_code == 401


def test_sign_out_works_with_no_session(api_client):
    assert api_client.post("/api/auth/logout").status_code == 204


@pytest.mark.parametrize(
    "make_token",
    [
        lambda user: "not a token",
        lambda user: token_for(user, secret="s" * 40),
        lambda user: token_for(user, exp=datetime.now(UTC) - timedelta(seconds=1)),
    ],
    ids=["garbage", "signed with another secret", "expired"],
)
def test_bad_session_tokens_count_as_not_signed_in(api_client, db, make_token):
    user = make_user(db)

    response = api_client.get(
        "/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={make_token(user)}"}
    )

    assert response.status_code == 401


def test_a_token_that_names_its_own_algorithm_is_refused(api_client, db):
    user = make_user(db)
    unsigned = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) + timedelta(minutes=5)},
        key=None,
        algorithm="none",
    )

    response = api_client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={unsigned}"})

    assert response.status_code == 401


def test_session_ends_when_the_user_is_deleted(api_client, db):
    user = make_user(db)
    token = token_for(user)
    db.delete(user)
    db.commit()

    response = api_client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={token}"})

    assert response.status_code == 401


def test_a_changed_role_applies_to_the_next_request(api_client, db):
    user = make_user(db, Role.BILLING_EXECUTIVE, password=PASSWORD)
    sign_in(api_client, user)

    user.role = Role.OPERATIONS_HEAD
    db.commit()

    assert api_client.get("/api/auth/me").json()["role"] == "operations_head"


def test_options_report_demo_mode(api_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    assert api_client.get("/api/auth/options").json() == {"demo_mode": True}

    monkeypatch.setattr(settings, "demo_mode", False)
    assert api_client.get("/api/auth/options").json() == {"demo_mode": False}


def test_demo_login_does_not_exist_with_demo_mode_off(api_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", False)

    response = api_client.post("/api/auth/demo-login", json={"role": "billing_executive"})

    assert response.status_code == 404
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("role", list(Role))
def test_demo_login_signs_in_as_the_seeded_user_for_that_role(
    empty_db, api_client, db, monkeypatch, role
):
    monkeypatch.setattr(settings, "demo_mode", True)
    make_user(db, role, email=DEMO_EMAILS[role])

    response = api_client.post("/api/auth/demo-login", json={"role": role})

    assert response.status_code == 200
    assert api_client.get("/api/auth/me").json()["role"] == role


def test_demo_login_is_404_when_the_seed_has_not_run(empty_db, api_client, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)

    response = api_client.post("/api/auth/demo-login", json={"role": "billing_executive"})

    assert response.status_code == 404


def test_unknown_email_still_runs_the_hash_check(api_client, monkeypatch):
    # Without this an attacker could tell real emails from fake ones by response time.
    checked = []
    real_verify = auth.hasher.verify

    def record_verify(stored_hash, password):
        checked.append(stored_hash)
        return real_verify(stored_hash, password)

    monkeypatch.setattr(auth, "hasher", type("Spy", (), {"verify": staticmethod(record_verify)}))

    api_client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})

    assert checked == [auth.UNKNOWN_USER_HASH]


def test_seeded_demo_password_signs_in(empty_db, api_client, db):
    from seed import DEMO_PASSWORD, seed

    seed(db)
    db.commit()
    user = db.scalar(select(User).where(User.email == DEMO_EMAILS[Role.BILLING_EXECUTIVE]))

    assert sign_in(api_client, user, password=DEMO_PASSWORD).status_code == 200
