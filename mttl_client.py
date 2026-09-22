"""Small, defensive client for the local MTTL-W01 backend."""

from __future__ import annotations

import ipaddress
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen


MAX_RESPONSE_BYTES = 64 * 1024


class MTTLClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        timeout: float = 3.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.timeout = timeout
        self.opener = opener
        self.base_url = self.validate_base_url(base_url)

    @staticmethod
    def validate_base_url(value: str) -> str:
        parsed = urlsplit(str(value).strip())
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Backend URL must use http or https")
        if parsed.username or parsed.password:
            raise ValueError("Credentials must not be embedded in the backend URL")
        if not parsed.hostname:
            raise ValueError("Backend URL must include a host")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("Backend URL must not include a path, query, or fragment")

        host = parsed.hostname
        if host != "localhost":
            try:
                address = ipaddress.ip_address(host)
            except ValueError as exc:
                raise ValueError("Backend host must be localhost or a private IP address") from exc
            if not (address.is_private or address.is_loopback or address.is_link_local):
                raise ValueError("Backend host must be on a private network")

        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Backend URL contains an invalid port") from exc

        netloc = f"[{host}]" if ":" in host else host
        if port is not None:
            netloc = f"{netloc}:{port}"
        return urlunsplit((parsed.scheme, netloc, "", "", ""))

    def configure(self, base_url: str) -> None:
        self.base_url = self.validate_base_url(base_url)

    def health(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/health"
        request = Request(url, headers={"Accept": "application/json", "User-Agent": "FlaskFarm-MTTL-Manager/0.1"})
        try:
            with self.opener(request, timeout=self.timeout) as response:
                status = int(getattr(response, "status", 200))
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError("Health response is too large")
                payload = json.loads(raw.decode("utf-8")) if raw else {}
                return {
                    "ok": 200 <= status < 300,
                    "status_code": status,
                    "payload": payload,
                    "url": url,
                    "error": "",
                }
        except (HTTPError, URLError, TimeoutError, OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            return {
                "ok": False,
                "status_code": getattr(exc, "code", None),
                "payload": {},
                "url": url,
                "error": str(exc),
            }
