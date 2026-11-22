import asyncio
from typing import Any

import httpx
from pydantic import BaseModel


class CustomerNotFound(Exception):
    pass


class ProfileUnavailable(Exception):
    pass


class Section(BaseModel):
    data: Any = None
    error: str | None = None


class Dashboard(BaseModel):
    profile: dict[str, Any]
    orders: Section
    recommendations: Section
    degraded: list[str]


class DashboardAggregator:
    def __init__(
        self,
        client: httpx.AsyncClient,
        base_url: str,
        timeout: float = 0.5,
        max_concurrency: int = 10,
    ) -> None:
        self._client = client
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._limit = asyncio.Semaphore(max_concurrency)

    async def build(self, customer_id: int) -> Dashboard:
        try:
            async with asyncio.TaskGroup() as group:
                profile = group.create_task(self._fetch_profile(customer_id))
                orders = group.create_task(self._fetch_optional(f"/customers/{customer_id}/orders"))
                recommendations = group.create_task(
                    self._fetch_optional(f"/customers/{customer_id}/recommendations")
                )
        except ExceptionGroup as errors:
            if errors.subgroup(CustomerNotFound) is not None:
                raise CustomerNotFound(customer_id) from None
            raise ProfileUnavailable(customer_id) from errors

        sections = {"orders": orders.result(), "recommendations": recommendations.result()}
        degraded = [name for name, section in sections.items() if section.error]
        return Dashboard(profile=profile.result(), degraded=degraded, **sections)

    async def _fetch(self, path: str) -> Any:
        async with self._limit:
            async with asyncio.timeout(self._timeout):
                response = await self._client.get(f"{self._base_url}{path}")
                response.raise_for_status()
                return response.json()

    async def _fetch_profile(self, customer_id: int) -> dict[str, Any]:
        try:
            return await self._fetch(f"/customers/{customer_id}")
        except httpx.HTTPStatusError as error:
            if error.response.status_code == 404:
                raise CustomerNotFound(customer_id) from error
            raise

    async def _fetch_optional(self, path: str) -> Section:
        try:
            return Section(data=await self._fetch(path))
        except (TimeoutError, httpx.HTTPError):
            return Section(error="unavailable")
