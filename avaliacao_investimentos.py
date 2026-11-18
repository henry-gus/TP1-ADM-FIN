#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
avaliacao_investimentos.py - Orçamento de capital: avaliação de um projeto de investimento
===========================================================================================
CAD 167 – Administração Financeira (UFMG)

Camada de CÁLCULO (pura: não imprime nem lê do usuário). Calcula, para um projeto com investimento
inicial e fluxos de caixa anuais:
  - VPL (valor presente líquido) e índice de lucratividade (IL);
  - TIR (taxa interna de retorno), por varredura da taxa seguida de bisseção;
  - payback simples e descontado (com interpolação linear dentro do ano);
  - recomendação pelo critério do VPL.

A taxa de desconto padrão é o WACC da empresa. Convenções: valores em R$ mil, taxas em fração.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

MAX_FLUXOS = 20
TOLERANCIA_TIR = 1e-10
TOLERANCIA_VPL = 1e-9
TAXA_MINIMA_TIR = -0.99
TAXA_MAXIMA_TIR = 10.0   # 1000% a.a.
PASSO_VARREDURA = 0.005


def _finito(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


@dataclass
class Projeto:
    """Projeto de investimento: investimento inicial (> 0, saída no ano 0), fluxos dos anos 1..n e taxa."""
    investimento_inicial: float
    fluxos: List[float]
    taxa: Optional[float] = None

    def __post_init__(self) -> None:
        if not _finito(self.investimento_inicial) or self.investimento_inicial <= 0:
            raise ValueError("Investimento inicial deve ser maior que zero.")
        if not isinstance(self.fluxos, (list, tuple)) or not 1 <= len(self.fluxos) <= MAX_FLUXOS:
            raise ValueError(f"Informe de 1 a {MAX_FLUXOS} fluxos anuais.")
        for ano, fluxo in enumerate(self.fluxos, 1):
            if not _finito(fluxo):
                raise ValueError(f"Fluxo do ano {ano} inválido: {fluxo!r}.")
        self.fluxos = [float(f) for f in self.fluxos]
        if self.taxa is not None and (not _finito(self.taxa) or self.taxa <= -1):
            raise ValueError("Taxa de desconto deve ser maior que -100%.")

    @classmethod
    def de(cls, obj: Any) -> "Projeto":
        """Aceita uma instância ou um dict (investimento_inicial ou investimento, fluxos, taxa)."""
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, dict):
            investimento = obj.get("investimento_inicial", obj.get("investimento"))
            return cls(investimento, list(obj.get("fluxos") or []), obj.get("taxa"))
        raise ValueError("Projeto inválido: informe investimento_inicial e fluxos.")

    @property
    def fluxos_completos(self) -> List[float]:
        """Fluxos com o ano 0 (investimento como saída)."""
        return [-float(self.investimento_inicial)] + list(self.fluxos)


def vpl(taxa: float, fluxos: Sequence[float]) -> float:
    """Valor presente líquido; fluxos[0] é o ano 0."""
    return sum(f / (1 + taxa) ** t for t, f in enumerate(fluxos))


def trocas_de_sinal(fluxos: Sequence[float]) -> int:
    """Número de trocas de sinal na sequência de fluxos (zeros ignorados)."""
    sinais = [f > 0 for f in fluxos if f != 0]
    return sum(1 for a, b in zip(sinais, sinais[1:]) if a != b)


def tir(fluxos: Sequence[float]) -> Tuple[Optional[float], Optional[str]]:
    """(TIR, motivo se não houver). Varre a taxa de −99% a 1000% e refina a primeira raiz por bisseção."""
    if trocas_de_sinal(fluxos) == 0:
        return None, "fluxos sem troca de sinal"
    passos = int(round((TAXA_MAXIMA_TIR - TAXA_MINIMA_TIR) / PASSO_VARREDURA))
    anterior_taxa = TAXA_MINIMA_TIR
    anterior_vpl = vpl(anterior_taxa, fluxos)
    if anterior_vpl == 0:
        return anterior_taxa, None
    for i in range(1, passos + 1):
        taxa = TAXA_MINIMA_TIR + i * PASSO_VARREDURA
        valor = vpl(taxa, fluxos)
        if valor == 0:
            return taxa, None
        if (valor > 0) != (anterior_vpl > 0):
            baixo, alto, vpl_baixo = anterior_taxa, taxa, anterior_vpl
            while alto - baixo > TOLERANCIA_TIR:
                meio = (baixo + alto) / 2
                vpl_meio = vpl(meio, fluxos)
                if (vpl_meio > 0) == (vpl_baixo > 0):
                    baixo, vpl_baixo = meio, vpl_meio
                else:
                    alto = meio
            return (baixo + alto) / 2, None
        anterior_taxa, anterior_vpl = taxa, valor
    return None, "não convergiu"


