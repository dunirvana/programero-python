# Chamadas concorrentes com asyncio, timeout e degradação graciosa

API que monta um dashboard de cliente chamando três serviços ao mesmo tempo (perfil, pedidos e recomendações) com `asyncio.TaskGroup`. Cada chamada tem timeout e passa por um `Semaphore` que limita quantas ficam em voo. O perfil é obrigatório: se falhar, a requisição inteira falha. Pedidos e recomendações são opcionais: se estourarem o tempo ou devolverem erro, o dashboard sai sem eles e a resposta lista o que ficou de fora em `degraded`.

## Rodando

```bash
docker compose up --build
curl localhost:8000/customers/1/dashboard   # recomendações lentas: sai com degraded
curl localhost:8000/customers/99/dashboard  # 404
```

O serviço `upstream` simula as dependências. As recomendações demoram 2 segundos de propósito, mais que o timeout de 0,5 segundo da API. Ajuste `RECOMMENDATIONS_DELAY` e `UPSTREAM_TIMEOUT` no `docker-compose.yml` para ver o comportamento mudar.

## Testes

```bash
docker compose run --rm tests
```

Os testes trocam o upstream por um `httpx.MockTransport`, então não precisam de rede.

Post: https://programero.blogspot.com/2026/11/concurrent-calls-asyncio-taskgroup.html
