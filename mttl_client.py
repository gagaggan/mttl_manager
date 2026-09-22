"""Small, defensive client for the local MTTL-W01 backend."""

from __future__ import annotations

import ipaddress
import json
import re
from http.cookiejar import CookieJar
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


MAX_RESPONSE_BYTES = 64 * 1024


class MTTLClientError(RuntimeError):
    """A safe, user-facing MTTL API error."""


class MTTLClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8080",
        timeout: float = 3.0,
        opener: Callable[..., Any] = urlopen,
        admin_opener_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.timeout = timeout
        self.opener = opener
        self.admin_opener_factory = admin_opener_factory or (
            lambda: build_opener(HTTPCookieProcessor(CookieJar()))
        )
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

        host = parsed.hostname.lower()
        if host != "localhost":
            try:
                address = ipaddress.ip_address(host)
            except ValueError:
                address = None
            if address is not None:
                if not (address.is_private or address.is_loopback or address.is_link_local):
                    raise ValueError("Public IP backend URLs are not allowed; use an HTTPS hostname")
            else:
                hostname_pattern = r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
                if not re.fullmatch(hostname_pattern, host):
                    raise ValueError("Backend hostname is invalid")
                if parsed.scheme != "https":
                    raise ValueError("NPM/public hostnames must use HTTPS")

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

    @staticmethod
    def validate_mqtt_host(value: str) -> str:
        host = str(value or "").strip()
        if not host:
            raise ValueError("MQTT Broker 주소가 필요합니다")
        try:
            address = ipaddress.ip_address(host)
        except ValueError as exc:
            raise ValueError("MQTT Broker는 사설 IP 주소로 입력하세요") from exc
        if not (address.is_private or address.is_loopback or address.is_link_local):
            raise ValueError("MQTT Broker는 사설 IP 주소만 허용됩니다")
        return host

    @staticmethod
    def validate_topic(value: str, label: str) -> str:
        topic = str(value or "").strip().strip("/")
        if not topic or "+" in topic or "#" in topic or "\x00" in topic:
            raise ValueError(f"{label}이 올바르지 않습니다")
        return topic

    def _admin_json(self, opener: Any, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": "FlaskFarm-MTTL-Manager/0.2",
        }
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with opener.open(request, timeout=max(self.timeout, 8.0)) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise MTTLClientError("백엔드 응답이 너무 큽니다")
                result = json.loads(raw.decode("utf-8")) if raw else {}
                if not isinstance(result, dict):
                    raise MTTLClientError("백엔드 JSON 응답 형식이 올바르지 않습니다")
                return result
        except HTTPError as exc:
            try:
                raw = exc.read(MAX_RESPONSE_BYTES + 1)
                body = json.loads(raw.decode("utf-8")) if raw else {}
                message = body.get("error") if isinstance(body, dict) else None
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                message = None
            raise MTTLClientError(message or f"백엔드 HTTP 오류 {exc.code}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise MTTLClientError(f"MTTL 백엔드 연결 실패: {exc}") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise MTTLClientError("백엔드 JSON 응답을 읽을 수 없습니다") from exc

    def admin_request(
        self,
        admin_password: str,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        require_changed_password: bool = False,
    ) -> dict[str, Any]:
        password = str(admin_password or "")
        if not password:
            raise ValueError("MTTL 관리자 암호를 입력하세요")
        opener = self.admin_opener_factory()
        logged_in = False
        login: dict[str, Any] = {}
        try:
            login = self._admin_json(opener, "POST", "/api/auth/login", {"password": password})
            logged_in = bool(login.get("authenticated"))
            if not logged_in:
                raise MTTLClientError("MTTL 관리자 인증에 실패했습니다")
            if require_changed_password and login.get("must_change_password"):
                raise MTTLClientError("MTTL 기본 관리자 암호를 먼저 웹 UI에서 변경하세요")
            result = self._admin_json(opener, method, path, payload)
            result["must_change_password"] = bool(login.get("must_change_password"))
            return result
        finally:
            if logged_in:
                try:
                    self._admin_json(opener, "POST", "/api/auth/logout")
                except MTTLClientError:
                    pass
