"""Log estruturado do pipeline.

Por que isso existe: uma ingestão que roda por cron às 3h da manhã só é
depurável pelo log. `print()` não tem nível, não tem timestamp e não diz de
qual módulo veio — quando o TMDB devolver 429 em massa, é aqui que se descobre.

O módulo se chama `logging_config` e não `logging` de propósito: um módulo
chamado `logging` dentro do pacote confundiria qualquer leitor sobre qual
`logging` está sendo importado.

Uso:

    from ingestion.logging_config import configurar_logging, get_logger

    configurar_logging()
    log = get_logger(__name__)
    log.info("coletando %s/%s", iso, ano)
"""

from __future__ import annotations

import logging
import sys

from ingestion.config import get_settings

FORMATO = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"
FORMATO_DATA = "%Y-%m-%dT%H:%M:%S%z"

_configurado = False


def configurar_logging(nivel: str | None = None, *, forcar: bool = False) -> None:
    """Configura o logging da aplicação uma única vez.

    O nível vem de `LOG_LEVEL` no ambiente, salvo se passado explicitamente.
    Chamadas repetidas são ignoradas (a menos que `forcar=True`), para que
    importar um módulo nunca reconfigure o log de quem o importou.
    """
    global _configurado
    if _configurado and not forcar:
        return

    nivel_efetivo = (nivel or get_settings().log_level).upper()

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(FORMATO, datefmt=FORMATO_DATA))

    raiz = logging.getLogger("ingestion")
    raiz.handlers.clear()
    raiz.addHandler(handler)
    raiz.setLevel(nivel_efetivo)
    raiz.propagate = False

    # httpx loga cada requisição em INFO; com centenas de filmes isso vira ruído.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    _configurado = True


def get_logger(nome: str) -> logging.Logger:
    """Logger do namespace `ingestion`, com o prefixo garantido."""
    if not nome.startswith("ingestion"):
        nome = f"ingestion.{nome}"
    return logging.getLogger(nome)
