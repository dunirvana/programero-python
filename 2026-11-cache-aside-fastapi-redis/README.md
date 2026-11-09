# Cache-aside com FastAPI e Redis

API pequena que lê produtos usando o padrão cache-aside: tenta o Redis, cai no "banco" (simulado, com latência) só quando precisa, grava com TTL e invalida o cache quando o produto muda. Requisições simultâneas para a mesma chave fazem uma única consulta.

## Rodando

```bash
docker compose up --build
curl localhost:8000/produtos/1   # origem: banco
curl localhost:8000/produtos/1   # origem: cache
```

## Testes

```bash
docker compose run --rm tests
```

Os testes usam fakeredis, então não dependem de um Redis de verdade.

Post: https://programero.blogspot.com/2026/11/cache-aside-fastapi-redis.html
