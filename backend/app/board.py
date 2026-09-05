import sqlite3
from dataclasses import dataclass
from uuid import uuid4

from pydantic import BaseModel, Field

from app.ai import (
    BoardOperation,
    CreateCardOperation,
    DeleteCardOperation,
    EditCardOperation,
    MoveCardOperation,
    RenameColumnOperation,
)
from app.database import Database, utc_now


class CardResponse(BaseModel):
    id: str
    title: str
    details: str


class ColumnResponse(BaseModel):
    id: str
    title: str
    cardIds: list[str]


class BoardResponse(BaseModel):
    id: str
    title: str
    columns: list[ColumnResponse]
    cards: dict[str, CardResponse]


class RenameColumnRequest(BaseModel):
    title: str = Field(min_length=1, max_length=80)


class CreateCardRequest(BaseModel):
    columnId: str
    title: str = Field(min_length=1, max_length=200)
    details: str = ""


class EditCardRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    details: str = ""


class MoveCardRequest(BaseModel):
    columnId: str
    position: int = Field(ge=0)


class BoardItemNotFound(Exception):
    pass


class InvalidBoardOperation(Exception):
    pass


@dataclass(frozen=True)
class OwnedBoard:
    id: str
    title: str


class BoardStore:
    def __init__(self, database: Database) -> None:
        self._database = database

    def get(self, username: str) -> BoardResponse:
        with self._database.session() as connection:
            board = self._owned_board(connection, username)
            return self._snapshot(connection, board)

    def rename_column(self, username: str, column_id: str, title: str) -> BoardResponse:
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            self._rename_column(connection, board.id, column_id, title)
            self._touch_board(connection, board.id)
            return self._snapshot(connection, board)

    def create_card(self, username: str, request: CreateCardRequest) -> BoardResponse:
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            self._create_card(
                connection, board.id, request.columnId, request.title, request.details
            )
            self._touch_board(connection, board.id)
            return self._snapshot(connection, board)

    def edit_card(self, username: str, card_id: str, request: EditCardRequest) -> BoardResponse:
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            self._edit_card(connection, board.id, card_id, request.title, request.details)
            self._touch_board(connection, board.id)
            return self._snapshot(connection, board)

    def delete_card(self, username: str, card_id: str) -> BoardResponse:
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            self._delete_card(connection, board.id, card_id)
            self._touch_board(connection, board.id)
            return self._snapshot(connection, board)

    def move_card(
        self, username: str, card_id: str, request: MoveCardRequest
    ) -> BoardResponse:
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            self._move_card(
                connection, board.id, card_id, request.columnId, request.position
            )
            self._touch_board(connection, board.id)
            return self._snapshot(connection, board)

    def apply_operations(
        self, username: str, operations: list[BoardOperation]
    ) -> BoardResponse:
        operation_ids = [operation.operationId for operation in operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise InvalidBoardOperation("Operation identifiers must be unique")

        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            for operation in operations:
                self._apply_operation(connection, board.id, operation)
            if operations:
                self._touch_board(connection, board.id)
            return self._snapshot(connection, board)

    def _snapshot(self, connection: sqlite3.Connection, board: OwnedBoard) -> BoardResponse:
        columns = connection.execute(
            "SELECT id, title FROM board_columns WHERE board_id = ? ORDER BY position",
            (board.id,),
        ).fetchall()
        card_rows = connection.execute(
            "SELECT id, column_id, title, details FROM cards WHERE board_id = ? ORDER BY column_id, position",
            (board.id,),
        ).fetchall()
        cards = {
            row["id"]: CardResponse(
                id=row["id"], title=row["title"], details=row["details"]
            )
            for row in card_rows
        }
        card_ids = {column["id"]: [] for column in columns}
        for row in card_rows:
            card_ids[row["column_id"]].append(row["id"])
        return BoardResponse(
            id=board.id,
            title=board.title,
            columns=[
                ColumnResponse(
                    id=column["id"],
                    title=column["title"],
                    cardIds=card_ids[column["id"]],
                )
                for column in columns
            ],
            cards=cards,
        )

    _OPERATION_HANDLERS: dict[str, str] = {
        "create_card": "_create_card_operation",
        "edit_card": "_edit_card_operation",
        "delete_card": "_delete_card_operation",
        "move_card": "_move_card_operation",
        "rename_column": "_rename_column_operation",
    }

    def _apply_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: BoardOperation,
    ) -> None:
        handler = getattr(self, self._OPERATION_HANDLERS[operation.type])
        handler(connection, board_id, operation)

    def _create_card(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        column_id: str,
        title: str,
        details: str,
    ) -> None:
        self._owned_column(connection, board_id, column_id)
        title = self._required_text(title)
        position = connection.execute(
            "SELECT count(*) FROM cards WHERE column_id = ?", (column_id,)
        ).fetchone()[0]
        timestamp = utc_now()
        connection.execute(
            "INSERT INTO cards (id, board_id, column_id, title, details, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                board_id,
                column_id,
                title,
                details,
                position,
                timestamp,
                timestamp,
            ),
        )

    def _create_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: CreateCardOperation,
    ) -> None:
        self._create_card(
            connection, board_id, operation.columnId, operation.title, operation.details
        )

    def _edit_card(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        card_id: str,
        title: str,
        details: str,
    ) -> None:
        self._owned_card(connection, board_id, card_id)
        connection.execute(
            "UPDATE cards SET title = ?, details = ?, updated_at = ? WHERE id = ?",
            (self._required_text(title), details, utc_now(), card_id),
        )

    def _edit_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: EditCardOperation,
    ) -> None:
        self._edit_card(connection, board_id, operation.cardId, operation.title, operation.details)

    def _delete_card(
        self, connection: sqlite3.Connection, board_id: str, card_id: str
    ) -> None:
        card = self._owned_card(connection, board_id, card_id)
        connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        self._write_positions(
            connection,
            card["column_id"],
            self._card_ids(connection, card["column_id"]),
        )

    def _delete_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: DeleteCardOperation,
    ) -> None:
        self._delete_card(connection, board_id, operation.cardId)

    def _move_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: MoveCardOperation,
    ) -> None:
        self._move_card(
            connection, board_id, operation.cardId, operation.columnId, operation.position
        )

    def _move_card(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        card_id: str,
        target_column_id: str,
        position: int,
    ) -> None:
        card = self._owned_card(connection, board_id, card_id)
        self._owned_column(connection, board_id, target_column_id)
        source_column_id = card["column_id"]
        source_ids = self._card_ids(connection, source_column_id)
        source_ids.remove(card_id)
        target_ids = (
            source_ids
            if source_column_id == target_column_id
            else self._card_ids(connection, target_column_id)
        )
        if position > len(target_ids):
            raise InvalidBoardOperation("Position is outside the target column")
        target_ids.insert(position, card_id)

        affected_ids = {source_column_id, target_column_id}
        temporary_offset = (
            len(target_ids) + 1
            if source_column_id == target_column_id
            else len(source_ids) + len(target_ids) + 1
        )
        connection.execute(
            f"UPDATE cards SET position = position + ? WHERE column_id IN ({','.join('?' for _ in affected_ids)})",
            (temporary_offset, *affected_ids),
        )
        self._write_positions(connection, source_column_id, source_ids)
        if source_column_id != target_column_id:
            self._write_positions(connection, target_column_id, target_ids)
        connection.execute(
            "UPDATE cards SET column_id = ?, updated_at = ? WHERE id = ?",
            (target_column_id, utc_now(), card_id),
        )

    def _rename_column(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        column_id: str,
        title: str,
    ) -> None:
        self._owned_column(connection, board_id, column_id)
        connection.execute(
            "UPDATE board_columns SET title = ?, updated_at = ? WHERE id = ?",
            (self._required_text(title), utc_now(), column_id),
        )

    def _rename_column_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: RenameColumnOperation,
    ) -> None:
        self._rename_column(connection, board_id, operation.columnId, operation.title)

    def _immediate(self):
        return ImmediateTransaction(self._database)

    @staticmethod
    def _owned_board(connection: sqlite3.Connection, username: str) -> OwnedBoard:
        row = connection.execute(
            "SELECT boards.id, boards.title FROM boards JOIN users ON users.id = boards.owner_user_id WHERE users.username = ?",
            (username,),
        ).fetchone()
        if row is None:
            raise BoardItemNotFound
        return OwnedBoard(id=row["id"], title=row["title"])

    @staticmethod
    def _owned_column(
        connection: sqlite3.Connection, board_id: str, column_id: str
    ) -> None:
        row = connection.execute(
            "SELECT 1 FROM board_columns WHERE id = ? AND board_id = ?",
            (column_id, board_id),
        ).fetchone()
        if row is None:
            raise BoardItemNotFound

    @staticmethod
    def _owned_card(
        connection: sqlite3.Connection, board_id: str, card_id: str
    ) -> sqlite3.Row:
        row = connection.execute(
            "SELECT id, column_id FROM cards WHERE id = ? AND board_id = ?",
            (card_id, board_id),
        ).fetchone()
        if row is None:
            raise BoardItemNotFound
        return row

    @staticmethod
    def _card_ids(connection: sqlite3.Connection, column_id: str) -> list[str]:
        return [
            row["id"]
            for row in connection.execute(
                "SELECT id FROM cards WHERE column_id = ? ORDER BY position",
                (column_id,),
            )
        ]

    @staticmethod
    def _write_positions(
        connection: sqlite3.Connection, column_id: str, card_ids: list[str]
    ) -> None:
        connection.executemany(
            "UPDATE cards SET column_id = ?, position = ? WHERE id = ?",
            [(column_id, position, card_id) for position, card_id in enumerate(card_ids)],
        )

    @staticmethod
    def _touch_board(connection: sqlite3.Connection, board_id: str) -> None:
        connection.execute(
            "UPDATE boards SET updated_at = ? WHERE id = ?", (utc_now(), board_id)
        )

    @staticmethod
    def _required_text(value: str) -> str:
        value = value.strip()
        if not value:
            raise InvalidBoardOperation("Title must not be blank")
        return value


class ImmediateTransaction:
    def __init__(self, database: Database) -> None:
        self._database = database
        self._connection: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._connection = self._database.connect()
        self._connection.execute("BEGIN IMMEDIATE")
        return self._connection

    def __exit__(self, exception_type, exception, traceback) -> None:
        if self._connection is None:
            return
        if exception_type is None:
            self._connection.commit()
        else:
            self._connection.rollback()
        self._connection.close()