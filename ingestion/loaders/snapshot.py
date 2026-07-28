"""Snapshots datados em parquet.  ⚠️  STUB — `[VOCÊ]` na Fase 1 do plano.

Os testes de `tests/test_loaders_snapshot.py` já estão escritos e **falhando**.
Implemente até que passem:

    pytest tests/test_loaders_snapshot.py

---------------------------------------------------------------------------
Layout no disco
---------------------------------------------------------------------------

    data/raw/<dataset>/ingested_date=YYYY-MM-DD/part-0000.parquet
                                               part-0001.parquet
                       ingested_date=YYYY-MM-DD/part-0000.parquet
                       ...

O particionamento `chave=valor` (estilo Hive) não é enfeite: o DuckDB e o dbt
leem `data/raw/<dataset>/**/*.parquet` e ganham `ingested_date` como coluna de
graça, sem configuração. É o que torna possível perguntar "como estava o dado
na semana passada?" — a pergunta que o v0 tinha destruído.

Dentro de uma mesma data, arquivos `part-NNNN` se acumulam em vez de se
sobrescrever. Rodar a ingestão duas vezes no mesmo dia (um retry manual, um
`workflow_dispatch`) **nunca** pode apagar o que já estava lá.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

# Nome da coluna de partição e da coluna de carimbo. Ficam aqui, e não soltas
# em strings pelo código, porque o dbt vai depender exatamente destes nomes.
COLUNA_PARTICAO = "ingested_date"
COLUNA_CARIMBO = "ingested_at"


def snapshot_dir(
    dataset: str,
    *,
    ingested_at: datetime,
    base_dir: Path | None = None,
) -> Path:
    """Diretório da partição de um dataset numa data.

    `[VOCÊ]` Deve devolver:

        <base_dir>/<dataset>/ingested_date=YYYY-MM-DD

    `base_dir` padrão: `get_settings().raw_dir` (importe de `ingestion.config`).
    A função apenas *calcula* o caminho — não cria diretório nem toca no disco.
    """
    raise NotImplementedError


def write_snapshot(
    registros: Iterable[Mapping[str, Any]],
    *,
    dataset: str,
    ingested_at: datetime | None = None,
    base_dir: Path | None = None,
) -> Path:
    """Grava registros como um novo arquivo parquet na partição do dia.

    `[VOCÊ]` Comportamento exigido pelos testes:

    * `ingested_at` padrão é `datetime.now(tz=UTC)`.
    * Toda linha ganha a coluna `ingested_at` (mesmo valor, ciente de fuso).
      É o que permite reconstruir "o que sabíamos, e quando".
    * O número de linhas gravadas é **igual** ao número de registros recebidos.
      Nenhuma agregação, nenhuma deduplicação, nenhuma perda de grão.
    * O arquivo é `part-NNNN.parquet`, com `NNNN` sendo o menor índice ainda
      livre na partição, com 4 dígitos. Nunca sobrescreve um arquivo existente.
    * Diretórios intermediários são criados se não existirem.
    * `registros` vazio levanta `ValueError` — gravar um parquet sem colunas
      é um erro silencioso que só aparece três etapas depois.
    * Devolve o `Path` do arquivo gravado.

    Sugestão: `pandas.DataFrame(...)` e `.to_parquet(caminho, index=False)`
    (o `pyarrow` já está nas dependências).
    """
    raise NotImplementedError


def read_snapshots(
    dataset: str,
    *,
    base_dir: Path | None = None,
) -> pd.DataFrame:
    """Lê todas as partições de um dataset num único DataFrame.

    `[VOCÊ]` Comportamento exigido pelos testes:

    * Concatena todos os `part-*.parquet` de todas as partições.
    * Acrescenta a coluna `ingested_date` (`str`, no formato `YYYY-MM-DD`),
      lida do nome do diretório da partição.
    * Dataset inexistente devolve um `DataFrame` vazio — e não uma exceção.
      Ler "nada ainda" é um estado normal do pipeline, não uma falha.

    Serve para verificação e exploração local; o consumo de verdade é via
    DuckDB e dbt, direto nos parquets.
    """
    raise NotImplementedError


__all__ = [
    "COLUNA_CARIMBO",
    "COLUNA_PARTICAO",
    "read_snapshots",
    "snapshot_dir",
    "write_snapshot",
]
