from typing import Any, Protocol

import httpx

MODEL = "gpt-oss-120b"


class AIClient(Protocol):
    def ask(self, prompt: str) -> str: ...


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

    def ask(self, prompt: str) -> str:
        try:
            with httpx.Client(
                timeout=self.timeout,
                transport=self.transport,
            ) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": MODEL,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                response.raise_for_status()
        except httpx.TimeoutException as exception:
            raise AIProviderTimeout("KodeKloud AI request timed out") from exception
        except httpx.HTTPError as exception:
            raise AIProviderError("KodeKloud AI request failed") from exception

        return self._content(response.json())

    @staticmethod
    def _content(payload: dict[str, Any]) -> str:
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exception:
            raise AIProviderError("KodeKloud AI returned an invalid response") from exception
        if not isinstance(content, str) or not content.strip():
            raise AIProviderError("KodeKloud AI returned an invalid response")
        return content.strip()