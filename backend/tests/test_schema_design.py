import json
import sqlite3
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parents[2] / "docs" / "schema.json"


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text())


def create_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    for statement in load_schema()["ddl"]:
        connection.execute(statement)
    return connection


def insert_samples(connection: sqlite3.Connection) -> None:
    samples = load_schema()["sampleRecords"]
    for table in ("users", "boards", "board_columns", "cards", "sessions"):
        for record in samples[table]:
            columns = ", ".join(record)
            placeholders = ", ".join("?" for _ in record)
            connection.execute(
                f"INSERT INTO {table} ({columns}) VALUES ({placeholders})",
                tuple(record.values()),
            )
    connection.commit()


def test_schema_json_and_sample_records_are_valid() -> None:
    schema = load_schema()
    connection = create_database()
    insert_samples(connection)

    assert schema["schemaVersion"] == 1
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM boards").fetchone()[0] == 1
    assert connection.execute("SELECT count(*) FROM board_columns").fetchone()[0] == 5
    assert connection.execute("SELECT count(*) FROM cards").fetchone()[0] == 2
    assert connection.execute("SELECT count(*) FROM sessions").fetchone()[0] == 1


def test_ownership_and_ordering_constraints_reject_invalid_records() -> None:
    connection = create_database()
    insert_samples(connection)

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO boards VALUES (?, ?, ?, ?, ?)",
            (
                "another-board",
                "00000000-0000-4000-8000-000000000001",
                "Duplicate board",
                "2026-09-02T20:00:00Z",
                "2026-09-02T20:00:00Z",
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO board_columns VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "duplicate-position",
                "10000000-0000-4000-8000-000000000001",
                "backlog",
                "Duplicate",
                0,
                "2026-09-02T20:00:00Z",
                "2026-09-02T20:00:00Z",
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO board_columns VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "invalid-column",
                "10000000-0000-4000-8000-000000000001",
                "custom",
                "Custom",
                4,
                "2026-09-02T20:00:00Z",
                "2026-09-02T20:00:00Z",
            ),
        )

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "duplicate-card-position",
                "10000000-0000-4000-8000-000000000001",
                "20000000-0000-4000-8000-000000000001",
                "Duplicate position",
                "",
                0,
                "2026-09-02T20:00:00Z",
                "2026-09-02T20:00:00Z",
            ),
        )

    connection.execute(
        "INSERT INTO users VALUES (?, ?, ?)",
        ("other-user", "other", "2026-09-02T20:00:00Z"),
    )
    connection.execute(
        "INSERT INTO boards VALUES (?, ?, ?, ?, ?)",
        (
            "other-board",
            "other-user",
            "Other board",
            "2026-09-02T20:00:00Z",
            "2026-09-02T20:00:00Z",
        ),
    )
    connection.execute(
        "INSERT INTO board_columns VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "other-column",
            "other-board",
            "backlog",
            "Backlog",
            0,
            "2026-09-02T20:00:00Z",
            "2026-09-02T20:00:00Z",
        ),
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO cards VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "cross-board-card",
                "10000000-0000-4000-8000-000000000001",
                "other-column",
                "Cross board",
                "",
                0,
                "2026-09-02T20:00:00Z",
                "2026-09-02T20:00:00Z",
            ),
        )


def test_column_rename_and_atomic_card_move_are_supported() -> None:
    connection = create_database()
    insert_samples(connection)

    connection.execute(
        "UPDATE board_columns SET title = ?, updated_at = ? WHERE id = ?",
        (
            "Ideas",
            "2026-09-02T20:05:00Z",
            "20000000-0000-4000-8000-000000000001",
        ),
    )
    assert connection.execute(
        "SELECT title FROM board_columns WHERE id = ?",
        ("20000000-0000-4000-8000-000000000001",),
    ).fetchone()[0] == "Ideas"

    source_column = "20000000-0000-4000-8000-000000000001"
    target_column = "20000000-0000-4000-8000-000000000002"
    moved_card = "30000000-0000-4000-8000-000000000002"
    with connection:
        connection.execute(
            "UPDATE cards SET position = position + 3 WHERE column_id IN (?, ?)",
            (source_column, target_column),
        )
        connection.execute(
            "UPDATE cards SET position = 0 WHERE id = ?",
            ("30000000-0000-4000-8000-000000000001",),
        )
        connection.execute(
            "UPDATE cards SET column_id = ?, position = 0, updated_at = ? WHERE id = ?",
            (target_column, "2026-09-02T20:05:00Z", moved_card),
        )

    assert connection.execute(
        "SELECT column_id, position FROM cards WHERE id = ?",
        (moved_card,),
    ).fetchone() == (target_column, 0)
    assert connection.execute(
        "SELECT position FROM cards WHERE column_id = ? ORDER BY position",
        (source_column,),
    ).fetchall() == [(0,)]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    with pytest.raises(sqlite3.IntegrityError):
        with connection:
            connection.execute(
                "UPDATE boards SET title = ? WHERE id = ?",
                ("Must roll back", "10000000-0000-4000-8000-000000000001"),
            )
            connection.execute(
                "UPDATE cards SET column_id = ? WHERE id = ?",
                ("missing-column", moved_card),
            )

    assert connection.execute(
        "SELECT title FROM boards WHERE id = ?",
        ("10000000-0000-4000-8000-000000000001",),
    ).fetchone()[0] == "Kanban Studio"