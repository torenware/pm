import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.board import BoardStore, MoveCardRequest
from app.database import Database
from app.main import create_app


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    return tmp_path / "pm.db"


@pytest.fixture
def client(database_path: Path) -> TestClient:
    test_client = TestClient(
        create_app(database_path=database_path, session_secret="test-secret")
    )
    response = test_client.post(
        "/api/login", json={"username": "user", "password": "password"}
    )
    assert response.status_code == 200
    return test_client


def add_card(
    client: TestClient, column_id: str, title: str, details: str = ""
) -> dict:
    response = client.post(
        "/api/cards",
        json={"columnId": column_id, "title": title, "details": details},
    )
    assert response.status_code == 201
    return response.json()


def card_id(board: dict, title: str) -> str:
    return next(card["id"] for card in board["cards"].values() if card["title"] == title)


def test_board_requires_authentication(database_path: Path) -> None:
    anonymous = TestClient(
        create_app(database_path=database_path, session_secret="test-secret")
    )

    assert anonymous.get("/api/board").status_code == 401
    assert anonymous.patch("/api/columns/unknown", json={"title": "Name"}).status_code == 401
    assert anonymous.post(
        "/api/cards", json={"columnId": "unknown", "title": "Card"}
    ).status_code == 401
    assert anonymous.patch(
        "/api/cards/unknown", json={"title": "Card", "details": ""}
    ).status_code == 401
    assert anonymous.delete("/api/cards/unknown").status_code == 401
    assert anonymous.post(
        "/api/cards/unknown/move", json={"columnId": "unknown", "position": 0}
    ).status_code == 401


def test_board_read_rename_and_card_crud(client: TestClient) -> None:
    board = client.get("/api/board").json()
    assert board["title"] == "Kanban Studio"
    assert [column["title"] for column in board["columns"]] == [
        "Backlog",
        "Discovery",
        "In Progress",
        "Review",
        "Done",
    ]
    assert board["cards"] == {}

    backlog_id = board["columns"][0]["id"]
    renamed = client.patch(
        f"/api/columns/{backlog_id}", json={"title": " Ideas "}
    )
    assert renamed.status_code == 200
    assert renamed.json()["columns"][0]["title"] == "Ideas"

    created = add_card(client, backlog_id, "First card", "Initial details")
    created_id = card_id(created, "First card")
    assert created["columns"][0]["cardIds"] == [created_id]
    assert created["cards"][created_id]["details"] == "Initial details"

    edited = client.patch(
        f"/api/cards/{created_id}",
        json={"title": " Updated card ", "details": "Updated details"},
    )
    assert edited.status_code == 200
    assert edited.json()["cards"][created_id] == {
        "id": created_id,
        "title": "Updated card",
        "details": "Updated details",
    }

    deleted = client.delete(f"/api/cards/{created_id}")
    assert deleted.status_code == 200
    assert deleted.json()["cards"] == {}
    assert deleted.json()["columns"][0]["cardIds"] == []


def test_same_column_reorders_at_start_middle_and_end(client: TestClient) -> None:
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]
    for title in ("A", "B", "C", "D"):
        board = add_card(client, column_id, title)
    ids = {title: card_id(board, title) for title in ("A", "B", "C", "D")}

    board = client.post(
        f"/api/cards/{ids['D']}/move", json={"columnId": column_id, "position": 0}
    ).json()
    assert board["columns"][0]["cardIds"] == [ids["D"], ids["A"], ids["B"], ids["C"]]

    board = client.post(
        f"/api/cards/{ids['D']}/move", json={"columnId": column_id, "position": 2}
    ).json()
    assert board["columns"][0]["cardIds"] == [ids["A"], ids["B"], ids["D"], ids["C"]]

    board = client.post(
        f"/api/cards/{ids['D']}/move", json={"columnId": column_id, "position": 3}
    ).json()
    assert board["columns"][0]["cardIds"] == [ids["A"], ids["B"], ids["C"], ids["D"]]


