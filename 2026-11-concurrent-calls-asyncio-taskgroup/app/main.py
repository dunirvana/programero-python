import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request

from app.aggregator import CustomerNotFound, Dashboard, DashboardAggregator, ProfileUnavailable


def create_app(transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(transport=transport) as client:
            app.state.aggregator = DashboardAggregator(
                client,
                base_url=os.getenv("UPSTREAM_URL", "http://upstream:9000"),
                timeout=float(os.getenv("UPSTREAM_TIMEOUT", "0.5")),
                max_concurrency=int(os.getenv("MAX_CONCURRENCY", "10")),
            )
            yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/customers/{customer_id}/dashboard", response_model=Dashboard)
    async def get_dashboard(customer_id: int, request: Request) -> Dashboard:
        try:
            return await request.app.state.aggregator.build(customer_id)
        except CustomerNotFound:
            raise HTTPException(status_code=404, detail="customer not found")
        except ProfileUnavailable:
            raise HTTPException(status_code=502, detail="customer service unavailable")

    return app


app = create_app()
