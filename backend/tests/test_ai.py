import httpx
import pytest
from fastapi.testclient import TestClient

from app.ai import (
    MODEL,
    AIConfigurationError,
    AIProviderError,
    AIProviderTimeout,
    KodeKloudClient,
)
from app.main import create_app


class StubAIClient:
    def __init__(self, answer: str = "4", error: Exception | None = None) -> None:
        self.answer = answer
        self.error = error
        self.prompts: list[str] = []

    def ask(self, prompt: str) -> str:
        self.prompts.append(prompt)
        if self.error:
            raise self.error
        return self.answer


def authenticated_client(tmp_path, ai_client=None) -> TestClient:
    client = TestClient(
        create_app(
            database_path=tmp_path / "pm.db",
            session_secret="test-secret",
            ai_client=ai_client,
        )
    )
    client.post(
        "/api/login",
        json={"username": "user", "password": "password"},
    )
    return client


def test_client_sends_openai_compatible_request() -> None:
    def handle_request(request: httpx.Request) -> httpx.Response:
        assert request.url == "https://example.test/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["Content-Type"] == "application/json"
        assert request.read() == (
            b'{"model":"gpt-oss-120b","messages":'
            b'[{"role":"user","content":"2+2"}]}'
        )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": " 4 "}}]},
        )

    client = KodeKloudClient(
        "https://example.test/v1/",
        "test-key",
        transport=httpx.MockTransport(handle_request),
    )

    assert MODEL == "gpt-oss-120b"
    assert client.ask("2+2") == "4"


def test_client_requires_configuration() -> None:
    with pytest.raises(AIConfigurationError, match="not configured"):
        KodeKloudClient("", "")


def test_client_maps_timeout_without_exposing_configuration() -> None:
    def time_out(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret provider detail")

    client = KodeKloudClient(
        "https://secret.example/v1",
        "secret-key",
        transport=httpx.MockTransport(time_out),
    )

    with pytest.raises(AIProviderTimeout, match="timed out") as error:
        client.ask("2+2")

    assert "secret" not in str(error.value)


def test_client_maps_provider_error() -> None:
    client = KodeKloudClient(
        "https://example.test/v1",
        "test-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(503, text="provider detail")
        ),
    )

    with pytest.raises(AIProviderError, match="request failed"):
        client.ask("2+2")


@pytest.mark.parametrize(
    "payload",
    [{}, {"choices": []}, {"choices": [{"message": {"content": ""}}]}],
)
def test_client_rejects_invalid_responses(payload: dict) -> None:
    client = KodeKloudClient(
        "https://example.test/v1",
        "test-key",
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(200, json=payload)
        ),
    )

    with pytest.raises(AIProviderError, match="invalid response"):
        client.ask("2+2")


def test_diagnostic_asks_two_plus_two(tmp_path) -> None:
    ai_client = StubAIClient()
    client = authenticated_client(tmp_path, ai_client)

    response = client.post("/api/ai/diagnostic")

    assert response.status_code == 200
    assert response.json() == {"answer": "4"}
    assert ai_client.prompts == ["2+2"]


def test_diagnostic_requires_authentication(tmp_path) -> None:
    client = TestClient(
        create_app(database_path=tmp_path / "pm.db", ai_client=StubAIClient())
    )

    assert client.post("/api/ai/diagnostic").status_code == 401


def test_diagnostic_reports_missing_configuration(tmp_path) -> None:
    client = authenticated_client(tmp_path)

    response = client.post("/api/ai/diagnostic")

    assert response.status_code == 503
    assert response.json() == {"detail": "AI service is not configured"}


@pytest.mark.parametrize(
    ("error", "status_code", "detail"),
    [
        (AIProviderTimeout("secret timeout"), 504, "AI service timed out"),
        (AIProviderError("secret failure"), 502, "AI service request failed"),
    ],
)
def test_diagnostic_hides_provider_errors(
    tmp_path,
    error: Exception,
    status_code: int,
    detail: str,
) -> None:
    client = authenticated_client(tmp_path, StubAIClient(error=error))

    response = client.post("/api/ai/diagnostic")

    assert response.status_code == status_code
    assert response.json() == {"detail": detail}
    assert "secret" not in response.text