def _acumulados(fluxos: Sequence[float], taxa: Optional[float]) -> List[float]:
    total, saida = 0.0, []
    for t, f in enumerate(fluxos):
        total += f if taxa is None else f / (1 + taxa) ** t
        saida.append(total)
    return saida


def payback(fluxos: Sequence[float], taxa: Optional[float] = None) -> Optional[float]:
    """Anos até recuperar o investimento (simples sem taxa; descontado com taxa). None se não recuperar."""
    acumulado = _acumulados(fluxos, taxa)
    if acumulado[0] >= 0:
        return 0.0
    for t in range(1, len(fluxos)):
        if acumulado[t] >= 0:
            fluxo_ano = acumulado[t] - acumulado[t - 1]
            return (t - 1) + (-acumulado[t - 1]) / fluxo_ano
    return None


def indice_lucratividade(taxa: float, fluxos: Sequence[float]) -> Optional[float]:
    """VP dos fluxos dos anos 1..n dividido pelo investimento inicial."""
    if not fluxos or fluxos[0] >= 0:
        return None
    return vpl(taxa, [0.0] + list(fluxos[1:])) / -fluxos[0]


def avaliar_projeto(projeto: Projeto, wacc: Optional[float], motivo_wacc: Optional[str] = None) -> Dict[str, Any]:
    """Avaliação completa. Sem taxa informada usa o WACC; sem os dois, levanta ValueError."""
    projeto = Projeto.de(projeto)
    if projeto.taxa is not None:
        taxa, origem = projeto.taxa, "informada"
    elif wacc is not None and _finito(wacc) and wacc > -1:
        taxa, origem = wacc, "WACC"
    else:
        detalhe = f" ({motivo_wacc})" if motivo_wacc else ""
        raise ValueError(f"Informe a taxa de desconto: o WACC não pôde ser calculado{detalhe}.")

    fluxos = projeto.fluxos_completos
    valor = vpl(taxa, fluxos)
    taxa_interna, motivo_tir = tir(fluxos)
    pb, pbd = payback(fluxos), payback(fluxos, taxa)
    if abs(valor) <= TOLERANCIA_VPL:
        recomendacao = "indiferente"
    else:
        recomendacao = "aceitar" if valor > 0 else "rejeitar"

    avisos = []
    trocas = trocas_de_sinal(fluxos)
    if trocas > 1:
        avisos.append(f"Os fluxos trocam de sinal {trocas} vezes: pode haver múltiplas TIRs; "
                      "prevalece o critério do VPL.")
    if pb is None:
        avisos.append("Payback simples: investimento não recuperado no horizonte do projeto.")
    if pbd is None:
        avisos.append("Payback descontado: investimento não recuperado no horizonte do projeto.")

    acumulado, acumulado_desc = _acumulados(fluxos, None), _acumulados(fluxos, taxa)
    tabela = [{"ano": t, "fluxo": f, "fluxo_descontado": f / (1 + taxa) ** t,
               "acumulado": acumulado[t], "acumulado_descontado": acumulado_desc[t]}
              for t, f in enumerate(fluxos)]
    return {
        "taxa": taxa, "origem_taxa": origem, "fluxos": fluxos, "vpl": valor,
        "tir": taxa_interna, "motivo_tir": motivo_tir, "payback_simples": pb, "payback_descontado": pbd,
        "indice_lucratividade": indice_lucratividade(taxa, fluxos), "recomendacao": recomendacao,
        "avisos": avisos, "tabela": tabela,
    }
