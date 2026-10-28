"""The dev server (python3 server.py) must keep answering while a browser holds idle connections, and serve its mock API."""
import json
import socket
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server  # noqa: E402

pytestmark = pytest.mark.full


@pytest.fixture
def base_url():
    httpd = server.ThreadedServer(("127.0.0.1", 0), server.InvestmentHandler)
    server.PORT = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.PORT}"
    httpd.shutdown()
    httpd.server_close()


def test_server_answers_while_an_idle_connection_is_open(base_url):
    port = int(base_url.rsplit(":", 1)[1])
    idle = socket.create_connection(("127.0.0.1", port))  # a browser preconnect sends nothing
    try:
        with urllib.request.urlopen(f"{base_url}/auth.html", timeout=5) as response:
            assert response.status == 200
    finally:
        idle.close()


def test_benchmark_returns_route_does_not_crash(base_url):
    with urllib.request.urlopen(f"{base_url}/benchmark-returns?benchmarkId=WIG&from=2010-01", timeout=5) as response:
        assert response.status == 200
        assert isinstance(json.loads(response.read()), (dict, list))
