import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path

from fastapi import Cookie, Depends, FastAPI, Response
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from app.ai import (
    AIClient,
    AIConfigurationError,
    AIProviderError,
    AIProviderTimeout,
    BoardOperation,
    ChatMessage,
    KodeKloudClient,
)
from app.auth import SESSION_COOKIE, SESSION_MAX_AGE, Session, SessionStore, require_session
from app.board import (
    BoardItemNotFound,
    BoardResponse,
    BoardStore,
    CreateCardRequest,
    EditCardRequest,
    InvalidBoardOperation,
    MoveCardRequest,
    RenameColumnRequest,
)
from app.database import Database

DEFAULT_STATIC_DIR = Path(__file__).parent / "static"
DEFAULT_DATABASE_PATH = Path(__file__).parents[2] / "data" / "pm.db"
DEFAULT_SESSION_SECRET = secrets.token_hex(32)
MAX_AI_HISTORY_MESSAGES = 20


class LoginRequest(BaseModel):
    username: str
    password: str


class AIDiagnosticResponse(BaseModel):
    answer: str


class AIBoardRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1)
    history: list[ChatMessage] = Field(
        default_factory=list, max_length=MAX_AI_HISTORY_MESSAGES
    )


class AIBoardResponse(BaseModel):
    assistantText: str
    appliedOperations: list[BoardOperation]
    board: BoardResponse


def create_app(
    static_dir: Path | None = None,
    database_path: Path = DEFAULT_DATABASE_PATH,
    session_secret: str = DEFAULT_SESSION_SECRET,
    now: Callable[[], float] = time.time,
    session_max_age: int = SESSION_MAX_AGE,
    ai_client: AIClient | None = None,
) -> FastAPI:
    application = FastAPI(title="Project Management MVP")
    database = Database(database_path)
    database.initialize()
    sessions = SessionStore(database, session_secret, now, session_max_age)
    boards = BoardStore(database)
    authenticated = require_session(sessions)

    @application.exception_handler(BoardItemNotFound)
    def board_item_not_found(_request, _exception) -> JSONResponse:
        return JSONResponse({"detail": "Board item not found"}, status_code=404)

    @application.exception_handler(InvalidBoardOperation)
    def invalid_board_operation(
        _request, exception: InvalidBoardOperation
    ) -> JSONResponse:
        return JSONResponse({"detail": str(exception)}, status_code=400)

    @application.exception_handler(AIConfigurationError)
    def ai_not_configured(_request, _exception) -> JSONResponse:
        return JSONResponse({"detail": "AI service is not configured"}, status_code=503)

    @application.exception_handler(AIProviderTimeout)
    def ai_timeout(_request, _exception) -> JSONResponse:
        return JSONResponse({"detail": "AI service timed out"}, status_code=504)

    @application.exception_handler(AIProviderError)
    def ai_provider_error(_request, _exception) -> JSONResponse:
        return JSONResponse({"detail": "AI service request failed"}, status_code=502)

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

    @application.get("/api/board", response_model=BoardResponse)
    def get_board(session: Session = Depends(authenticated)) -> BoardResponse:
        return boards.get(session.username)

    @application.post("/api/ai/diagnostic", response_model=AIDiagnosticResponse)
    def ai_diagnostic(
        _session: Session = Depends(authenticated),
    ) -> AIDiagnosticResponse:
        if ai_client is None:
            raise AIConfigurationError("KodeKloud AI is not configured")
        return AIDiagnosticResponse(answer=ai_client.ask("2+2"))

    @application.post("/api/ai/board", response_model=AIBoardResponse)
    def ai_board_operations(
        request: AIBoardRequest,
        session: Session = Depends(authenticated),
    ) -> AIBoardResponse:
        if ai_client is None:
            raise AIConfigurationError("KodeKloud AI is not configured")
        board = boards.get(session.username)
        ai_response = ai_client.ask_board(
            board.model_dump(), request.message, request.history
        )
        resulting_board = boards.apply_operations(
            session.username, ai_response.operations
        )
        return AIBoardResponse(
            assistantText=ai_response.assistantText,
            appliedOperations=ai_response.operations,
            board=resulting_board,
        )

    @application.patch("/api/columns/{column_id}", response_model=BoardResponse)
    def rename_column(
        column_id: str,
        request: RenameColumnRequest,
        session: Session = Depends(authenticated),
    ) -> BoardResponse:
        return boards.rename_column(session.username, column_id, request.title)

    @application.post("/api/cards", response_model=BoardResponse, status_code=201)
    def create_card(
        request: CreateCardRequest,
        session: Session = Depends(authenticated),
    ) -> BoardResponse:
        return boards.create_card(session.username, request)

    @application.patch("/api/cards/{card_id}", response_model=BoardResponse)
    def edit_card(
        card_id: str,
        request: EditCardRequest,
        session: Session = Depends(authenticated),
    ) -> BoardResponse:
        return boards.edit_card(session.username, card_id, request)

    @application.delete("/api/cards/{card_id}", response_model=BoardResponse)
    def delete_card(
        card_id: str,
        session: Session = Depends(authenticated),
    ) -> BoardResponse:
        return boards.delete_card(session.username, card_id)

    @application.post("/api/cards/{card_id}/move", response_model=BoardResponse)
    def move_card(
        card_id: str,
        request: MoveCardRequest,
        session: Session = Depends(authenticated),
    ) -> BoardResponse:
        return boards.move_card(session.username, card_id, request)

    application.mount(
        "/",
        StaticFiles(directory=static_dir or DEFAULT_STATIC_DIR, html=True),
        name="frontend",
    )
    return application


app = create_app(
    Path(os.environ.get("STATIC_DIR", DEFAULT_STATIC_DIR)),
    Path(os.environ.get("DATABASE_PATH", DEFAULT_DATABASE_PATH)),
    os.environ.get("SESSION_SECRET", DEFAULT_SESSION_SECRET),
    ai_client=(
        KodeKloudClient(os.environ["KK_BASE_URL"], os.environ["KK_API_KEY"])
        if os.environ.get("KK_BASE_URL") and os.environ.get("KK_API_KEY")
        else None
    ),
)