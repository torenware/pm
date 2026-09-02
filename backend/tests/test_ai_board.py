import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.ai import (
    AIProviderError,
    ChatMessage,
    KodeKloudClient,
    StructuredAIResponse,
)
from app.database import Database
from app.main import create_app


class StubBoardAIClient:
    def __init__(self, response: StructuredAIResponse) -> None:
        self.response = response
        self.calls: list[tuple[dict[str, Any], str, list[ChatMessage]]] = []

    def ask(self, _prompt: str) -> str:
        return "4"

    def ask_board(
        self,
        board: dict[str, Any],
        message: str,
        history: list[ChatMessage],
    ) -> StructuredAIResponse:
        self.calls.append((board, message, history))
        return self.response


def response(operations: list[dict[str, Any]]) -> StructuredAIResponse:
    return StructuredAIResponse.model_validate(
        {"assistantText": "Board updated", "operations": operations}
    )


def authenticated_client(
    database_path: Path, ai_client: StubBoardAIClient
) -> TestClient:
    client = TestClient(
        create_app(
            database_path=database_path,
            session_secret="test-secret",
            ai_client=ai_client,
        )
    )
    assert client.post(
        "/api/login", json={"username": "user", "password": "password"}
    ).status_code == 200
    return client


def operation_types(board: dict[str, Any]) -> list[dict[str, Any]]:
    first_column = board["columns"][0]["id"]
    second_column = board["columns"][1]["id"]
    card_id = next(iter(board["cards"]))
    return [
        {
            "operationId": "create-1",
            "type": "create_card",
            "columnId": first_column,
            "title": "New card",
            "details": "Details",
        },
        {
            "operationId": "edit-1",
            "type": "edit_card",
            "cardId": card_id,
            "title": "Edited card",
            "details": "Edited details",
        },
        {
            "operationId": "delete-1",
            "type": "delete_card",
            "cardId": card_id,
        },
        {
            "operationId": "move-1",
            "type": "move_card",
            "cardId": card_id,
            "columnId": second_column,
            "position": 0,
        },
        {
            "operationId": "rename-1",
            "type": "rename_column",
            "columnId": first_column,
            "title": "Ideas",
        },
    ]


def add_card(client: TestClient, column_id: str, title: str = "Existing") -> dict:
    result = client.post(
        "/api/cards",
        json={"columnId": column_id, "title": title, "details": ""},
    )
    assert result.status_code == 201
    return result.json()


def test_structured_response_accepts_each_supported_operation(tmp_path: Path) -> None:
    ai_client = StubBoardAIClient(response([]))
    client = authenticated_client(tmp_path / "pm.db", ai_client)
    board = client.get("/api/board").json()
    board = add_card(client, board["columns"][0]["id"])

    parsed = response(operation_types(board))

    assert [operation.type for operation in parsed.operations] == [
        "create_card",
        "edit_card",
        "delete_card",
        "move_card",
        "rename_column",
    ]


@pytest.mark.parametrize(
    "operation",
    [
        {"operationId": "bad", "type": "archive_card", "cardId": "card"},
        {"operationId": "bad", "type": "edit_card", "title": "Missing id"},
        {
            "operationId": "bad",
            "type": "delete_card",
            "cardId": "card",
            "unexpected": True,
        },
    ],
)
def test_structured_response_rejects_unsupported_or_malformed_operations(
    operation: dict[str, Any],
) -> None:
    with pytest.raises(ValidationError):
        response([operation])


def test_provider_sends_board_message_history_and_strict_schema() -> None:
    captured: dict[str, Any] = {}

    def handle_request(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.read()))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {"assistantText": "No changes", "operations": []}
                            )
                        }
                    }
                ]
            },
        )

    client = KodeKloudClient(
        "https://example.test/v1",
        "test-key",
        transport=httpx.MockTransport(handle_request),
    )
    board = {"id": "board-1", "columns": [], "cards": {}}
    history = [ChatMessage(role="user", content="Earlier message")]

    result = client.ask_board(board, "Current message", history)

    prompt = json.loads(captured["messages"][1]["content"])
    assert prompt == {
        "board": board,
        "message": "Current message",
        "history": [{"role": "user", "content": "Earlier message"}],
    }
    assert captured["response_format"]["type"] == "json_schema"
    assert captured["response_format"]["json_schema"]["strict"] is True
    assert set(
        captured["response_format"]["json_schema"]["schema"]["$defs"]
    ) >= {
        "CreateCardOperation",
        "EditCardOperation",
        "DeleteCardOperation",
        "MoveCardOperation",
        "RenameColumnOperation",
    }
    assert result.assistantText == "No changes"


@pytest.mark.parametrize("content", ["not json", '{"assistantText":"Missing ops"}'])
def test_provider_rejects_malformed_structured_output(content: str) -> None:
    client = KodeKloudClient(
        "https://example.test/v1",
        "test-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"choices": [{"message": {"content": content}}]}
            )
        ),
    )

    with pytest.raises(AIProviderError, match="invalid response"):
        client.ask_board({}, "message", [])


def test_ai_board_requires_authentication(tmp_path: Path) -> None:
    client = TestClient(
        create_app(
            database_path=tmp_path / "pm.db",
            ai_client=StubBoardAIClient(response([])),
        )
    )

    assert client.post(
        "/api/ai/board", json={"message": "Hello", "history": []}
    ).status_code == 401


