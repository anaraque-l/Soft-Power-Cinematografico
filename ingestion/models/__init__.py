"""Modelos pydantic: o contrato das fontes externas, validado na fronteira.

A regra desta camada: **nada entra no pipeline sem passar por aqui**. Quando o
TMDB renomear um campo ou passar a devolver `null` onde antes vinha número, o
pipeline falha alto, nesta linha, com o nome do campo — em vez de gravar
silenciosamente uma coluna de `None` que só será notada três meses depois,
quando a série temporal já estiver corrompida.
"""

from ingestion.models.tmdb import (
    Movie,
    MovieReleases,
    MovieWatchProviders,
    ReleaseDate,
    WatchProvider,
)

__all__ = [
    "Movie",
    "MovieReleases",
    "MovieWatchProviders",
    "ReleaseDate",
    "WatchProvider",
]
