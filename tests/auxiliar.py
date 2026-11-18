"""Utilidades compartilhadas pelos testes: caminho do projeto e dados de exemplo."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any, Dict

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from analise_demonstracoes_financeiras import DADOS_EXEMPLO, DadosFinanceiros  # noqa: E402

PASTA_DADOS = Path(__file__).resolve().parent / "dados"


def dados_exemplo() -> DadosFinanceiros:
    """Dados fictícios embutidos, em uma cópia independente."""
    return DadosFinanceiros.from_dict(copy.deepcopy(DADOS_EXEMPLO))


def dict_de(**alteracoes: Any) -> Dict[str, Any]:
    """Cópia de DADOS_EXEMPLO com alterações por seção.

    Cada argumento é o nome de uma seção. Um dict é mesclado na seção; qualquer outro valor
    (inclusive None) a substitui. Ex.: dict_de(mercado={"preco_acao": None}, exercicio_anterior=None).
    """
    base = copy.deepcopy(DADOS_EXEMPLO)
    for secao, valor in alteracoes.items():
        if isinstance(valor, dict) and isinstance(base.get(secao), dict):
            base[secao].update(valor)
        else:
            base[secao] = valor
    return base


def dados_de(**alteracoes: Any) -> DadosFinanceiros:
    """Como dict_de, mas devolve DadosFinanceiros."""
    return DadosFinanceiros.from_dict(dict_de(**alteracoes))
