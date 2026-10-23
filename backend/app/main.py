"""CodeMap FastAPI application."""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .auth import (
    Credentials,
    RefreshToken,
    SignUpCredentials,
    bearer_token,
    current_user,
    supabase_request,
)
from .config import allowed_origins

app = FastAPI(title="CodeMap API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Report that the API process is running."""
    return {"status": "ok"}


@app.post("/api/auth/signup")
def signup(credentials: SignUpCredentials) -> dict[str, Any]:
    """Create a Supabase user and return a session when confirmation is disabled."""
    return supabase_request(
        "signup",
        method="POST",
        payload={
            "email": credentials.email,
            "password": credentials.password,
            "data": {"full_name": credentials.full_name},
        },
    )


@app.post("/api/auth/login")
def login(credentials: Credentials) -> dict[str, Any]:
    """Exchange email and password for a Supabase JWT session."""
    return supabase_request(
        "token?grant_type=password",
        method="POST",
        payload=credentials.model_dump(mode="json"),
    )


@app.post("/api/auth/refresh")
def refresh(token: RefreshToken) -> dict[str, Any]:
    """Exchange a refresh token for a fresh JWT session."""
    return supabase_request(
        "token?grant_type=refresh_token",
        method="POST",
        payload=token.model_dump(),
    )


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(token: Annotated[str, Depends(bearer_token)]) -> Response:
    """Revoke the active Supabase session."""
    supabase_request("logout", method="POST", access_token=token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/auth/me")
def me(user: Annotated[dict[str, Any], Depends(current_user)]) -> dict[str, Any]:
    """Return the authenticated Supabase user."""
    return user
