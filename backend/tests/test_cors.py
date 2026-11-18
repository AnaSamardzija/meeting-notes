"""CORS: only the addresses in CORS_ORIGINS may send requests with the login
cookie, and "*" is never accepted."""

import pytest
from pydantic import ValidationError

from app.config import Settings, settings


def test_allowed_origin_may_send_the_login_cookie(anonymous_client):
    origin = settings.cors_origin_list[0]

    response = anonymous_client.get("/api/health", headers={"Origin": origin})

    assert response.headers["access-control-allow-origin"] == origin
    assert response.headers["access-control-allow-credentials"] == "true"


def test_other_origin_is_not_allowed(anonymous_client):
    response = anonymous_client.get(
        "/api/health", headers={"Origin": "https://evil.example"}
    )

    # Without this header the browser does not give the answer to the page
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize(
    "cors_origins", ["*", "http://localhost:5173,*", "http://localhost:5173,"]
)
def test_wildcard_and_empty_origins_are_refused(cors_origins):
    with pytest.raises(ValidationError):
        Settings(cors_origins=cors_origins)
