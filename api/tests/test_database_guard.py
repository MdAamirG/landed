"""The suite empties tables, so it must refuse to run against anything but the test branch.

These tests run pytest itself, because the thing being proved is that the suite stops.
The hosts are fake (.invalid never resolves), so a broken guard still can't reach a real database.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

API_DIR = Path(__file__).resolve().parent.parent

DIRECT = "postgresql://user:pass@ep-app.neon.invalid/neondb"
POOLED = "postgresql://user:pass@ep-app-pooler.neon.invalid/neondb"
OTHER_BRANCH = "postgresql://user:pass@ep-test.neon.invalid/neondb"


def run_suite(test_url: str, direct: str = DIRECT, pooled: str = POOLED):
    """Collect the suite with these URLs. Empty strings stop .env filling them in."""
    env = {
        **os.environ,
        "DATABASE_URL_TEST": test_url,
        "DATABASE_URL": direct,
        "DATABASE_URL_POOLED": pooled,
    }
    # --collect-only: the guard runs at startup, and no test here should run for real.
    return subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_refuses_when_test_url_is_unset():
    result = run_suite(test_url="")

    assert result.returncode == 2
    assert "DATABASE_URL_TEST is not set" in result.stdout + result.stderr


@pytest.mark.parametrize(
    "test_url",
    [
        pytest.param(DIRECT, id="same host as DATABASE_URL"),
        pytest.param(POOLED, id="same host as DATABASE_URL_POOLED"),
        pytest.param(DIRECT.replace("ep-app", "EP-APP"), id="same host in another case"),
    ],
)
def test_refuses_when_test_host_matches_an_app_host(test_url):
    result = run_suite(test_url=test_url)

    assert result.returncode == 2
    assert "same host" in result.stdout + result.stderr


def test_refuses_the_pooled_host_of_the_app_database():
    # Only the direct app URL is configured here, but this is the same Neon branch.
    result = run_suite(test_url=POOLED, pooled="")

    assert result.returncode == 2
    assert "same host" in result.stdout + result.stderr


def test_allows_a_separate_host():
    result = run_suite(test_url=OTHER_BRANCH)

    assert result.returncode == 0, result.stdout + result.stderr
