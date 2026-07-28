"""Cliente assíncrono da API do TMDB.

Responsabilidades, e só elas:

* **autenticação** — aceita tanto a chave v3 (`api_key` na query) quanto o
  *read access token* v4 (JWT no header `Authorization`). O TMDB entrega os
  dois na mesma tela e é fácil colar o errado; aqui os dois funcionam.
* **rate limit** — o TMDB derruba quem passa de ~50 requisições por segundo.
  Um throttle no cliente é mais barato que descobrir isso por 429 em produção.
* **retry** — 429 e 5xx são transitórios: backoff exponencial com jitter.
  401 e 404 não são: falham na hora, sem gastar quatro tentativas.
* **timeout explícito** — sem timeout, uma conexão pendurada trava o cron
  semanal inteiro sem deixar rastro.

O que este módulo **não** faz: não valida o contrato (`ingestion.models`) e
não grava nada (`ingestion.loaders`). Ele devolve o JSON como veio.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    before_sleep_log,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from ingestion.logging_config import get_logger

log = get_logger(__name__)

BASE_URL = "https://api.themoviedb.org/3"

# O TMDB anuncia ~50 req/s. Ficamos deliberadamente abaixo: a ingestão é
# semanal e não tem pressa nenhuma, mas ser bloqueada custa a janela inteira.
MAX_RPS_PADRAO = 20.0
TIMEOUT_PADRAO = 15.0
MAX_TENTATIVAS_PADRAO = 5


class TMDBError(RuntimeError):
    """Falha ao falar com o TMDB."""


class TMDBTransientError(TMDBError):
    """Falha que provavelmente passa se tentarmos de novo (429, 5xx, timeout)."""


class TMDBPermanentError(TMDBError):
    """Falha que não passa com retry (401 chave inválida, 404 recurso inexistente)."""


class _Throttle:
    """Espaça as requisições em pelo menos `1/max_rps` segundos.

    Simples de propósito: um relógio monotônico e um lock. Não é um token
    bucket — não precisamos de rajadas, precisamos de previsibilidade.
    """

    def __init__(self, max_rps: float) -> None:
        self._intervalo = 1.0 / max_rps if max_rps > 0 else 0.0
        self._lock = asyncio.Lock()
        self._liberado_em = 0.0

    async def aguardar(self) -> None:
        if not self._intervalo:
            return
        async with self._lock:
            agora = time.monotonic()
            atraso = self._liberado_em - agora
            if atraso > 0:
                await asyncio.sleep(atraso)
            self._liberado_em = max(agora, self._liberado_em) + self._intervalo


class TMDBClient:
    """Cliente do TMDB v3.

    Use como *context manager* assíncrono para garantir o fechamento das
    conexões:

        async with TMDBClient(chave) as tmdb:
            async for filme in tmdb.descobrir_filmes("BR", 2023):
                ...
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = BASE_URL,
        timeout: float = TIMEOUT_PADRAO,
        max_rps: float = MAX_RPS_PADRAO,
        max_tentativas: int = MAX_TENTATIVAS_PADRAO,
        backoff_inicial: float = 0.5,
        backoff_maximo: float = 30.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key vazia — use Settings.require_tmdb_key()")

        self._max_tentativas = max_tentativas
        self._backoff_inicial = backoff_inicial
        self._backoff_maximo = backoff_maximo
        self._throttle = _Throttle(max_rps)

        # Token v4 é um JWT e vai no header; chave v3 vai na query string.
        eh_token_v4 = api_key.startswith("eyJ")
        self._params_auth: dict[str, str] = {} if eh_token_v4 else {"api_key": api_key}
        headers = {"Accept": "application/json"}
        if eh_token_v4:
            headers["Authorization"] = f"Bearer {api_key}"

        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout, connect=5.0),
            headers=headers,
        )

    # --- ciclo de vida ---------------------------------------------------

    async def __aenter__(self) -> TMDBClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    # --- transporte ------------------------------------------------------

    async def _executar(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        """Uma tentativa: throttle, GET, e tradução do status em exceção."""
        await self._throttle.aguardar()

        consulta = {**self._params_auth, **{k: v for k, v in params.items() if v is not None}}
        resposta = await self._client.get(path, params=consulta)
        codigo = resposta.status_code

        if codigo == 429:
            # O TMDB diz em quanto tempo podemos voltar; obedecer é mais rápido
            # que o backoff genérico e evita entrar numa espiral de bloqueio.
            espera = float(resposta.headers.get("retry-after", 1))
            log.warning("429 em %s — respeitando retry-after de %.1fs", path, espera)
            await asyncio.sleep(espera)
            raise TMDBTransientError(f"429 Too Many Requests em {path}")

        if codigo >= 500:
            raise TMDBTransientError(f"{codigo} em {path}")

        if codigo >= 400:
            raise TMDBPermanentError(f"{codigo} em {path}: {resposta.text[:200]}")

        return resposta.json()

    async def _get(self, path: str, **params: Any) -> dict[str, Any]:
        """GET com retry. Só repete o que vale a pena repetir."""
        retrying = AsyncRetrying(
            retry=retry_if_exception_type(
                (TMDBTransientError, httpx.TimeoutException, httpx.TransportError)
            ),
            stop=stop_after_attempt(self._max_tentativas),
            wait=wait_exponential_jitter(initial=self._backoff_inicial, max=self._backoff_maximo),
            before_sleep=before_sleep_log(log, logging.WARNING),
            reraise=True,
        )
        async for tentativa in retrying:
            with tentativa:
                return await self._executar(path, params)
        raise AssertionError("inalcançável: AsyncRetrying sempre sai por return ou exceção")

    # --- endpoints -------------------------------------------------------

    async def descobrir_filmes(
        self,
        iso: str,
        ano: int,
        *,
        max_paginas: int = 5,
        ordenacao: str = "vote_count.desc",
    ) -> AsyncIterator[dict[str, Any]]:
        """Filmes de um país num ano, do mais votado para o menos.

        Ordenamos por `vote_count` e não por `popularity`: popularidade é um
        score interno de engajamento semanal do TMDB — foi exatamente a métrica
        que condenou o v0. Contagem de votos ao menos é um número absoluto e
        acumulado, apropriado para *selecionar* o corpus (não para pontuá-lo).

        `with_origin_country` filtra por país de origem da produção, e não por
        região de disponibilidade — é o recorte que a tese pede.

        Rende um dicionário por filme, já achatando a paginação.
        """
        pagina = 1
        while pagina <= max_paginas:
            dados = await self._get(
                "/discover/movie",
                with_origin_country=iso.upper(),
                primary_release_year=ano,
                sort_by=ordenacao,
                include_adult="false",
                page=pagina,
            )
            resultados: list[dict[str, Any]] = dados.get("results") or []
            for filme in resultados:
                yield filme

            total_paginas = int(dados.get("total_pages") or 1)
            if not resultados or pagina >= total_paginas:
                return
            pagina += 1

    async def datas_de_lancamento(self, filme_id: int) -> dict[str, Any]:
        """`/movie/{id}/release_dates` — insumo bruto da dimensão *Alcance*."""
        return await self._get(f"/movie/{filme_id}/release_dates")

    async def provedores(self, filme_id: int) -> dict[str, Any]:
        """`/movie/{id}/watch/providers` — onde a obra está disponível, por país."""
        return await self._get(f"/movie/{filme_id}/watch/providers")

    async def traducoes(self, filme_id: int) -> dict[str, Any]:
        """`/movie/{id}/translations` — insumo da dimensão *Penetração externa*."""
        return await self._get(f"/movie/{filme_id}/translations")
