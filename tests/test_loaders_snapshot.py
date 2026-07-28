"""Testes do gravador de snapshots.  ⚠️  `[VOCÊ]` — escritos, falhando, esperando.

    pytest tests/test_loaders_snapshot.py

Os dois testes que importam mais que todos os outros juntos:

* `test_preserva_o_grao` — o v0 morreu de `groupby(pais).agg(join)`.
* `test_duas_execucoes_no_mesmo_dia_nao_se_sobrescrevem` — o v0 morreu de
  `if_exists="replace"`.

O resto é caminho feliz. Estes dois são a fase inteira.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from ingestion.loaders.snapshot import read_snapshots, snapshot_dir, write_snapshot

pytestmark = pytest.mark.pendente

QUANDO = datetime(2026, 7, 27, 3, 15, tzinfo=UTC)
DEPOIS = datetime(2026, 8, 3, 3, 15, tzinfo=UTC)


def registros(n: int, *, inicio: int = 0) -> list[dict]:
    return [{"movie_id": inicio + i, "iso_3166_1": "BR", "vote_count": 100 + i} for i in range(n)]


class TestSnapshotDir:
    def test_particiona_por_data(self, tmp_path: Path):
        caminho = snapshot_dir("tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path)
        assert caminho == tmp_path / "tmdb_movies" / "ingested_date=2026-07-27"

    def test_nao_cria_o_diretorio(self, tmp_path: Path):
        """Calcular caminho e criar diretório são responsabilidades diferentes."""
        caminho = snapshot_dir("tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path)
        assert not caminho.exists()


class TestWriteSnapshot:
    def test_grava_na_particao_do_dia(self, tmp_path: Path):
        destino = write_snapshot(
            registros(3), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path
        )

        assert destino.exists()
        assert destino.parent.name == "ingested_date=2026-07-27"
        assert destino.name == "part-0000.parquet"

    def test_preserva_o_grao(self, tmp_path: Path):
        """Entram 250 registros, saem 250 linhas. Nada de agregar na ingestão."""
        destino = write_snapshot(
            registros(250), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path
        )
        assert len(pd.read_parquet(destino)) == 250

    def test_carimba_toda_linha_com_ingested_at(self, tmp_path: Path):
        """Sem o carimbo não dá para reconstruir o que sabíamos, e quando."""
        destino = write_snapshot(
            registros(5), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path
        )
        df = pd.read_parquet(destino)

        assert "ingested_at" in df.columns
        assert df["ingested_at"].notna().all()
        assert df["ingested_at"].nunique() == 1

    def test_preserva_as_colunas_originais(self, tmp_path: Path):
        destino = write_snapshot(
            registros(2), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path
        )
        colunas = set(pd.read_parquet(destino).columns)
        assert {"movie_id", "iso_3166_1", "vote_count"} <= colunas

    def test_duas_execucoes_no_mesmo_dia_nao_se_sobrescrevem(self, tmp_path: Path):
        """Um retry manual não pode apagar o que a execução anterior gravou."""
        primeiro = write_snapshot(
            registros(3), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path
        )
        segundo = write_snapshot(
            registros(2, inicio=100),
            dataset="tmdb_movies",
            ingested_at=QUANDO,
            base_dir=tmp_path,
        )

        assert primeiro != segundo
        assert primeiro.name == "part-0000.parquet"
        assert segundo.name == "part-0001.parquet"
        assert primeiro.exists(), "a primeira execução foi apagada — este é o bug do v0"
        assert len(pd.read_parquet(primeiro)) == 3

    def test_datas_diferentes_vao_para_particoes_diferentes(self, tmp_path: Path):
        a = write_snapshot(
            registros(1), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path
        )
        b = write_snapshot(
            registros(1), dataset="tmdb_movies", ingested_at=DEPOIS, base_dir=tmp_path
        )
        assert a.parent != b.parent

    def test_usa_agora_quando_nao_recebe_data(self, tmp_path: Path):
        destino = write_snapshot(registros(1), dataset="tmdb_movies", base_dir=tmp_path)
        hoje = datetime.now(tz=UTC).date().isoformat()
        assert destino.parent.name == f"ingested_date={hoje}"

    def test_registros_vazios_levantam_erro(self, tmp_path: Path):
        """Parquet sem colunas é um erro silencioso que só aparece três etapas depois."""
        with pytest.raises(ValueError):
            write_snapshot([], dataset="tmdb_movies", base_dir=tmp_path)

    def test_cria_os_diretorios_intermediarios(self, tmp_path: Path):
        destino = write_snapshot(
            registros(1),
            dataset="tmdb_movies",
            ingested_at=QUANDO,
            base_dir=tmp_path / "fundo" / "do" / "poco",
        )
        assert destino.exists()


class TestReadSnapshots:
    def test_concatena_todas_as_particoes(self, tmp_path: Path):
        write_snapshot(registros(3), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path)
        write_snapshot(
            registros(2, inicio=50),
            dataset="tmdb_movies",
            ingested_at=DEPOIS,
            base_dir=tmp_path,
        )

        df = read_snapshots("tmdb_movies", base_dir=tmp_path)
        assert len(df) == 5

    def test_expoe_a_data_da_particao_como_coluna(self, tmp_path: Path):
        """É esta coluna que transforma snapshots soltos em série temporal."""
        write_snapshot(registros(1), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path)
        write_snapshot(registros(1), dataset="tmdb_movies", ingested_at=DEPOIS, base_dir=tmp_path)

        df = read_snapshots("tmdb_movies", base_dir=tmp_path)
        assert set(df["ingested_date"]) == {"2026-07-27", "2026-08-03"}

    def test_le_multiplos_arquivos_da_mesma_particao(self, tmp_path: Path):
        write_snapshot(registros(3), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path)
        write_snapshot(
            registros(4, inicio=100),
            dataset="tmdb_movies",
            ingested_at=QUANDO,
            base_dir=tmp_path,
        )

        assert len(read_snapshots("tmdb_movies", base_dir=tmp_path)) == 7

    def test_dataset_inexistente_devolve_dataframe_vazio(self, tmp_path: Path):
        """'Ainda não há dado' é um estado normal do pipeline, não uma falha."""
        df = read_snapshots("nunca_coletado", base_dir=tmp_path)
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_nao_mistura_datasets(self, tmp_path: Path):
        write_snapshot(registros(3), dataset="tmdb_movies", ingested_at=QUANDO, base_dir=tmp_path)
        write_snapshot(
            registros(9), dataset="tmdb_watch_providers", ingested_at=QUANDO, base_dir=tmp_path
        )

        assert len(read_snapshots("tmdb_movies", base_dir=tmp_path)) == 3
        assert len(read_snapshots("tmdb_watch_providers", base_dir=tmp_path)) == 9
