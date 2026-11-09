# programero-python

Projetos de exemplo em Python dos posts do blog [PROGRAMERO](https://programero.blogspot.com).

Cada pasta é um projeto independente, ligado a um post. Para rodar qualquer um deles basta ter o Docker instalado:

```bash
cd <pasta-do-projeto>
docker compose up --build
```

E para rodar os testes:

```bash
docker compose run --rm tests
```

## Projetos

| Projeto | Post |
|---|---|
| [2026-11-cache-aside-fastapi-redis](2026-11-cache-aside-fastapi-redis) | [Cache-aside com FastAPI e Redis](https://programero.blogspot.com/2026/11/cache-aside-fastapi-redis.html) |
