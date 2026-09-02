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
        with self._database.connect() as connection:
            board = self._owned_board(connection, username)
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

    def rename_column(self, username: str, column_id: str, title: str) -> BoardResponse:
        title = self._required_text(title)
        with self._database.connect() as connection:
            board = self._owned_board(connection, username)
            result = connection.execute(
                "UPDATE board_columns SET title = ?, updated_at = ? WHERE id = ? AND board_id = ?",
                (title, utc_now(), column_id, board.id),
            )
            if result.rowcount == 0:
                raise BoardItemNotFound
            self._touch_board(connection, board.id)
        return self.get(username)

    def create_card(self, username: str, request: CreateCardRequest) -> BoardResponse:
        title = self._required_text(request.title)
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            self._owned_column(connection, board.id, request.columnId)
            position = connection.execute(
                "SELECT count(*) FROM cards WHERE column_id = ?",
                (request.columnId,),
            ).fetchone()[0]
            timestamp = utc_now()
            connection.execute(
                "INSERT INTO cards (id, board_id, column_id, title, details, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(uuid4()),
                    board.id,
                    request.columnId,
                    title,
                    request.details,
                    position,
                    timestamp,
                    timestamp,
                ),
            )
            self._touch_board(connection, board.id)
        return self.get(username)

    def edit_card(self, username: str, card_id: str, request: EditCardRequest) -> BoardResponse:
        title = self._required_text(request.title)
        with self._database.connect() as connection:
            board = self._owned_board(connection, username)
            result = connection.execute(
                "UPDATE cards SET title = ?, details = ?, updated_at = ? WHERE id = ? AND board_id = ?",
                (title, request.details, utc_now(), card_id, board.id),
            )
            if result.rowcount == 0:
                raise BoardItemNotFound
            self._touch_board(connection, board.id)
        return self.get(username)

    def delete_card(self, username: str, card_id: str) -> BoardResponse:
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            card = self._owned_card(connection, board.id, card_id)
            connection.execute("DELETE FROM cards WHERE id = ?", (card_id,))
            self._write_positions(
                connection,
                card["column_id"],
                self._card_ids(connection, card["column_id"]),
            )
            self._touch_board(connection, board.id)
        return self.get(username)

    def move_card(
        self, username: str, card_id: str, request: MoveCardRequest
    ) -> BoardResponse:
        with self._immediate() as connection:
            board = self._owned_board(connection, username)
            card = self._owned_card(connection, board.id, card_id)
            self._owned_column(connection, board.id, request.columnId)
            source_column_id = card["column_id"]
            source_ids = self._card_ids(connection, source_column_id)
            source_ids.remove(card_id)
            if source_column_id == request.columnId:
                target_ids = source_ids
            else:
                target_ids = self._card_ids(connection, request.columnId)
            if request.position > len(target_ids):
                raise InvalidBoardOperation("Position is outside the target column")
            target_ids.insert(request.position, card_id)

            affected_ids = {source_column_id, request.columnId}
            temporary_offset = sum(
                connection.execute(
                    "SELECT count(*) FROM cards WHERE column_id = ?", (column_id,)
                ).fetchone()[0]
                for column_id in affected_ids
            ) + 1
            connection.execute(
                f"UPDATE cards SET position = position + ? WHERE column_id IN ({','.join('?' for _ in affected_ids)})",
                (temporary_offset, *affected_ids),
            )
            self._write_positions(connection, source_column_id, source_ids)
            if source_column_id != request.columnId:
                self._write_positions(connection, request.columnId, target_ids)
            connection.execute(
                "UPDATE cards SET column_id = ?, updated_at = ? WHERE id = ?",
                (request.columnId, utc_now(), card_id),
            )
            self._touch_board(connection, board.id)
        return self.get(username)

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
        return self.get(username)

    def _apply_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: BoardOperation,
    ) -> None:
        if isinstance(operation, CreateCardOperation):
            self._create_card_operation(connection, board_id, operation)
        elif isinstance(operation, EditCardOperation):
            self._edit_card_operation(connection, board_id, operation)
        elif isinstance(operation, DeleteCardOperation):
            self._delete_card_operation(connection, board_id, operation)
        elif isinstance(operation, MoveCardOperation):
            self._move_card_operation(connection, board_id, operation)
        elif isinstance(operation, RenameColumnOperation):
            self._rename_column_operation(connection, board_id, operation)

    def _create_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: CreateCardOperation,
    ) -> None:
        self._owned_column(connection, board_id, operation.columnId)
        title = self._required_text(operation.title)
        position = connection.execute(
            "SELECT count(*) FROM cards WHERE column_id = ?", (operation.columnId,)
        ).fetchone()[0]
        timestamp = utc_now()
        connection.execute(
            "INSERT INTO cards (id, board_id, column_id, title, details, position, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(uuid4()),
                board_id,
                operation.columnId,
                title,
                operation.details,
                position,
                timestamp,
                timestamp,
            ),
        )

    def _edit_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: EditCardOperation,
    ) -> None:
        self._owned_card(connection, board_id, operation.cardId)
        connection.execute(
            "UPDATE cards SET title = ?, details = ?, updated_at = ? WHERE id = ?",
            (
                self._required_text(operation.title),
                operation.details,
                utc_now(),
                operation.cardId,
            ),
        )

    def _delete_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: DeleteCardOperation,
    ) -> None:
        card = self._owned_card(connection, board_id, operation.cardId)
        connection.execute("DELETE FROM cards WHERE id = ?", (operation.cardId,))
        self._write_positions(
            connection,
            card["column_id"],
            self._card_ids(connection, card["column_id"]),
        )

    def _move_card_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: MoveCardOperation,
    ) -> None:
        card = self._owned_card(connection, board_id, operation.cardId)
        self._owned_column(connection, board_id, operation.columnId)
        source_column_id = card["column_id"]
        source_ids = self._card_ids(connection, source_column_id)
        source_ids.remove(operation.cardId)
        target_ids = (
            source_ids
            if source_column_id == operation.columnId
            else self._card_ids(connection, operation.columnId)
        )
        if operation.position > len(target_ids):
            raise InvalidBoardOperation("Position is outside the target column")
        target_ids.insert(operation.position, operation.cardId)

        affected_ids = {source_column_id, operation.columnId}
        temporary_offset = sum(
            connection.execute(
                "SELECT count(*) FROM cards WHERE column_id = ?", (column_id,)
            ).fetchone()[0]
            for column_id in affected_ids
        ) + 1
        connection.execute(
            f"UPDATE cards SET position = position + ? WHERE column_id IN ({','.join('?' for _ in affected_ids)})",
            (temporary_offset, *affected_ids),
        )
        self._write_positions(connection, source_column_id, source_ids)
        if source_column_id != operation.columnId:
            self._write_positions(connection, operation.columnId, target_ids)
        connection.execute(
            "UPDATE cards SET column_id = ?, updated_at = ? WHERE id = ?",
            (operation.columnId, utc_now(), operation.cardId),
        )

    def _rename_column_operation(
        self,
        connection: sqlite3.Connection,
        board_id: str,
        operation: RenameColumnOperation,
    ) -> None:
        self._owned_column(connection, board_id, operation.columnId)
        connection.execute(
            "UPDATE board_columns SET title = ?, updated_at = ? WHERE id = ?",
            (self._required_text(operation.title), utc_now(), operation.columnId),
        )

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