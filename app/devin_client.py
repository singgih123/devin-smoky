from __future__ import annotations

import httpx

from app.types import JSONObject, JSONValue


class DevinConfigurationError(RuntimeError):
    pass


class DevinClient:
    def __init__(self, api_key: str, org_id: str, base_url: str) -> None:
        self.api_key = api_key
        self.org_id = org_id
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        if not self.api_key or not self.org_id:
            raise DevinConfigurationError("DEVIN_API_KEY and DEVIN_ORG_ID must be configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _session_url(self, session_id: str) -> str:
        normalized_id = normalize_session_id(session_id)
        return f"{self.base_url}/organizations/{self.org_id}/sessions/{normalized_id}"

    async def create_session(self, prompt: str) -> str:
        url = f"{self.base_url}/organizations/{self.org_id}/sessions"
        data = await self._request("POST", url, {"prompt": prompt})
        session_id = extract_session_id(data)
        if not session_id:
            raise RuntimeError("Devin API did not return a session ID")
        return session_id

    async def send_message(self, session_id: str, message: str) -> None:
        url = f"{self._session_url(session_id)}/messages"
        await self._request("POST", url, {"message": message})

    async def list_messages(self, session_id: str) -> JSONObject:
        url = f"{self._session_url(session_id)}/messages"
        return await self._request("GET", url, None)

    async def _request(self, method: str, url: str, payload: JSONObject | None) -> JSONObject:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(method, url, headers=self._headers(), json=payload)
        response.raise_for_status()
        data: JSONValue = response.json()
        if isinstance(data, dict):
            return data
        return {"value": data}


def normalize_session_id(session_id: str) -> str:
    session_id = session_id.strip()
    if not session_id:
        return session_id
    if session_id.startswith("devin-"):
        return session_id
    return f"devin-{session_id}"


def session_web_url(session_id: str) -> str:
    session_id = normalize_session_id(session_id)
    web_id = session_id.removeprefix("devin-")
    return f"https://app.devin.ai/sessions/{web_id}"


def extract_session_id(data: JSONObject) -> str | None:
    for key in ("devin_id", "session_id", "id"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return normalize_session_id(value)
    session_value = data.get("session")
    if isinstance(session_value, dict):
        return extract_session_id(session_value)
    return None


def message_text(message: JSONObject) -> str:
    for key in ("message", "content", "text", "body"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def message_author(message: JSONObject) -> str:
    for key in ("role", "author", "speaker", "sender"):
        value = message.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "message"


def extract_message_items(data: JSONObject) -> list[JSONObject]:
    for key in ("messages", "data", "items", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def format_recent_messages(data: JSONObject, limit: int = 5) -> str:
    items = extract_message_items(data)[-limit:]
    if not items:
        return "Belum ada pesan yang bisa ditampilkan."

    lines: list[str] = []
    for item in items:
        text = message_text(item)
        if text:
            lines.append(f"{message_author(item)}: {text}")
    return "\n\n".join(lines) if lines else "Belum ada pesan teks yang bisa ditampilkan."
