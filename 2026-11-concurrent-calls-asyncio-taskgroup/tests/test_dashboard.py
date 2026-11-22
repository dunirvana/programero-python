import asyncio
import time

import httpx
import pytest
import pytest_asyncio

from app.aggregator import CustomerNotFound, DashboardAggregator, ProfileUnavailable
from app.main import create_app

BASE_URL = "http://upstream.test"


class FakeUpstream:
    def __init__(self, delays: dict[str, float] | None = None, failing: set[str] | None = None):
        self.delays = delays or {}
        self.failing = failing or set()
        self.in_flight = 0
        self.max_in_flight = 0

    async def __call__(self, request: httpx.Request) -> httpx.Response:
        kind = request.url.path.rsplit("/", 1)[-1]
        kind = kind if kind in ("orders", "recommendations") else "profile"
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            await asyncio.sleep(self.delays.get(kind, 0))
        finally:
            self.in_flight -= 1
        if kind in self.failing:
            return httpx.Response(500)
        if request.url.path.startswith("/customers/404"):
            return httpx.Response(404)
        payloads = {
            "profile": {"id": 1, "name": "Alice Johnson"},
            "orders": [{"id": 101, "total": 59.9}],
            "recommendations": ["keyboard"],
        }
        return httpx.Response(200, json=payloads[kind])


def make_aggregator(upstream: FakeUpstream, **options) -> tuple[DashboardAggregator, httpx.AsyncClient]:
    client = httpx.AsyncClient(transport=httpx.MockTransport(upstream))
    return DashboardAggregator(client, BASE_URL, **options), client


async def test_returns_all_sections_when_upstream_is_healthy():
    aggregator, client = make_aggregator(FakeUpstream())
    async with client:
        dashboard = await aggregator.build(1)

    assert dashboard.profile["name"] == "Alice Johnson"
    assert dashboard.orders.data == [{"id": 101, "total": 59.9}]
    assert dashboard.recommendations.data == ["keyboard"]
    assert dashboard.degraded == []


async def test_calls_run_concurrently():
    upstream = FakeUpstream(delays={"profile": 0.2, "orders": 0.2, "recommendations": 0.2})
    aggregator, client = make_aggregator(upstream, timeout=1.0)
    async with client:
        started = time.perf_counter()
        await aggregator.build(1)
        elapsed = time.perf_counter() - started

    assert upstream.max_in_flight == 3
    assert elapsed < 0.5


async def test_semaphore_limits_in_flight_calls():
    upstream = FakeUpstream(delays={"profile": 0.05, "orders": 0.05, "recommendations": 0.05})
    aggregator, client = make_aggregator(upstream, timeout=1.0, max_concurrency=1)
    async with client:
        await aggregator.build(1)

    assert upstream.max_in_flight == 1


async def test_slow_optional_call_degrades_instead_of_failing():
    upstream = FakeUpstream(delays={"recommendations": 1.0})
    aggregator, client = make_aggregator(upstream, timeout=0.1)
    async with client:
        dashboard = await aggregator.build(1)

    assert dashboard.recommendations.error == "unavailable"
    assert dashboard.recommendations.data is None
    assert dashboard.orders.data is not None
    assert dashboard.degraded == ["recommendations"]


async def test_failing_optional_call_degrades():
    aggregator, client = make_aggregator(FakeUpstream(failing={"orders"}))
    async with client:
        dashboard = await aggregator.build(1)

    assert dashboard.degraded == ["orders"]


async def test_profile_failure_cancels_the_whole_request():
    aggregator, client = make_aggregator(FakeUpstream(failing={"profile"}))
    async with client:
        with pytest.raises(ProfileUnavailable):
            await aggregator.build(1)


async def test_unknown_customer_raises_not_found():
    aggregator, client = make_aggregator(FakeUpstream())
    async with client:
        with pytest.raises(CustomerNotFound):
            await aggregator.build(404)


@pytest_asyncio.fixture
async def api_client(monkeypatch):
    monkeypatch.setenv("UPSTREAM_URL", BASE_URL)
    monkeypatch.setenv("UPSTREAM_TIMEOUT", "0.1")
    upstream = FakeUpstream(delays={"recommendations": 1.0})
    app = create_app(transport=httpx.MockTransport(upstream))
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://api.test") as client:
            yield client


async def test_endpoint_returns_degraded_dashboard(api_client):
    response = await api_client.get("/customers/1/dashboard")

    assert response.status_code == 200
    body = response.json()
    assert body["profile"]["name"] == "Alice Johnson"
    assert body["degraded"] == ["recommendations"]


async def test_endpoint_returns_404_for_unknown_customer(api_client):
    response = await api_client.get("/customers/404/dashboard")

    assert response.status_code == 404