def test_ai_board_returns_text_without_mutating_for_empty_operations(
    tmp_path: Path,
) -> None:
    ai_client = StubBoardAIClient(response([]))
    client = authenticated_client(tmp_path / "pm.db", ai_client)
    before = client.get("/api/board").json()

    result = client.post(
        "/api/ai/board",
        json={
            "message": "What should I do?",
            "history": [{"role": "assistant", "content": "Let us review."}],
        },
    )

    assert result.status_code == 200
    assert result.json() == {
        "assistantText": "Board updated",
        "appliedOperations": [],
        "board": before,
    }
    assert ai_client.calls[0][0] == before
    assert ai_client.calls[0][1] == "What should I do?"
    assert ai_client.calls[0][2][0].content == "Let us review."


def test_ai_board_applies_single_and_multiple_operations(tmp_path: Path) -> None:
    database_path = tmp_path / "pm.db"
    ai_client = StubBoardAIClient(response([]))
    client = authenticated_client(database_path, ai_client)
    board = client.get("/api/board").json()
    first_column = board["columns"][0]["id"]
    second_column = board["columns"][1]["id"]

    ai_client.response = response(
        [
            {
                "operationId": "create-1",
                "type": "create_card",
                "columnId": first_column,
                "title": "Created by AI",
                "details": "",
            }
        ]
    )
    created = client.post(
        "/api/ai/board", json={"message": "Create a card", "history": []}
    )
    assert created.status_code == 200
    created_board = created.json()["board"]
    created_id = next(
        card_id
        for card_id, card in created_board["cards"].items()
        if card["title"] == "Created by AI"
    )

    ai_client.response = response(
        [
            {
                "operationId": "edit-1",
                "type": "edit_card",
                "cardId": created_id,
                "title": "Edited by AI",
                "details": "Updated",
            },
            {
                "operationId": "move-1",
                "type": "move_card",
                "cardId": created_id,
                "columnId": second_column,
                "position": 0,
            },
            {
                "operationId": "rename-1",
                "type": "rename_column",
                "columnId": first_column,
                "title": "AI Ideas",
            },
        ]
    )
    updated = client.post(
        "/api/ai/board", json={"message": "Update the board", "history": []}
    )

    assert updated.status_code == 200
    result = updated.json()
    assert [item["operationId"] for item in result["appliedOperations"]] == [
        "edit-1",
        "move-1",
        "rename-1",
    ]
    assert result["board"]["cards"][created_id]["title"] == "Edited by AI"
    assert result["board"]["columns"][0]["title"] == "AI Ideas"
    assert result["board"]["columns"][1]["cardIds"] == [created_id]

    ai_client.response = response(
        [
            {
                "operationId": "delete-1",
                "type": "delete_card",
                "cardId": created_id,
            }
        ]
    )
    deleted = client.post(
        "/api/ai/board", json={"message": "Delete the card", "history": []}
    )
    assert deleted.status_code == 200
    assert created_id not in deleted.json()["board"]["cards"]


@pytest.mark.parametrize("bad_card_id", ["stale-card", "other-card"])
def test_invalid_or_cross_user_operation_rolls_back_entire_response(
    tmp_path: Path, bad_card_id: str
) -> None:
    database_path = tmp_path / "pm.db"
    ai_client = StubBoardAIClient(response([]))
    client = authenticated_client(database_path, ai_client)
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]
    if bad_card_id == "other-card":
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

    ai_client.response = response(
        [
            {
                "operationId": "rename-first",
                "type": "rename_column",
                "columnId": column_id,
                "title": "Must roll back",
            },
            {
                "operationId": "edit-invalid",
                "type": "edit_card",
                "cardId": bad_card_id,
                "title": "No",
                "details": "",
            },
        ]
    )

    result = client.post(
        "/api/ai/board", json={"message": "Invalid batch", "history": []}
    )

    assert result.status_code == 404
    assert client.get("/api/board").json()["columns"][0]["title"] == "Backlog"


def test_duplicate_operation_ids_roll_back_response(tmp_path: Path) -> None:
    ai_client = StubBoardAIClient(response([]))
    client = authenticated_client(tmp_path / "pm.db", ai_client)
    board = client.get("/api/board").json()
    column_id = board["columns"][0]["id"]
    ai_client.response = response(
        [
            {
                "operationId": "duplicate",
                "type": "rename_column",
                "columnId": column_id,
                "title": "First",
            },
            {
                "operationId": "duplicate",
                "type": "rename_column",
                "columnId": column_id,
                "title": "Second",
            },
        ]
    )

    result = client.post(
        "/api/ai/board", json={"message": "Duplicate ids", "history": []}
    )

    assert result.status_code == 400
    assert client.get("/api/board").json()["columns"][0]["title"] == "Backlog"


def test_conversation_history_is_not_persisted(tmp_path: Path) -> None:
    database_path = tmp_path / "pm.db"
    ai_client = StubBoardAIClient(response([]))
    client = authenticated_client(database_path, ai_client)
    marker = "history-marker-that-must-not-be-stored"

    result = client.post(
        "/api/ai/board",
        json={
            "message": "Current message",
            "history": [{"role": "user", "content": marker}],
        },
    )

    assert result.status_code == 200
    with Database(database_path).connect() as connection:
        for table in ("users", "boards", "board_columns", "cards", "sessions"):
            rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            assert all(marker not in str(tuple(row)) for row in rows)