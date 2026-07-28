"""Modelos do TMDB.  ⚠️  STUB — `[VOCÊ]` na Fase 1 do plano.

Os testes de `tests/test_models_tmdb.py` já estão escritos e **falhando**.
Implemente até que passem:

    pytest tests/test_models_tmdb.py

Os nomes dos campos são os do TMDB, em inglês, de propósito: esta camada
espelha o contrato da fonte. A tradução para o vocabulário do projeto acontece
depois, no dbt (camada silver). Misturar as duas coisas aqui é o começo de um
pipeline em que ninguém mais sabe de onde veio cada nome.

---------------------------------------------------------------------------
Referência dos payloads (é isto que o `TMDBClient` devolve)
---------------------------------------------------------------------------

`GET /discover/movie` → cada item de `results`:

    {
      "id": 508965,
      "title": "Klaus",
      "original_title": "Klaus",
      "original_language": "en",
      "release_date": "2019-11-08",     ← pode vir "" (string vazia!)
      "vote_count": 3612,
      "vote_average": 8.2,
      "popularity": 45.7,
      "genre_ids": [16, 35, 10751],
      "overview": "...",
      "poster_path": "/q2fdvS3E5JuHVoP3l3zHVFbCa8V.jpg",  ← pode vir null
      "adult": false,
      "backdrop_path": "...", "video": false          ← campos que ignoramos
    }

`GET /movie/{id}/release_dates`:

    {
      "id": 508965,
      "results": [
        {"iso_3166_1": "BR",
         "release_dates": [
            {"certification": "L",
             "iso_639_1": "",
             "note": "",
             "release_date": "2019-11-15T00:00:00.000Z",
             "type": 4}
         ]},
        {"iso_3166_1": "US", "release_dates": [...]}
      ]
    }

    `type`: 1 Premiere · 2 Limitado · 3 Cinema · 4 Digital · 5 Físico · 6 TV

`GET /movie/{id}/watch/providers`:

    {
      "id": 508965,
      "results": {
        "BR": {"link": "https://...",
               "flatrate": [{"provider_id": 8, "provider_name": "Netflix",
                             "logo_path": "/x.jpg", "display_priority": 1}],
               "rent": [...], "buy": [...]},
        "US": {...}
      }
    }

    Chaves de tipo possíveis dentro de cada país: `flatrate`, `free`, `ads`,
    `rent`, `buy`. `link` não é um tipo — é a URL da página do TMDB.
"""

from __future__ import annotations

# `date` e `datetime` estão aqui para você usar nas anotações dos campos.
from datetime import date, datetime  # noqa: F401
from typing import Any

from pydantic import BaseModel

# Tipos de disponibilidade que contam como "streaming por assinatura".
# `rent` e `buy` são transação avulsa: presença em catálogo é outra coisa.
TIPOS_STREAMING: frozenset[str] = frozenset({"flatrate", "free", "ads"})


class Movie(BaseModel):
    """Um filme, como o `/discover/movie` o devolve.

    `[VOCÊ]` Campos esperados (nesta ordem, com estes tipos):

        id: int
        title: str
        original_title: str
        original_language: str
        release_date: date | None (default: None)
        vote_count: int
        vote_average: float
        popularity: float
        genre_ids: list[int]      (default: lista vazia)
        overview: str             (default: "")
        poster_path: str | None   (default: None)
        adult: bool               (default: False)

    Dois detalhes que os testes cobrem e que são a razão de este modelo existir:

    1. `release_date` chega como `""` quando o TMDB não sabe a data. Um
       `date | None` puro rejeita a string vazia com `ValidationError`. Use um
       validador `mode="before"` que converta `""` (e só ela) para `None`.
    2. Campos que o TMDB manda e nós não usamos (`backdrop_path`, `video`)
       devem ser simplesmente ignorados, não causar erro.

    Sobre `popularity`: guardamos o campo porque a camada bruta grava o dado
    como veio — mas ele **não** entra no ISPC. Foi a métrica que condenou o v0
    (ver `docs/adr/0002-reconstrucao-do-v0.md`).
    """

    def __init__(self, **dados: Any) -> None:  # pragma: no cover - stub
        raise NotImplementedError(
            "Movie ainda não foi implementado — ver tests/test_models_tmdb.py"
        )

    @property
    def ano(self) -> int | None:
        """Ano de lançamento, ou `None` se a data for desconhecida.

        `[VOCÊ]` O grão do ISPC é país × ano; é este campo que amarra os dois.
        """
        raise NotImplementedError


