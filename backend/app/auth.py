import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Cookie, HTTPException, status

SESSION_COOKIE = "pm_session"
SESSION_MAX_AGE = 8 * 60 * 60


@dataclass(frozen=True)
class Session:
    username: str
    expires_at: float


class SessionStore:
    def __init__(
        self,
        secret: str,
        now: Callable[[], float] = time.time,
        max_age: int = SESSION_MAX_AGE,
    ) -> None:
        self._secret = secret.encode()
        self._now = now
        self.max_age = max_age
        self._sessions: dict[str, Session] = {}

    def create(self, username: str) -> str:
        session_id = secrets.token_urlsafe(32)
        self._sessions[session_id] = Session(
            username=username,
            expires_at=self._now() + self.max_age,
        )
        return self._sign(session_id)

    def get(self, cookie: str | None) -> Session | None:
        session_id = self._verify(cookie)
        if session_id is None:
            return None

        session = self._sessions.get(session_id)
        if session is None:
            return None
        if session.expires_at <= self._now():
            self._sessions.pop(session_id, None)
            return None
        return session

    def delete(self, cookie: str | None) -> None:
        session_id = self._verify(cookie)
        if session_id is not None:
            self._sessions.pop(session_id, None)

    def _sign(self, session_id: str) -> str:
        signature = hmac.new(self._secret, session_id.encode(), hashlib.sha256).hexdigest()
        return f"{session_id}.{signature}"

    def _verify(self, cookie: str | None) -> str | None:
        if cookie is None:
            return None
        try:
            session_id, signature = cookie.rsplit(".", 1)
        except ValueError:
            return None
        expected = hmac.new(
            self._secret,
            session_id.encode(),
            hashlib.sha256,
        ).hexdigest()
        return session_id if hmac.compare_digest(signature, expected) else None


def require_session(store: SessionStore):
    def dependency(pm_session: str | None = Cookie(default=None)) -> Session:
        session = store.get(pm_session)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        return session

    return dependency