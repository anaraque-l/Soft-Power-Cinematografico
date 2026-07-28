"""Gravação da camada bruta (bronze).

Duas regras, e elas são a correção do erro central do v0:

1. **Nunca sobrescrever.** Cada execução é um *snapshot* datado. O v0 usava
   `if_exists="replace"`: a cada rodada o histórico anterior era apagado, o que
   torna qualquer série temporal impossível — e o ISPC é, por definição, uma
   série temporal.
2. **Nunca agregar.** O grão que entra é o grão que sai. O v0 fazia
   `groupby(pais).agg(join)` na primeira transformação e restavam cinco linhas
   de texto concatenado. Depois disso nenhuma pergunta interessante era mais
   respondível.
"""

from ingestion.loaders.snapshot import read_snapshots, snapshot_dir, write_snapshot

__all__ = ["read_snapshots", "snapshot_dir", "write_snapshot"]
