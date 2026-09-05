import json
from typing import Annotated, Any, Literal, Protocol

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

MODEL = "gpt-oss-120b"


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class CreateCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operationId: str = Field(min_length=1)
    type: Literal["create_card"]
    columnId: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    details: str


class EditCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operationId: str = Field(min_length=1)
    type: Literal["edit_card"]
    cardId: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=200)
    details: str


class DeleteCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operationId: str = Field(min_length=1)
    type: Literal["delete_card"]
    cardId: str = Field(min_length=1)


class MoveCardOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operationId: str = Field(min_length=1)
    type: Literal["move_card"]
    cardId: str = Field(min_length=1)
    columnId: str = Field(min_length=1)
    position: int = Field(ge=0)


class RenameColumnOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operationId: str = Field(min_length=1)
    type: Literal["rename_column"]
    columnId: str = Field(min_length=1)
    title: str = Field(min_length=1, max_length=80)


BoardOperation = Annotated[
    CreateCardOperation
    | EditCardOperation
    | DeleteCardOperation
    | MoveCardOperation
    | RenameColumnOperation,
    Field(discriminator="type"),
]


class StructuredAIResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistantText: str = Field(min_length=1)
    operations: list[BoardOperation]


class AIClient(Protocol):
    def ask(self, prompt: str) -> str: ...

    def ask_board(
        self,
        board: dict[str, Any],
        message: str,
        history: list[ChatMessage],
    ) -> StructuredAIResponse: ...


class AIConfigurationError(Exception):
    pass


class AIProviderError(Exception):
    pass


class AIProviderTimeout(AIProviderError):
    pass


class KodeKloudClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not base_url or not api_key:
            raise AIConfigurationError("KodeKloud AI is not configured")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.transport = transport
        self._client = httpx.Client(timeout=timeout, transport=transport)

    def ask(self, prompt: str) -> str:
        return self._complete([{"role": "user", "content": prompt}])

    def ask_board(
        self,
        board: dict[str, Any],
        message: str,
        history: list[ChatMessage],
    ) -> StructuredAIResponse:
        prompt = json.dumps(
            {
                "board": board,
                "message": message,
                "history": [item.model_dump() for item in history],
            },
            separators=(",", ":"),
        )
        content = self._complete(
            [
                {
                    "role": "system",
                    "content": (
                        "You operate a Kanban board. Return JSON matching the supplied "
                        "schema. Use only the five supported operation types. Reference "
                        "existing columnId and cardId values from the board. Do not replace "
                        "the board. Return an empty operations array for text-only replies."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "board_operations",
                    "strict": True,
                    "schema": StructuredAIResponse.model_json_schema(),
                },
            },
        )
        try:
            return StructuredAIResponse.model_validate_json(content)
        except ValidationError as exception:
            raise AIProviderError("KodeKloud AI returned an invalid response") from exception

    def _complete(
        self,
        messages: list[dict[str, str]],
        response_format: dict[str, Any] | None = None,
    ) -> str:
        request: dict[str, Any] = {"model": MODEL, "messages": messages}
        if response_format is not None:
            request["response_format"] = response_format
        try:
            response = self._client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=request,
            )
            response.raise_for_status()
        except httpx.TimeoutException as exception:
            raise AIProviderTimeout("KodeKloud AI request timed out") from exception
        except httpx.HTTPError as exception:
            raise AIProviderError("KodeKloud AI request failed") from exception

        try:
            return self._content(response.json())
        except ValueError as exception:
            raise AIProviderError("KodeKloud AI returned an invalid response") from exception

    @staticmethod
    def _content(payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exception:
            raise AIProviderError("KodeKloud AI returned an invalid response") from exception
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("KodeKloud AI returned an invalid response")
        return content.strip()