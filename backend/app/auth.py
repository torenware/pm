import hashlib
import hmac
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import Cookie, HTTPException, status

from app.database import Database

SESSION_COOKIE = "pm_session"
SESSION_MAX_AGE = 8 * 60 * 60


@dataclass(frozen=True)
class Session:
    username: str
    expires_at: float


class SessionStore:
    def __init__(
        self,
        database: Database,
        secret: str,
        now: Callable[[], float] = time.time,
        max_age: int = SESSION_MAX_AGE,
    ) -> None:
        self._database = database
        self._secret = secret.encode()
        self._now = now
        self.max_age = max_age

    def create(self, username: str) -> str:
        session_id = secrets.token_urlsafe(32)
        created_at = self._timestamp(self._now())
        expires_at = self._timestamp(self._now() + self.max_age)
        with self._database.session() as connection:
            connection.execute(
                "DELETE FROM sessions WHERE expires_at <= ?",
                (created_at,),
            )
            user = connection.execute(
                "SELECT id FROM users WHERE username = ?",
                (username,),
            ).fetchone()
            if user is None:
                raise ValueError("Unknown session user")
            connection.execute(
                "INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (self._hash(session_id), user["id"], created_at, expires_at),
            )
        return self._sign(session_id)

    def get(self, cookie: str | None) -> Session | None:
        session_id = self._verify(cookie)
        if session_id is None:
            return None

        now = self._timestamp(self._now())
        with self._database.session() as connection:
            row = connection.execute(
                "SELECT users.username, sessions.expires_at FROM sessions JOIN users ON users.id = sessions.user_id WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
                (self._hash(session_id), now),
            ).fetchone()
            if row is None:
                connection.execute(
                    "DELETE FROM sessions WHERE token_hash = ?",
                    (self._hash(session_id),),
                )
                return None
        expires_at = datetime.fromisoformat(row["expires_at"]).timestamp()
        return Session(username=row["username"], expires_at=expires_at)

    def delete(self, cookie: str | None) -> None:
        session_id = self._verify(cookie)
        if session_id is not None:
            with self._database.session() as connection:
                connection.execute(
                    "DELETE FROM sessions WHERE token_hash = ?",
                    (self._hash(session_id),),
                )

    @staticmethod
    def _timestamp(value: float) -> str:
        return datetime.fromtimestamp(value, UTC).isoformat()

    @staticmethod
    def _hash(session_id: str) -> str:
        return hashlib.sha256(session_id.encode()).hexdigest()

    def _sign(self, session_id: str) -> str:
        signature = hmac.HMAC(self._secret, session_id.encode(), hashlib.sha256).hexdigest()
        return f"{session_id}.{signature}"

    def _verify(self, cookie: str | None) -> str | None:
        if cookie is None:
            return None
        try:
            session_id, signature = cookie.rsplit(".", 1)
        except ValueError:
            return None
        expected = hmac.HMAC(
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