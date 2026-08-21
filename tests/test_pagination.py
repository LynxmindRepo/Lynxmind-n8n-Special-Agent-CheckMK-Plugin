"""Self-check for N8nMonitor._fetch_all_executions pagination.

No framework: run directly, asserts raise on failure.

    python tests/test_pagination.py
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "n8n_cmk" / "special_agents"))
from agent_n8n import N8nMonitor  # noqa: E402


def _exec(minutes_ago: int) -> dict:
    started = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
    return {"id": str(minutes_ago), "startedAt": started.isoformat().replace("+00:00", "Z")}


class FakeResponse:
    def __init__(self, payload):
        self.status = 200
        self.headers = {"content-type": "application/json"}
        self._payload = payload

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Serves pre-built pages in order, one per call to .get()."""

    def __init__(self, pages):
        self._pages = list(pages)
        self.calls = []

    def get(self, url, headers=None, params=None):
        self.calls.append(dict(params or {}))
        page = self._pages.pop(0) if self._pages else {"data": [], "nextCursor": None}
        return FakeResponse(page)


async def test_stops_when_cursor_exhausted():
    session = FakeSession([
        {"data": [_exec(1), _exec(2)], "nextCursor": "abc"},
        {"data": [_exec(3)], "nextCursor": None},
    ])
    mon = N8nMonitor("http://n8n.local")
    mon.session = session
    result = await mon._fetch_all_executions(activation_time=None)
    assert len(result) == 3, result
    assert len(session.calls) == 2
    assert session.calls[1]["cursor"] == "abc"


async def test_stops_early_at_activation_time():
    # Newest-first pages; page 2's oldest entry (200min ago) predates activation.
    activation = datetime.now(timezone.utc) - timedelta(minutes=60)
    session = FakeSession([
        {"data": [_exec(10), _exec(20)], "nextCursor": "p2"},
        {"data": [_exec(90), _exec(200)], "nextCursor": "p3"},  # should not be fetched
        {"data": [_exec(300)], "nextCursor": None},
    ])
    mon = N8nMonitor("http://n8n.local")
    mon.session = session
    result = await mon._fetch_all_executions(activation_time=activation)
    # page 3 must never be requested: page 2 already crosses the boundary
    assert len(session.calls) == 2, session.calls
    # only executions newer than activation_time survive the filter
    assert len(result) == 2, result


async def test_max_pages_safety_cap():
    # Every page still has a cursor and stays newer than activation - would
    # loop forever without the cap.
    activation = datetime.now(timezone.utc) - timedelta(days=365)
    pages = [{"data": [_exec(1)], "nextCursor": f"p{i}"} for i in range(100)]
    session = FakeSession(pages)
    mon = N8nMonitor("http://n8n.local")
    mon.session = session
    result = await mon._fetch_all_executions(activation_time=activation, max_pages=5)
    assert len(session.calls) == 5, session.calls
    assert len(result) == 5, result


async def test_raises_on_http_error():
    session = MagicMock()
    bad_response = FakeResponse({})
    bad_response.status = 500
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=bad_response)
    ctx.__aexit__ = AsyncMock(return_value=False)
    session.get = MagicMock(return_value=ctx)
    mon = N8nMonitor("http://n8n.local")
    mon.session = session
    try:
        await mon._fetch_all_executions(activation_time=None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError on HTTP 500")


async def main():
    await test_stops_when_cursor_exhausted()
    await test_stops_early_at_activation_time()
    await test_max_pages_safety_cap()
    await test_raises_on_http_error()
    print("all pagination checks passed")


if __name__ == "__main__":
    asyncio.run(main())
