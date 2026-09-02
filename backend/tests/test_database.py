import sqlite3
from pathlib import Path

from app.database import Database


def test_initialize_creates_database_and_seeds_mvp_data(tmp_path: Path) -> None:
    database_path = tmp_path / "nested" / "pm.db"
    database = Database(database_path)

    database.initialize()

    assert database_path.is_file()
    with database.connect() as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == 1
        assert connection.execute("SELECT username FROM users").fetchone()[0] == "user"
        assert connection.execute("SELECT title FROM boards").fetchone()[0] == "Kanban Studio"
        rows = connection.execute(
            "SELECT column_key FROM board_columns ORDER BY position"
        ).fetchall()
        assert [row["column_key"] for row in rows] == [
            "backlog",
            "discovery",
            "progress",
            "review",
            "done",
        ]


def test_initialize_is_idempotent_and_preserves_existing_data(tmp_path: Path) -> None:
    database = Database(tmp_path / "pm.db")
    database.initialize()
    with database.connect() as connection:
        connection.execute("UPDATE boards SET title = 'Changed'")

    database.initialize()

    with database.connect() as connection:
        assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM boards").fetchone()[0] == 1
        assert connection.execute("SELECT count(*) FROM board_columns").fetchone()[0] == 5
        assert connection.execute("SELECT title FROM boards").fetchone()[0] == "Changed"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_database_enforces_foreign_keys_on_every_connection(tmp_path: Path) -> None:
    database = Database(tmp_path / "pm.db")
    database.initialize()

    with database.connect() as connection:
        try:
            connection.execute(
                "INSERT INTO boards VALUES (?, ?, ?, ?, ?)",
                ("bad-board", "missing-user", "Bad", "now", "now"),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("foreign key violation was accepted")