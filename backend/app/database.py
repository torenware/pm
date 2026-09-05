import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS = {
    1: (
        "CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL COLLATE NOCASE UNIQUE, created_at TEXT NOT NULL)",
        "CREATE TABLE boards (id TEXT PRIMARY KEY, owner_user_id TEXT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE, title TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)",
        "CREATE TABLE board_columns (id TEXT PRIMARY KEY, board_id TEXT NOT NULL REFERENCES boards(id) ON DELETE CASCADE, column_key TEXT NOT NULL CHECK (column_key IN ('backlog', 'discovery', 'progress', 'review', 'done')), title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 80), position INTEGER NOT NULL CHECK (position BETWEEN 0 AND 4), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE (board_id, id), UNIQUE (board_id, column_key), UNIQUE (board_id, position))",
        "CREATE TABLE cards (id TEXT PRIMARY KEY, board_id TEXT NOT NULL, column_id TEXT NOT NULL, title TEXT NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 200), details TEXT NOT NULL DEFAULT '', position INTEGER NOT NULL CHECK (position >= 0), created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY (board_id, column_id) REFERENCES board_columns(board_id, id) ON DELETE CASCADE, UNIQUE (column_id, position))",
        "CREATE TABLE sessions (token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, created_at TEXT NOT NULL, expires_at TEXT NOT NULL, CHECK (expires_at > created_at))",
        "CREATE INDEX cards_board_id_idx ON cards(board_id)",
        "CREATE INDEX sessions_user_id_idx ON sessions(user_id)",
        "CREATE INDEX sessions_expires_at_idx ON sessions(expires_at)",
    )
}

MVP_USER_ID = "00000000-0000-4000-8000-000000000001"
MVP_BOARD_ID = "10000000-0000-4000-8000-000000000001"
FIXED_COLUMNS = (
    ("20000000-0000-4000-8000-000000000001", "backlog", "Backlog", 0),
    ("20000000-0000-4000-8000-000000000002", "discovery", "Discovery", 1),
    ("20000000-0000-4000-8000-000000000003", "progress", "In Progress", 2),
    ("20000000-0000-4000-8000-000000000004", "review", "Review", 3),
    ("20000000-0000-4000-8000-000000000005", "done", "Done", 4),
)


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def session(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self.connect()
        try:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
            )
            applied = {
                row["version"]
                for row in connection.execute("SELECT version FROM schema_migrations")
            }
            for version, statements in MIGRATIONS.items():
                if version in applied:
                    continue
                for statement in statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (version, utc_now()),
                )
            self._seed(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _seed(self, connection: sqlite3.Connection) -> None:
        timestamp = utc_now()
        connection.execute(
            "INSERT OR IGNORE INTO users (id, username, created_at) VALUES (?, 'user', ?)",
            (MVP_USER_ID, timestamp),
        )
        connection.execute(
            "INSERT OR IGNORE INTO boards (id, owner_user_id, title, created_at, updated_at) VALUES (?, ?, 'Kanban Studio', ?, ?)",
            (MVP_BOARD_ID, MVP_USER_ID, timestamp, timestamp),
        )
        connection.executemany(
            "INSERT OR IGNORE INTO board_columns (id, board_id, column_key, title, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (column_id, MVP_BOARD_ID, key, title, position, timestamp, timestamp)
                for column_id, key, title, position in FIXED_COLUMNS
            ],
        )