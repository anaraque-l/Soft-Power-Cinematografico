"""Clientes das fontes externas.

Um módulo por fonte. Cada cliente é responsável por *falar* com a API —
autenticação, paginação, rate limit, retry — e por nada além disso: não
valida contrato (isso é `ingestion.models`) e não grava (isso é
`ingestion.loaders`).
"""

from ingestion.clients.tmdb import (
    TMDBClient,
    TMDBError,
    TMDBPermanentError,
    TMDBTransientError,
)

__all__ = ["TMDBClient", "TMDBError", "TMDBPermanentError", "TMDBTransientError"]