class ReleaseDate(BaseModel):
    """Um evento de lançamento: um filme, num país, numa data, de um tipo.

    `[VOCÊ]` Campos esperados:

        iso_3166_1: str      ← 2 letras, normalizado para MAIÚSCULO
        release_date: datetime
        type: int
        certification: str   (default: "")

    Note que o TMDB aninha os eventos por país; achatar essa estrutura é
    trabalho de `MovieReleases.from_payload`, não deste modelo.
    """

    def __init__(self, **dados: Any) -> None:  # pragma: no cover - stub
        raise NotImplementedError(
            "ReleaseDate ainda não foi implementado — ver tests/test_models_tmdb.py"
        )


class MovieReleases(BaseModel):
    """Todos os lançamentos de um filme, já achatados.

    `[VOCÊ]` Campos esperados:

        movie_id: int
        lancamentos: list[ReleaseDate]
    """

    def __init__(self, **dados: Any) -> None:  # pragma: no cover - stub
        raise NotImplementedError(
            "MovieReleases ainda não foi implementado — ver tests/test_models_tmdb.py"
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> MovieReleases:
        """Constrói a partir do JSON cru de `/movie/{id}/release_dates`.

        `[VOCÊ]` Desaninhe `results[].release_dates[]` em uma lista única de
        `ReleaseDate`, copiando o `iso_3166_1` do país para cada evento.
        Um país sem nenhum evento simplesmente não contribui com linhas.
        """
        raise NotImplementedError

    @property
    def mercados(self) -> set[str]:
        """Países em que o filme teve algum lançamento registrado.

        `[VOCÊ]` Insumo direto da dimensão *Alcance* do ISPC.
        """
        raise NotImplementedError

    @property
    def n_mercados(self) -> int:
        """Quantidade de países distintos em `mercados`."""
        raise NotImplementedError

    def to_rows(self) -> list[dict[str, Any]]:
        """Uma linha por evento de lançamento, pronta para o parquet.

        `[VOCÊ]` Chaves de cada linha, exatamente:
        `movie_id`, `iso_3166_1`, `release_date`, `type`, `certification`.

        Um evento por linha — o grão não se agrega aqui. Agregar cedo demais
        foi o erro estrutural do v0.
        """
        raise NotImplementedError


class WatchProvider(BaseModel):
    """Disponibilidade de um filme num país, por um provedor, num modelo.

    `[VOCÊ]` Campos esperados:

        iso_3166_1: str      ← 2 letras, MAIÚSCULO
        provider_id: int
        provider_name: str
        tipo: str            ← "flatrate" | "free" | "ads" | "rent" | "buy"
    """

    def __init__(self, **dados: Any) -> None:  # pragma: no cover - stub
        raise NotImplementedError(
            "WatchProvider ainda não foi implementado — ver tests/test_models_tmdb.py"
        )


class MovieWatchProviders(BaseModel):
    """Todas as disponibilidades de um filme, já achatadas.

    `[VOCÊ]` Campos esperados:

        movie_id: int
        disponibilidades: list[WatchProvider]
    """

    def __init__(self, **dados: Any) -> None:  # pragma: no cover - stub
        raise NotImplementedError(
            "MovieWatchProviders ainda não foi implementado — ver tests/test_models_tmdb.py"
        )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> MovieWatchProviders:
        """Constrói a partir do JSON cru de `/movie/{id}/watch/providers`.

        `[VOCÊ]` `results` é um dicionário indexado por país, não uma lista.
        Dentro de cada país, ignore a chave `link` (é URL, não provedor) e
        transforme cada item das demais chaves num `WatchProvider` com o
        `tipo` correspondente.
        """
        raise NotImplementedError

    @property
    def mercados_streaming(self) -> set[str]:
        """Países com disponibilidade por assinatura, gratuita ou com anúncios.

        `[VOCÊ]` Use `TIPOS_STREAMING`. Aluguel e compra ficam de fora: estar
        no catálogo de uma assinatura e estar à venda são fatos culturais
        diferentes, e a dimensão *Alcance* mede o primeiro.
        """
        raise NotImplementedError

    def to_rows(self) -> list[dict[str, Any]]:
        """Uma linha por (filme, país, provedor, tipo).

        `[VOCÊ]` Chaves de cada linha, exatamente:
        `movie_id`, `iso_3166_1`, `provider_id`, `provider_name`, `tipo`.
        """
        raise NotImplementedError


__all__ = [
    "TIPOS_STREAMING",
    "Movie",
    "MovieReleases",
    "MovieWatchProviders",
    "ReleaseDate",
    "WatchProvider",
]
