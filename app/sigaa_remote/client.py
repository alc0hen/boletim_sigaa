import json
import logging
import os
import time

import httpx

from .errors import (
    RemoteApiError,
    RemoteInvalidCredentials,
    RemoteQuestionnaireError,
    RemoteSessionExpired,
    RemoteUnavailable,
)
from .signer import RequestSigner

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 45.0
HISTORY_TIMEOUT = 240.0
DETAILS_TIMEOUT = 90.0
HEALTH_TIMEOUT = 5.0
HEALTH_CACHE_SECONDS = 30.0


def is_configured() -> bool:
    return bool(
        os.environ.get("SIGAA_API_URL")
        and os.environ.get("SIGAA_API_PRIVATE_KEY")
    )


class SigaaRemoteClient:
    def __init__(self, base_url=None, private_key=None):
        base_url = base_url or os.environ.get("SIGAA_API_URL", "")
        self.base_url = base_url.rstrip("/")
        self._signer = RequestSigner(private_key or os.environ["SIGAA_API_PRIVATE_KEY"])
        self.public_key = self._signer.public_key_hex
        self._http = None
        self._health_checked_at = 0.0
        self._health_ok = False

    def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(base_url=self.base_url, timeout=DEFAULT_TIMEOUT)
        return self._http

    async def aclose(self):
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
        self._http = None

    def _path(self, suffix: str) -> str:
        return f"/api/v1/{self.public_key}{suffix}"

    @staticmethod
    def _raise_for_payload(status_code: int, payload: dict):
        code = payload.get("code")
        detail = payload.get("detail") or payload.get("message")

        if code in ("session_not_found", "sigaa_session_expired"):
            raise RemoteSessionExpired(status_code, code, detail)
        if code == "questionnaire":
            raise RemoteQuestionnaireError(status_code, code, detail)
        if code == "invalid_credentials":
            raise RemoteInvalidCredentials(status_code, code, detail)
        raise RemoteApiError(status_code, code, detail)

    async def _request(self, method: str, suffix: str, body: dict = None, timeout=None):
        path = self._path(suffix)
        raw = json.dumps(body).encode("utf-8") if body is not None else b""
        headers = self._signer.headers(method, path, raw)
        if body is not None:
            headers["Content-Type"] = "application/json"

        try:
            response = await self._client().request(
                method,
                path,
                content=raw if body is not None else None,
                headers=headers,
                timeout=timeout or DEFAULT_TIMEOUT,
            )
        except httpx.HTTPError as e:
            self._health_ok = False
            self._health_checked_at = time.monotonic()
            raise RemoteUnavailable(f"API do SIGAA inacessível: {e}") from e

        if response.status_code >= 500:
            self._health_ok = False
            self._health_checked_at = time.monotonic()
            raise RemoteUnavailable(f"API do SIGAA respondeu {response.status_code}.")

        if response.status_code >= 400:
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            self._raise_for_payload(response.status_code, payload)

        if not response.content:
            return {}
        return response.json()

    async def healthy(self, force: bool = False) -> bool:
        now = time.monotonic()
        if not force and (now - self._health_checked_at) < HEALTH_CACHE_SECONDS:
            return self._health_ok

        try:
            response = await self._client().get("/healthz", timeout=HEALTH_TIMEOUT)
            self._health_ok = response.status_code == 200
        except httpx.HTTPError as e:
            logger.warning("Health check da API do SIGAA falhou: %s", e)
            self._health_ok = False
        self._health_checked_at = now
        return self._health_ok

    async def create_session(self, url: str, institution: str, username: str, password: str):
        return await self._request(
            "POST",
            "/sessions",
            {
                "url": url,
                "institution": institution,
                "username": username,
                "password": password,
            },
        )

    async def list_bonds(self, session_id: str):
        return await self._request("GET", f"/sessions/{session_id}/bonds")

    async def list_courses(self, session_id: str, bond_id: str):
        return await self._request(
            "GET", f"/sessions/{session_id}/bonds/{bond_id}/courses", timeout=DETAILS_TIMEOUT
        )

    async def course_details(self, session_id: str, bond_id: str, course_id: int):
        return await self._request(
            "GET",
            f"/sessions/{session_id}/bonds/{bond_id}/courses/{course_id}/details",
            timeout=DETAILS_TIMEOUT,
        )

    async def history(self, session_id: str, bond_id: str, cached_history=None, parallel=True):
        return await self._request(
            "POST",
            f"/sessions/{session_id}/bonds/{bond_id}/history",
            {"cached_history": cached_history, "parallel": parallel},
            timeout=HISTORY_TIMEOUT,
        )

    async def enrollment_disciplines(self, session_id: str, bond_id: str):
        return await self._request(
            "GET",
            f"/sessions/{session_id}/bonds/{bond_id}/enrollment",
            timeout=DETAILS_TIMEOUT,
        )

    async def enrollment_selection(self, session_id: str, bond_id: str, selected_class_ids):
        return await self._request(
            "POST",
            f"/sessions/{session_id}/bonds/{bond_id}/enrollment/selection",
            {"selected_class_ids": [str(c) for c in selected_class_ids]},
            timeout=DETAILS_TIMEOUT,
        )

    async def enrollment_confirm(self, session_id: str, bond_id: str, password: str):
        return await self._request(
            "POST",
            f"/sessions/{session_id}/bonds/{bond_id}/enrollment/confirm",
            {"password": password},
            timeout=DETAILS_TIMEOUT,
        )

    async def close_session(self, session_id: str):
        return await self._request("DELETE", f"/sessions/{session_id}")


_client = None


def get_client():
    global _client
    if not is_configured():
        return None
    if _client is None:
        _client = SigaaRemoteClient()
    return _client


async def close_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
