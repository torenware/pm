import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.auth import SESSION_COOKIE, Session, SessionStore, require_session

DEFAULT_STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_SESSION_SECRET = secrets.token_hex(32)


class LoginRequest(BaseModel):
    username: str
    password: str


def create_app(
    static_dir: Path | None = None,
    session_secret: str = DEFAULT_SESSION_SECRET,
    now: Callable[[], float] = time.time,
    session_max_age: int = 8 * 60 * 60,
) -> FastAPI:
    application = FastAPI(title="Project Management MVP")
    sessions = SessionStore(session_secret, now, session_max_age)
    authenticated = require_session(sessions)

    @application.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/login")
    def login(credentials: LoginRequest, response: Response) -> dict[str, str]:
        if credentials.username != "user" or credentials.password != "password":
            response.status_code = 401
            return {"detail": "Invalid username or password"}

        response.set_cookie(
            SESSION_COOKIE,
            sessions.create(credentials.username),
            max_age=sessions.max_age,
            httponly=True,
            secure=False,
            samesite="lax",
        )
        return {"username": credentials.username}

    @application.post("/api/logout", status_code=204)
    def logout(
        response: Response,
        pm_session: str | None = Cookie(default=None),
    ) -> None:
        sessions.delete(pm_session)
        response.delete_cookie(SESSION_COOKIE, httponly=True, samesite="lax")

    @application.get("/api/session")
    def current_session(session: Session = Depends(authenticated)) -> dict[str, str]:
        return {"username": session.username}

    @application.get("/api/protected")
    def protected(session: Session = Depends(authenticated)) -> dict[str, str]:
        return {"username": session.username}

    application.mount(
        "/",
        StaticFiles(directory=static_dir or DEFAULT_STATIC_DIR, html=True),
        name="frontend",
    )
    return application


app = create_app(
    Path(os.environ.get("STATIC_DIR", DEFAULT_STATIC_DIR)),
    os.environ.get("SESSION_SECRET", DEFAULT_SESSION_SECRET),
)