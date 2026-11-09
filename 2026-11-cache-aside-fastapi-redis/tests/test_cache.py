import asyncio
import copy

import fakeredis
import httpx
import pytest

from app import main
from app.main import Repositorio, create_app


@pytest.fixture(autouse=True)
def restaurar_produtos():
    original = copy.deepcopy(main.PRODUTOS)
    yield
    main.PRODUTOS.clear()
    main.PRODUTOS.update(original)


def novo_app(latencia: float = 0.01):
    repo = Repositorio(latencia=latencia)
    cliente = fakeredis.FakeAsyncRedis(decode_responses=True)
    return create_app(cliente, repo), repo


def cliente_http(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


def rodar(coro):
    return asyncio.run(coro)


def test_primeira_leitura_vem_do_banco_e_segunda_do_cache():
    async def cenario():
        app, repo = novo_app()
        async with cliente_http(app) as c:
            a = (await c.get("/produtos/1")).json()
            b = (await c.get("/produtos/1")).json()
        return a, b, repo.consultas

    a, b, consultas = rodar(cenario())
    assert a["origem"] == "banco"
    assert b["origem"] == "cache"
    assert consultas == 1


def test_produto_inexistente_retorna_404_e_nao_vai_para_o_cache():
    async def cenario():
        app, _ = novo_app()
        async with cliente_http(app) as c:
            r1 = await c.get("/produtos/999")
            r2 = await c.get("/produtos/999")
        return r1.status_code, r2.status_code

    assert rodar(cenario()) == (404, 404)


def test_atualizar_invalida_o_cache():
    async def cenario():
        app, repo = novo_app()
        async with cliente_http(app) as c:
            await c.get("/produtos/2")
            await c.put("/produtos/2", json={"preco": 999.0})
            depois = (await c.get("/produtos/2")).json()
        return depois, repo.consultas

    depois, consultas = rodar(cenario())
    assert depois["origem"] == "banco"
    assert depois["produto"]["preco"] == 999.0
    assert consultas == 2


def test_requisicoes_simultaneas_geram_uma_unica_consulta():
    async def cenario():
        app, repo = novo_app(latencia=0.1)
        async with cliente_http(app) as c:
            respostas = await asyncio.gather(*[c.get("/produtos/1") for _ in range(10)])
        return [r.json()["origem"] for r in respostas], repo.consultas

    origens, consultas = rodar(cenario())
    assert consultas == 1
    assert origens.count("banco") == 1
    assert origens.count("cache") == 9


def test_ttl_e_definido_na_chave():
    async def cenario():
        app, _ = novo_app()
        async with cliente_http(app) as c:
            await c.get("/produtos/1")
        return await app.state.redis.ttl("produto:1")

    ttl = rodar(cenario())
    assert 0 < ttl <= main.TTL_SEGUNDOS


def test_health():
    async def cenario():
        app, _ = novo_app()
        async with cliente_http(app) as c:
            return (await c.get("/health")).json()

    assert rodar(cenario()) == {"status": "ok"}
