import importlib.util
import io
import json
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / 'mttl_client.py'
SPEC = importlib.util.spec_from_file_location('mttl_client_under_test', MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MAX_RESPONSE_BYTES = MODULE.MAX_RESPONSE_BYTES
MTTLClient = MODULE.MTTLClient
MTTLClientError = MODULE.MTTLClientError


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.stream = io.BytesIO(payload)

    def read(self, size=-1):
        return self.stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_accepts_loopback_and_private_backend_urls():
    assert MTTLClient.validate_base_url('http://127.0.0.1:8080/') == 'http://127.0.0.1:8080'
    assert MTTLClient.validate_base_url('http://192.168.29.230:8080') == 'http://192.168.29.230:8080'
    assert MTTLClient.validate_base_url('https://mttl.example.com/') == 'https://mttl.example.com'


@pytest.mark.parametrize(
    'value',
    [
        'ftp://192.168.29.230',
        'http://user:password@192.168.29.230:8080',
        'http://8.8.8.8:8080',
        'http://example.com:8080',
        'http://192.168.29.230:8080/api/health',
    ],
)
def test_rejects_unsafe_backend_urls(value):
    with pytest.raises(ValueError):
        MTTLClient.validate_base_url(value)


def test_health_parses_bounded_json_response():
    payload = {'status': 'ok'}
    opener = lambda request, timeout: FakeResponse(json.dumps(payload).encode())
    result = MTTLClient(opener=opener).health()
    assert result['ok'] is True
    assert result['status_code'] == 200
    assert result['payload'] == payload


def test_health_rejects_oversized_response():
    opener = lambda request, timeout: FakeResponse(b'x' * (MAX_RESPONSE_BYTES + 1))
    result = MTTLClient(opener=opener).health()
    assert result['ok'] is False
    assert result['error'] == 'Health response is too large'

class FakeAdminOpener:
    def __init__(self, must_change=False):
        self.must_change = must_change
        self.calls = []

    def open(self, request, timeout):
        payload = json.loads(request.data.decode()) if request.data else None
        self.calls.append((request.get_method(), request.full_url, payload))
        if request.full_url.endswith('/api/auth/login'):
            return FakeResponse(json.dumps({'authenticated': True, 'must_change_password': self.must_change}).encode())
        if request.full_url.endswith('/api/auth/logout'):
            return FakeResponse(b'{"ok":true}')
        if request.full_url.endswith('/api/ha'):
            return FakeResponse(b'{"enabled":true,"connected":true,"password_set":true}')
        raise AssertionError(request.full_url)


def test_admin_request_uses_ephemeral_login_and_logout():
    opener = FakeAdminOpener()
    client = MTTLClient(
        base_url='http://192.168.29.230:8080',
        admin_opener_factory=lambda: opener,
    )
    result = client.admin_request('secret-value', 'GET', '/api/ha')
    assert result['connected'] is True
    assert [call[1].rsplit('/', 1)[-1] for call in opener.calls] == ['login', 'ha', 'logout']
    assert not hasattr(client, 'admin_password')


def test_default_admin_password_blocks_mutation_and_logs_out():
    opener = FakeAdminOpener(must_change=True)
    client = MTTLClient(admin_opener_factory=lambda: opener)
    with pytest.raises(MTTLClientError, match='기본 관리자 암호'):
        client.admin_request('admin', 'PUT', '/api/ha', {}, require_changed_password=True)
    assert opener.calls[-1][1].endswith('/api/auth/logout')


@pytest.mark.parametrize('host', ['192.168.29.178', '10.0.0.2', '127.0.0.1'])
def test_accepts_private_mqtt_hosts(host):
    assert MTTLClient.validate_mqtt_host(host) == host


@pytest.mark.parametrize('host', ['', 'example.com', '8.8.8.8'])
def test_rejects_non_private_mqtt_hosts(host):
    with pytest.raises(ValueError):
        MTTLClient.validate_mqtt_host(host)
