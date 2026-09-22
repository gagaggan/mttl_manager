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
