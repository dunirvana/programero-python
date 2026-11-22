import asyncio
import os

from fastapi import FastAPI, HTTPException

app = FastAPI()

CUSTOMERS = {
    1: {"id": 1, "name": "Alice Johnson"},
    2: {"id": 2, "name": "Bob Smith"},
    3: {"id": 3, "name": "Carol White"},
}

ORDERS_DELAY = float(os.getenv("ORDERS_DELAY", "0.2"))
RECOMMENDATIONS_DELAY = float(os.getenv("RECOMMENDATIONS_DELAY", "2.0"))


def get_customer_or_404(customer_id: int) -> dict:
    customer = CUSTOMERS.get(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    return customer


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/customers/{customer_id}")
async def get_customer(customer_id: int) -> dict:
    await asyncio.sleep(0.1)
    return get_customer_or_404(customer_id)


@app.get("/customers/{customer_id}/orders")
async def get_orders(customer_id: int) -> list[dict]:
    await asyncio.sleep(ORDERS_DELAY)
    get_customer_or_404(customer_id)
    return [{"id": 100 + customer_id, "total": 59.9}, {"id": 200 + customer_id, "total": 12.5}]


@app.get("/customers/{customer_id}/recommendations")
async def get_recommendations(customer_id: int) -> list[str]:
    await asyncio.sleep(RECOMMENDATIONS_DELAY)
    get_customer_or_404(customer_id)
    return ["keyboard", "monitor stand"]
