"""Camada de ingestão: busca dados nas fontes externas e grava a camada bruta.

Regra desta camada: gravar o dado como ele veio, com carimbo de data,
sem agregar e sem interpretar. Toda transformação acontece depois, no dbt.
"""

__version__ = "0.1.0"
