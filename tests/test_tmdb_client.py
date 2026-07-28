"""Testes do cliente TMDB — sem tocar a rede.

O `respx` intercepta o transporte do httpx, então dá para testar exatamente o
que é difícil de observar em produção: o que acontece no 429, no 500, no
timeout. Um cliente de API sem estes testes é um cliente cujo retry ninguém
nunca viu funcionar.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from ingestion.clients.tmdb import (
    TMDBClient,
    TMDBPermanentError,
    TMDBTransientError,
    _Throttle,
)

BASE = "https://tmdb.test/3"


def cliente(**kwargs) -> TMDBClient:
    """Cliente de teste: sem throttle e sem espera entre tentativas."""
    kwargs.setdefault("api_key", "chave-v3")
    kwargs.setdefault("base_url", BASE)
    kwargs.setdefault("max_rps", 0)
    kwargs.setdefault("backoff_inicial", 0.0)
    kwargs.setdefault("backoff_maximo", 0.0)
    return TMDBClient(**kwargs)


def pagina(ids: list[int], *, page: int = 1, total_pages: int = 1) -> dict:
    return {
        "page": page,
        "total_pages": total_pages,
        "total_results": len(ids) * total_pages,
        "results": [{"id": i, "title": f"Filme {i}"} for i in ids],
    }


class TestAutenticacao:
    def test_chave_vazia_falha_na_construcao(self):
        """Falhar aqui é melhor que descobrir a chave faltando no 401 do loop."""
        with pytest.raises(ValueError, match="api_key"):
            TMDBClient("")

    async def test_chave_v3_vai_na_query_string(self):
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/movie/1/release_dates").mock(
                return_value=httpx.Response(200, json={"id": 1, "results": []})
            )
            async with cliente(api_key="chave-v3") as tmdb:
                await tmdb.datas_de_lancamento(1)

        assert rota.calls.last.request.url.params["api_key"] == "chave-v3"
        assert "authorization" not in rota.calls.last.request.headers

    async def test_token_v4_vai_no_header_bearer(self):
        """O TMDB entrega chave v3 e token v4 na mesma tela; os dois funcionam."""
        token = "eyJhbGciOiJIUzI1NiJ9.fake"
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/movie/1/release_dates").mock(
                return_value=httpx.Response(200, json={"id": 1, "results": []})
            )
            async with cliente(api_key=token) as tmdb:
                await tmdb.datas_de_lancamento(1)

        requisicao = rota.calls.last.request
        assert requisicao.headers["authorization"] == f"Bearer {token}"
        assert "api_key" not in requisicao.url.params


class TestPaginacao:
    async def test_percorre_todas_as_paginas(self):
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/discover/movie")
            rota.side_effect = [
                httpx.Response(200, json=pagina([1, 2], page=1, total_pages=3)),
                httpx.Response(200, json=pagina([3, 4], page=2, total_pages=3)),
                httpx.Response(200, json=pagina([5, 6], page=3, total_pages=3)),
            ]
            async with cliente() as tmdb:
                filmes = [f async for f in tmdb.descobrir_filmes("BR", 2023)]

        assert [f["id"] for f in filmes] == [1, 2, 3, 4, 5, 6]
        assert rota.call_count == 3

    async def test_respeita_max_paginas(self):
        """O corte vertical do plano roda com poucas páginas por país."""
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/discover/movie")
            rota.side_effect = [
                httpx.Response(200, json=pagina([1], page=1, total_pages=50)),
                httpx.Response(200, json=pagina([2], page=2, total_pages=50)),
            ]
            async with cliente() as tmdb:
                filmes = [f async for f in tmdb.descobrir_filmes("BR", 2023, max_paginas=2)]

        assert len(filmes) == 2
        assert rota.call_count == 2

    async def test_para_quando_results_vem_vazio(self):
        """País sem filmes num ano é normal — não pode virar loop infinito."""
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/discover/movie").mock(
                return_value=httpx.Response(200, json=pagina([], page=1, total_pages=99))
            )
            async with cliente() as tmdb:
                filmes = [f async for f in tmdb.descobrir_filmes("KE", 1995)]

        assert filmes == []
        assert rota.call_count == 1

    async def test_envia_os_parametros_do_recorte(self):
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/discover/movie").mock(
                return_value=httpx.Response(200, json=pagina([1]))
            )
            async with cliente() as tmdb:
                _ = [f async for f in tmdb.descobrir_filmes("br", 2023)]

        params = rota.calls.last.request.url.params
        assert params["with_origin_country"] == "BR", "ISO deve ir em maiúsculo"
        assert params["primary_release_year"] == "2023"
        assert params["sort_by"] == "vote_count.desc", "popularity foi o erro do v0"
        assert params["include_adult"] == "false"


class TestRetry:
    async def test_retenta_apos_429_respeitando_retry_after(self):
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/movie/7/watch/providers")
            rota.side_effect = [
                httpx.Response(429, headers={"retry-after": "0"}),
                httpx.Response(200, json={"id": 7, "results": {}}),
            ]
            async with cliente() as tmdb:
                dados = await tmdb.provedores(7)

        assert dados["id"] == 7
        assert rota.call_count == 2

    async def test_retenta_em_500_e_desiste_apos_max_tentativas(self):
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/movie/7/release_dates").mock(return_value=httpx.Response(503))
            async with cliente(max_tentativas=3) as tmdb:
                with pytest.raises(TMDBTransientError):
                    await tmdb.datas_de_lancamento(7)

        assert rota.call_count == 3

    async def test_retenta_timeout(self):
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/movie/7/translations")
            rota.side_effect = [
                httpx.ConnectTimeout("estourou"),
                httpx.Response(200, json={"id": 7, "translations": []}),
            ]
            async with cliente() as tmdb:
                dados = await tmdb.traducoes(7)

        assert dados["id"] == 7
        assert rota.call_count == 2

    @pytest.mark.parametrize("codigo", [401, 404, 422])
    async def test_nao_retenta_erro_permanente(self, codigo):
        """Chave inválida não melhora na quarta tentativa — falha na primeira."""
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get("/movie/7/release_dates").mock(
                return_value=httpx.Response(codigo, json={"status_message": "não"})
            )
            async with cliente(max_tentativas=5) as tmdb:
                with pytest.raises(TMDBPermanentError, match=str(codigo)):
                    await tmdb.datas_de_lancamento(7)

        assert rota.call_count == 1


class TestEndpoints:
    @pytest.mark.parametrize(
        ("metodo", "caminho"),
        [
            ("datas_de_lancamento", "/movie/42/release_dates"),
            ("provedores", "/movie/42/watch/providers"),
            ("traducoes", "/movie/42/translations"),
        ],
    )
    async def test_endpoint_certo(self, metodo, caminho):
        with respx.mock(base_url=BASE) as mock:
            rota = mock.get(caminho).mock(return_value=httpx.Response(200, json={"id": 42}))
            async with cliente() as tmdb:
                dados = await getattr(tmdb, metodo)(42)

        assert dados == {"id": 42}
        assert rota.call_count == 1


class TestThrottle:
    async def test_espaca_as_requisicoes(self):
        """Sem espaçamento, uma coleta de 35 países leva 429 do TMDB."""
        throttle = _Throttle(max_rps=100.0)  # 10 ms entre chamadas

        inicio = time.monotonic()
        for _ in range(3):
            await throttle.aguardar()
        decorrido = time.monotonic() - inicio

        assert decorrido >= 0.02, "a segunda e a terceira chamadas deveriam ter esperado"

    async def test_max_rps_zero_desliga_o_throttle(self):
        throttle = _Throttle(max_rps=0)
        inicio = time.monotonic()
        for _ in range(50):
            await throttle.aguardar()
        assert time.monotonic() - inicio < 0.05
