"""Small Supabase Auth HTTP client and FastAPI authentication helpers."""

import json
import ssl
from typing import Annotated, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import certifi
from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from .config import required_setting


class Credentials(BaseModel):
    """Email and password submitted by the login form."""

    email: EmailStr
    password: str = Field(min_length=6)


class SignUpCredentials(Credentials):
    """Account registration fields."""

    full_name: str = Field(min_length=1, max_length=100)


class RefreshToken(BaseModel):
    """Refresh token submitted when an access token expires."""

    refresh_token: str = Field(min_length=1)


def supabase_request(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    """Call a Supabase Auth endpoint and return its JSON response."""
    base_url = required_setting("SUPABASE_URL").rstrip("/")
    api_key = required_setting("SUPABASE_PUBLISHABLE_KEY")
    headers = {"apikey": api_key, "Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{base_url}/auth/v1/{path}", data=body, headers=headers, method=method
    )

    try:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with urlopen(request, timeout=10, context=ssl_context) as response:
            return json.loads(response.read().decode())
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode()).get(
                "msg", "Authentication request failed"
            )
        except (json.JSONDecodeError, UnicodeDecodeError):
            detail = "Authentication request failed"
        raise HTTPException(status_code=error.code, detail=detail) from error
    except URLError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Authentication service is unavailable: {error.reason}",
        ) from error


def bearer_token(authorization: Annotated[str | None, Header()] = None) -> str:
    """Extract a JWT from an Authorization Bearer header."""
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def current_user(
    token: Annotated[str, Depends(bearer_token)],
) -> dict[str, Any]:
    """Validate a JWT with Supabase and return its current user."""
    return supabase_request("user", access_token=token)
