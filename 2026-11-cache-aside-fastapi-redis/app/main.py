import asyncio
import json
import os

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Request

TTL_SEGUNDOS = int(os.getenv("CACHE_TTL", "30"))

# "Banco de dados" de mentira, só para ter algo lento para cachear.
PRODUTOS = {
    1: {"id": 1, "nome": "Teclado mecânico", "preco": 349.9},
    2: {"id": 2, "nome": "Monitor 27 polegadas", "preco": 1499.0},
}


class Repositorio:
    def __init__(self, latencia: float = 0.2):
        self.latencia = latencia
        self.consultas = 0

    async def buscar(self, produto_id: int) -> dict | None:
        self.consultas += 1
        await asyncio.sleep(self.latencia)
        return PRODUTOS.get(produto_id)


def create_app(cliente: redis.Redis | None = None, repo: Repositorio | None = None) -> FastAPI:
    app = FastAPI(title="Cache-aside com Redis")
    app.state.redis = cliente or redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True
    )
    app.state.repo = repo or Repositorio()
    app.state.locks: dict[int, asyncio.Lock] = {}

    def chave(produto_id: int) -> str:
        return f"produto:{produto_id}"

    @app.get("/produtos/{produto_id}")
    async def obter(produto_id: int, request: Request):
        r: redis.Redis = request.app.state.redis
        repo: Repositorio = request.app.state.repo

        em_cache = await r.get(chave(produto_id))
        if em_cache:
            return {"origem": "cache", "produto": json.loads(em_cache)}

        # Single flight: só uma requisição vai ao "banco" por chave;
        # as demais esperam e reaproveitam o resultado.
        lock = request.app.state.locks.setdefault(produto_id, asyncio.Lock())
        async with lock:
            em_cache = await r.get(chave(produto_id))
            if em_cache:
                return {"origem": "cache", "produto": json.loads(em_cache)}

            produto = await repo.buscar(produto_id)
            if produto is None:
                raise HTTPException(status_code=404, detail="Produto não encontrado")

            await r.set(chave(produto_id), json.dumps(produto), ex=TTL_SEGUNDOS)
            return {"origem": "banco", "produto": produto}

    @app.put("/produtos/{produto_id}")
    async def atualizar(produto_id: int, dados: dict, request: Request):
        if produto_id not in PRODUTOS:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        PRODUTOS[produto_id] = {**PRODUTOS[produto_id], **dados, "id": produto_id}
        # Invalida o cache: a próxima leitura volta ao banco.
        await request.app.state.redis.delete(chave(produto_id))
        return PRODUTOS[produto_id]

    @app.get("/health")
    async def health(request: Request):
        await request.app.state.redis.ping()
        return {"status": "ok"}

    return app


def _criar_padrao() -> FastAPI:
    return create_app()


app = _criar_padrao()