def test_cross_column_moves_at_start_middle_and_end(client: TestClient) -> None:
    board = client.get("/api/board").json()
    source_id = board["columns"][0]["id"]
    target_id = board["columns"][1]["id"]
    for title in ("A", "B", "C"):
        board = add_card(client, source_id, title)
    for title in ("X", "Y"):
        board = add_card(client, target_id, title)
    ids = {title: card_id(board, title) for title in ("A", "B", "C", "X", "Y")}

    board = client.post(
        f"/api/cards/{ids['A']}/move", json={"columnId": target_id, "position": 0}
    ).json()
    assert board["columns"][1]["cardIds"] == [ids["A"], ids["X"], ids["Y"]]

    board = client.post(
        f"/api/cards/{ids['B']}/move", json={"columnId": target_id, "position": 2}
    ).json()
    assert board["columns"][1]["cardIds"] == [
        ids["A"],
        ids["X"],
        ids["B"],
        ids["Y"],
    ]

    board = client.post(
        f"/api/cards/{ids['C']}/move", json={"columnId": target_id, "position": 4}
    ).json()
    assert board["columns"][0]["cardIds"] == []
    assert board["columns"][1]["cardIds"] == [
        ids["A"],
        ids["X"],
        ids["B"],
        ids["Y"],
        ids["C"],
    ]


def test_validation_unknown_ids_and_cross_user_ids(
    client: TestClient, database_path: Path
) -> None:
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]

    assert client.patch(f"/api/columns/{column_id}", json={"title": "   "}).status_code == 400
    assert client.post(
        "/api/cards", json={"columnId": column_id, "title": "   "}
    ).status_code == 400
    assert client.patch(
        "/api/cards/unknown", json={"title": "Card", "details": ""}
    ).status_code == 404
    assert client.delete("/api/cards/unknown").status_code == 404
    assert client.post(
        "/api/cards/unknown/move", json={"columnId": column_id, "position": 0}
    ).status_code == 404
    card_board = add_card(client, column_id, "Position check")
    position_card_id = card_id(card_board, "Position check")
    invalid_move = client.post(
        f"/api/cards/{position_card_id}/move",
        json={"columnId": column_id, "position": 2},
    )
    assert invalid_move.status_code == 400
    assert client.get("/api/board").json()["columns"][0]["cardIds"] == [
        position_card_id
    ]
    assert client.post(
        "/api/cards", json={"columnId": column_id, "title": "x" * 201}
    ).status_code == 422

    database = Database(database_path)
    with database.connect() as connection:
        timestamp = "2026-09-02T20:00:00+00:00"
        connection.execute(
            "INSERT INTO users VALUES ('other-user', 'other', ?)", (timestamp,)
        )
        connection.execute(
            "INSERT INTO boards VALUES ('other-board', 'other-user', 'Other', ?, ?)",
            (timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO board_columns VALUES ('other-column', 'other-board', 'backlog', 'Other', 0, ?, ?)",
            (timestamp, timestamp),
        )
        connection.execute(
            "INSERT INTO cards VALUES ('other-card', 'other-board', 'other-column', 'Other', '', 0, ?, ?)",
            (timestamp, timestamp),
        )

    assert client.patch("/api/columns/other-column", json={"title": "No"}).status_code == 404
    assert client.post(
        "/api/cards", json={"columnId": "other-column", "title": "No"}
    ).status_code == 404
    assert client.patch(
        "/api/cards/other-card", json={"title": "No", "details": ""}
    ).status_code == 404
    assert client.delete("/api/cards/other-card").status_code == 404
    assert client.post(
        "/api/cards/other-card/move", json={"columnId": column_id, "position": 0}
    ).status_code == 404


def test_invalid_move_rolls_back_runtime_position_changes(
    client: TestClient, database_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    board = client.get("/api/board").json()
    source_id = board["columns"][0]["id"]
    target_id = board["columns"][1]["id"]
    board = add_card(client, source_id, "A")
    board = add_card(client, source_id, "B")
    moved_id = card_id(board, "B")
    database = Database(database_path)
    store = BoardStore(database)

    def fail_after_shift(*_args) -> None:
        raise sqlite3.IntegrityError("forced failure")

    monkeypatch.setattr(store, "_write_positions", fail_after_shift)

    with pytest.raises(sqlite3.IntegrityError, match="forced failure"):
        store.move_card(
            "user", moved_id, MoveCardRequest(columnId=target_id, position=0)
        )

    persisted = client.get("/api/board").json()
    assert persisted["columns"][0]["cardIds"] == board["columns"][0]["cardIds"]
    assert persisted["columns"][1]["cardIds"] == []