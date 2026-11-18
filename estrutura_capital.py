#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
estrutura_capital.py - Estrutura de Capital: custo de capital, alavancagem e estrutura ótima
=============================================================================================
CAD 167 – Administração Financeira (UFMG)

Camada de CÁLCULO (pura: não imprime nem lê do usuário). Recebe `DadosFinanceiros` e calcula:
  - custo de capital: Kd contábil, alíquota efetiva, Ke pelo CAPM, pesos e WACC;
  - endividamento e graus de alavancagem (GAO, GAF e GAC) com o exercício anterior;
  - análise EBIT-LPA (dívida × ações) com o ponto de indiferença;
  - simulação da estrutura ótima (beta de Hamada + ratings sintéticos) e o benefício fiscal
    de Modigliani-Miller com impostos.

Convenções: valores em R$ mil, ações em milhares, taxas em fração (0,11 = 11%). Dado ausente
produz Indicador com valor None e o motivo; entrada inválida produz ValueError nomeando o campo.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from analise_demonstracoes_financeiras import (
    DadosFinanceiros,
    Indicador,
    _num_br,
    _valido,
    dividir,
)

ALIQUOTA_NOMINAL = 0.34          # IRPJ (25%) + CSLL (9%)
FAIXA_KD_USUAL = (0.02, 0.40)    # fora desta faixa o Kd contábil recebe aviso de atenção

# Ratings sintéticos por índice de cobertura de juros (EBIT / despesa de juros).
# Fonte: A. Damodaran, "Ratings, Interest Coverage Ratios and Default Spread", empresas não
# financeiras de grande porte, atualização de janeiro de 2026.
# Cada linha: (cobertura mínima, rating, spread sobre a taxa livre de risco), em ordem decrescente.
TABELA_SPREADS: Tuple[Tuple[float, str, float], ...] = (
    (8.50, "AAA", 0.0040),
    (6.50, "AA", 0.0055),
    (5.50, "A+", 0.0070),
    (4.25, "A", 0.0078),
    (3.00, "A−", 0.0089),
    (2.50, "BBB", 0.0111),
    (2.25, "BB+", 0.0138),
    (2.00, "BB", 0.0184),
    (1.75, "B+", 0.0275),
    (1.50, "B", 0.0321),
    (1.25, "B−", 0.0509),
    (0.80, "CCC", 0.0885),
    (0.65, "CC", 0.1261),
    (0.20, "C", 0.1600),
    (-math.inf, "D", 0.1900),
)

MAX_ITERACOES_KD = 30
MOTIVO_KE = "informe Rf, beta e prêmio de mercado"


def _pct(v: float) -> str:
    return f"{_num_br(v * 100)}%"


def _numero_curto(v: float) -> str:
    return f"{v:g}".replace(".", ",")


def _finito(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# ============================================================================
# Parâmetros de mercado e alíquota
# ============================================================================
@dataclass
class ParametrosMercado:
    """Parâmetros do custo de capital informados pelo usuário (taxas em fração)."""
    taxa_livre_risco: Optional[float] = None
    beta: Optional[float] = None
    premio_risco_mercado: Optional[float] = None
    custo_divida: Optional[float] = None

    @classmethod
    def de(cls, obj: Any) -> Optional["ParametrosMercado"]:
        """Aceita uma instância, um dict com as mesmas chaves ou None."""
        if obj is None or isinstance(obj, cls):
            return obj
        if isinstance(obj, dict):
            campos = {f.name for f in dataclasses.fields(cls)}
            return cls(**{k: v for k, v in obj.items() if k in campos})
        raise ValueError("Parâmetros de mercado devem ser um objeto com taxa_livre_risco, beta, "
                         "premio_risco_mercado e custo_divida.")


def normalizar_taxa(valor: Any, nome: str, avisos: List[str]) -> Optional[float]:
    """Taxa em fração. Valor > 1 é tratado como percentual (11 -> 0,11) e gera aviso."""
    if valor is None:
        return None
    if not _finito(valor):
        raise ValueError(f"{nome} inválida: {valor!r}.")
    if valor > 1:
        avisos.append(f"{nome}: o valor {_numero_curto(valor)} foi interpretado como percentual "
                      f"(usado {_numero_curto(valor)}/100 = {_pct(valor / 100)}).")
        return valor / 100
    return float(valor)


_NOMES_TAXAS = (
    ("taxa_livre_risco", "Taxa livre de risco"),
    ("premio_risco_mercado", "Prêmio de risco de mercado"),
    ("custo_divida", "Custo da dívida"),
)


def aplicar_parametros(dados: DadosFinanceiros, parametros: Any, avisos: List[str]) -> DadosFinanceiros:
    """Cópia de `dados` com os parâmetros informados sobrepostos a `dados.mercado` e as taxas normalizadas."""
    p = ParametrosMercado.de(parametros)
    mercado = dados.mercado
    novos: Dict[str, Optional[float]] = {}
    for campo in ("taxa_livre_risco", "beta", "premio_risco_mercado", "custo_divida"):
        informado = getattr(p, campo) if p is not None else None
        novos[campo] = informado if informado is not None else getattr(mercado, campo)
    for campo, nome in _NOMES_TAXAS:
        novos[campo] = normalizar_taxa(novos[campo], nome, avisos)
    beta = novos["beta"]
    if beta is not None:
        if not _finito(beta):
            raise ValueError(f"Beta inválido: {beta!r}.")
        if beta <= 0:
            avisos.append(f"Beta de {_numero_curto(beta)} (≤ 0) é incomum: confira o valor informado.")
    return dataclasses.replace(dados, mercado=dataclasses.replace(mercado, **novos))


def aliquota_aplicada(dados: DadosFinanceiros) -> Tuple[Optional[float], float, str, List[str]]:
    """(alíquota efetiva, alíquota aplicada, origem, avisos).

    A efetiva é IR e CS / LAIR. Se o LAIR não for positivo, o imposto faltar ou a efetiva sair de
    [0, 1], usa-se a alíquota nominal de 34%.
    """
    dre = dados.dre
    lair, imposto = dre.lair_calc, dre.imposto_renda
    efetiva = dividir(imposto, lair)
    nominal = f"usada a alíquota nominal de {_pct(ALIQUOTA_NOMINAL)}"
    if not _valido(imposto):
        return None, ALIQUOTA_NOMINAL, "nominal 34%", [f"IR e CS não informados: {nominal}."]
    if not _valido(lair) or lair <= 0:
        return efetiva, ALIQUOTA_NOMINAL, "nominal 34%", [
            f"Lucro antes dos impostos não positivo: a alíquota efetiva não tem sentido; {nominal}."]
    if not 0 <= efetiva <= 1:
        return efetiva, ALIQUOTA_NOMINAL, "nominal 34%", [
            f"Alíquota efetiva de {_pct(efetiva)} fora do intervalo de 0% a 100%; {nominal}."]
    return efetiva, efetiva, "efetiva", []


# ============================================================================
# Custo de capital (WACC)
# ============================================================================
def _valor_capital_proprio(dados: DadosFinanceiros) -> Tuple[Optional[float], str, Optional[str], List[str]]:
    """(E, base dos pesos, motivo se E indisponível, avisos)."""
    m, pl = dados.mercado, dados.balanco.patrimonio_liquido
    if _valido(m.preco_acao) and _valido(m.numero_acoes) and m.preco_acao * m.numero_acoes > 0:
        return m.preco_acao * m.numero_acoes, "mercado", None, []
    if _valido(pl) and pl > 0:
        return pl, "contábil", None, [
            "Preço da ação ou nº de ações não informado: os pesos do WACC usam o PL contábil no lugar do "
            "valor de mercado do capital próprio."]
    return None, "contábil", "informe o preço da ação (PL contábil não positivo)", []


def custo_capital(dados: DadosFinanceiros) -> Tuple[List[Indicador], Dict[str, Any], List[str]]:
    """Indicadores do módulo de custo de capital, metadados e avisos."""
    avisos: List[str] = []
    bp, dre, m = dados.balanco, dados.dre, dados.mercado

    # --- Kd contábil sobre a dívida média ---
    d = bp.divida_total
    anterior = dados.exercicio_anterior
    d_anterior = anterior.divida_total if anterior is not None else None
    if _valido(d) and _valido(d_anterior):
        divida_media = (d + d_anterior) / 2
        formula_kd = "Despesas Financeiras / Dívida Média"
    else:
        divida_media = d
        formula_kd = "Despesas Financeiras / Dívida (saldo atual)"
        if _valido(d) and d > 0:
            avisos.append("Sem a dívida do exercício anterior: o Kd contábil usa o saldo atual, não a média.")

    kd_contabil: Optional[float] = None
    motivo_kd: Optional[str] = None
    if not _valido(d):
        motivo_kd = "falta: empréstimos e financiamentos"
    elif d == 0:
        motivo_kd = "empresa sem dívida"
    elif not _valido(dre.despesas_financeiras):
        motivo_kd = "falta: despesas financeiras"
    else:
        kd_contabil = dividir(dre.despesas_financeiras, divida_media)
        if kd_contabil is None:
            motivo_kd = "dívida média igual a zero"

    informado = _valido(m.custo_divida)
    kd = m.custo_divida if informado else kd_contabil
    if kd_contabil is not None and not informado:
        sugestao = "Informe o custo da dívida (opção --kd ou campo Kd) para um WACC mais confiável."
        if kd_contabil > 1:
            avisos.append(f"Kd contábil de {_pct(kd_contabil)} a.a. é implausível (as despesas financeiras "
                          f"incluem variação cambial, derivativos e outros itens). {sugestao}")
        elif not FAIXA_KD_USUAL[0] <= kd_contabil <= FAIXA_KD_USUAL[1]:
            avisos.append(f"Atenção: Kd contábil de {_pct(kd_contabil)} a.a. está fora da faixa usual de "
                          f"{FAIXA_KD_USUAL[0] * 100:g}% a {FAIXA_KD_USUAL[1] * 100:g}% a.a. {sugestao}")

    # --- alíquota ---
    efetiva, t, origem_aliquota, avisos_aliquota = aliquota_aplicada(dados)
    avisos += avisos_aliquota
    kd_liquido = kd * (1 - t) if kd is not None else None

    # --- Ke (CAPM) ---
    ke: Optional[float] = None
    if all(_valido(x) for x in (m.taxa_livre_risco, m.beta, m.premio_risco_mercado)):
        ke = m.taxa_livre_risco + m.beta * m.premio_risco_mercado

    # --- pesos ---
    e, base_pesos, motivo_e, avisos_e = _valor_capital_proprio(dados)
    avisos += avisos_e
    dv = ev = None
    motivo_pesos: Optional[str] = None
    if not _valido(d):
        motivo_pesos = "falta: empréstimos e financiamentos"
    elif e is None:
        motivo_pesos = motivo_e
    else:
        dv, ev = d / (d + e), e / (d + e)

    # --- WACC ---
    wacc: Optional[float] = None
    motivo_wacc: Optional[str] = None
    if ke is None:
        motivo_wacc = MOTIVO_KE
    elif dv is None:
        motivo_wacc = motivo_pesos
    elif dv == 0:
        wacc = ke
        avisos.append("Estrutura 100% capital próprio (sem dívida): WACC = Ke.")
    elif kd is None:
        motivo_wacc = f"Kd indisponível ({motivo_kd})"
    else:
        wacc = dv * kd * (1 - t) + ev * ke

    indicadores = [
        Indicador("Custo da Dívida (Kd)", kd_contabil, "%", formula_kd, None if kd_contabil is not None else motivo_kd),
        Indicador("Alíquota Efetiva de IR/CS", efetiva, "%", "IR e CS / Lucro antes dos Impostos",
                  None if efetiva is not None else "falta: IR e CS ou lucro antes dos impostos"),
        Indicador("Alíquota Aplicada", t, "%", "Efetiva, ou 34% se a efetiva for implausível"),
        Indicador("Kd após Impostos", kd_liquido, "%",
                  "Kd informado × (1 − Alíquota)" if informado else "Kd × (1 − Alíquota)",
                  None if kd_liquido is not None else motivo_kd),
        Indicador("Custo do Capital Próprio (Ke)", ke, "%", "Rf + β × Prêmio de Mercado",
                  None if ke is not None else MOTIVO_KE),
        Indicador("Valor do Capital Próprio (E)", e, "R$ mil",
                  "Preço × Nº de Ações" if base_pesos == "mercado" else "PL contábil (sem preço da ação)",
                  motivo_e),
        Indicador("Dívida (D)", d, "R$ mil", "Empréstimos CP + LP",
                  None if _valido(d) else "falta: empréstimos e financiamentos"),
        Indicador("Peso da Dívida (D/V)", dv, "%", "D / (D + E)", motivo_pesos),
        Indicador("Peso do Capital Próprio (E/V)", ev, "%", "E / (D + E)", motivo_pesos),
        Indicador("WACC", wacc, "%", "D/V × Kd × (1 − t) + E/V × Ke", motivo_wacc),
    ]
    meta: Dict[str, Any] = {
        "base_pesos": base_pesos,
        "kd_utilizado": "informado" if informado else "contábil",
        "origem_aliquota": origem_aliquota,
        "ke": ke, "wacc": wacc, "motivo_wacc": motivo_wacc, "aliquota": t, "kd": kd,
        "d": d if _valido(d) else None, "e": e, "dv": dv,
    }
    return indicadores, meta, avisos


# ============================================================================
# Endividamento e graus de alavancagem
# ============================================================================
def _variacao(atual: Optional[float], anterior: Optional[float]) -> Optional[float]:
    """Δ% = atual / anterior − 1 (None se faltar dado ou se o anterior for zero)."""
    razao = dividir(atual, anterior)
    return None if razao is None else razao - 1


def endividamento_alavancagem(dados: DadosFinanceiros) -> Tuple[List[Indicador], List[str]]:
    """Indicadores acrescentados ao módulo de estrutura de capital, e avisos."""
    avisos: List[str] = []
    bp, dre = dados.balanco, dados.dre
    d, pl = bp.divida_total, bp.patrimonio_liquido
    ebit = dre.ebit_calc
    caixa = bp.caixa if _valido(bp.caixa) else 0.0
    divida_liquida = d - caixa if _valido(d) else None
    ebitda = ebit + dre.depreciacao_amortizacao if _valido(ebit) and _valido(dre.depreciacao_amortizacao) else None

    dl_ebitda: Optional[float] = None
    motivo_dl: Optional[str] = None
    if divida_liquida is None:
        motivo_dl = "falta: empréstimos e financiamentos"
    elif ebitda is None:
        motivo_dl = "falta: EBITDA (EBIT ou depreciação e amortização)"
    elif ebitda <= 0:
        motivo_dl = "EBITDA não positivo"
    else:
        dl_ebitda = divida_liquida / ebitda

    d_dpl = dividir(d, d + pl) if _valido(d) and _valido(pl) else None

    gao = gaf = gac = None
    motivo_gao = motivo_gaf = None
    anterior = dados.exercicio_anterior
    if anterior is None:
        motivo_gao = motivo_gaf = "sem exercício anterior"
    else:
        dv = _variacao(dre.vendas, anterior.vendas)
        de = _variacao(ebit, anterior.ebit)
        dl = _variacao(dre.lucro_liquido_calc, anterior.lucro_liquido)
        if de is None:
            motivo_gao = motivo_gaf = "falta: EBIT de um dos exercícios (ou EBIT anterior igual a zero)"
        if dv is None:
            motivo_gao = "falta: vendas de um dos exercícios (ou vendas anteriores iguais a zero)"
        elif abs(dv) < 1e-12:
            motivo_gao = "variação das vendas igual a zero"
        elif de is not None:
            gao = de / dv
        if de is not None:
            if dl is None:
                motivo_gaf = "falta: lucro líquido de um dos exercícios (ou lucro anterior igual a zero)"
            elif abs(de) < 1e-12:
                motivo_gaf = "variação do EBIT igual a zero"
            else:
                gaf = dl / de
        sem_sentido = []
        if _valido(anterior.vendas) and anterior.vendas <= 0:
            sem_sentido.append("vendas anteriores não positivas")
        if _valido(anterior.ebit) and _valido(ebit) and (anterior.ebit <= 0 or (anterior.ebit > 0) != (ebit > 0)):
            sem_sentido.append("EBIT anterior não positivo ou com sinal diferente do atual")
        if _valido(anterior.lucro_liquido) and anterior.lucro_liquido <= 0:
            sem_sentido.append("lucro líquido anterior não positivo")
        if sem_sentido and (gao is not None or gaf is not None):
            avisos.append("Graus de alavancagem calculados, mas sem interpretação econômica: "
                          + "; ".join(sem_sentido) + ".")
    if gao is not None and gaf is not None:
        gac = gao * gaf
    motivo_gac = None if gac is not None else (motivo_gao or motivo_gaf)

    return [
        Indicador("Dívida Líquida", divida_liquida, "R$ mil", "Dívida Total − Caixa",
                  None if divida_liquida is not None else "falta: empréstimos e financiamentos"),
        Indicador("Dívida Líquida / EBITDA", dl_ebitda, "x", "Dívida Líquida / EBITDA", motivo_dl),
        Indicador("Dívida / (Dívida + PL)", d_dpl, "%", "Dívida Total / (Dívida Total + PL)",
                  None if d_dpl is not None else "falta: dívida ou patrimônio líquido"),
        Indicador("Grau de Alavancagem Operacional (GAO)", gao, "x", "Δ% EBIT / Δ% Vendas", motivo_gao),
        Indicador("Grau de Alavancagem Financeira (GAF)", gaf, "x", "Δ% Lucro Líquido / Δ% EBIT", motivo_gaf),
        Indicador("Grau de Alavancagem Combinada (GAC)", gac, "x", "GAO × GAF", motivo_gac),
    ], avisos


# ============================================================================
# Análise EBIT-LPA
# ============================================================================
@dataclass
class CenarioCaptacao:
    """Cenário de captação: valor (R$ mil), taxa da nova dívida (fração), preço de emissão (R$/ação)."""
    valor: float
    taxa_divida: float
    preco_emissao: float
    ebit_projetado: Optional[float] = None

    def __post_init__(self) -> None:
        for campo, mensagem in (("valor", "Valor a captar deve ser maior que zero."),
                                ("taxa_divida", "Taxa da nova dívida deve ser maior que zero."),
                                ("preco_emissao", "Preço de emissão deve ser maior que zero.")):
            v = getattr(self, campo)
            if not _finito(v) or v <= 0:
                raise ValueError(mensagem)
        if self.ebit_projetado is not None and not _finito(self.ebit_projetado):
            raise ValueError(f"EBIT projetado inválido: {self.ebit_projetado!r}.")

    @classmethod
    def de(cls, obj: Any) -> "CenarioCaptacao":
        """Aceita uma instância ou um dict com as mesmas chaves."""
        if isinstance(obj, cls):
            return obj
        if isinstance(obj, dict):
            return cls(valor=obj.get("valor"), taxa_divida=obj.get("taxa_divida"),
                       preco_emissao=obj.get("preco_emissao"), ebit_projetado=obj.get("ebit_projetado"))
        raise ValueError("Cenário de captação inválido: informe valor, taxa_divida e preco_emissao.")


def indiferenca(alt1: Tuple[float, float], alt2: Tuple[float, float], aliquota: float) -> Optional[float]:
    """EBIT de indiferença entre duas alternativas (juros, nº de ações).

    EBIT* = (J1·N2 − J2·N1) / (N2 − N1). A alíquota se cancela na igualdade dos LPAs; None se as
    retas forem paralelas (mesmo número de ações).
    """
    (j1, n1), (j2, n2) = alt1, alt2
    if abs(n2 - n1) <= 1e-12 * max(abs(n1), abs(n2), 1.0):
        return None
    return (j1 * n2 - j2 * n1) / (n2 - n1)


def _lpa(ebit: float, juros: float, acoes: float, t: float) -> float:
    return (ebit - juros) * (1 - t) / acoes


def analise_ebit_lpa(dados: DadosFinanceiros, cenario: CenarioCaptacao) -> Dict[str, Any]:
    """Compara o financiamento por dívida e por ações para o cenário de captação."""
    cenario = CenarioCaptacao.de(cenario)
    n0 = dados.mercado.numero_acoes
    if not _valido(n0) or n0 <= 0:
        return {"motivo": "informe o número de ações"}
    ebit_avaliado = cenario.ebit_projetado if cenario.ebit_projetado is not None else dados.dre.ebit_calc
    if not _valido(ebit_avaliado):
        return {"motivo": "falta: EBIT"}
    juros_atuais = dados.dre.despesas_financeiras if _valido(dados.dre.despesas_financeiras) else 0.0
    t = aliquota_aplicada(dados)[1]
    novas_acoes = cenario.valor / cenario.preco_emissao      # R$ mil / (R$/ação) = milhares de ações
    bases = [("Dívida", juros_atuais + cenario.valor * cenario.taxa_divida, n0),
             ("Ações", juros_atuais, n0 + novas_acoes)]
    alternativas = [{
        "nome": nome, "juros": j, "acoes": n, "lpa_no_ebit": _lpa(ebit_avaliado, j, n, t),
        "inclinacao": (1 - t) / n, "intercepto": -j * (1 - t) / n,
    } for nome, j, n in bases]

    ebit_ind = indiferenca((bases[0][1], bases[0][2]), (bases[1][1], bases[1][2]), t)
    lpa_ind = _lpa(ebit_ind, bases[0][1], bases[0][2], t) if ebit_ind is not None else None
    diferenca = alternativas[0]["lpa_no_ebit"] - alternativas[1]["lpa_no_ebit"]
    melhor = "Empate" if abs(diferenca) <= 1e-9 else ("Dívida" if diferenca > 0 else "Ações")
    dominante = None
    if ebit_ind is None:
        dominante = max(alternativas, key=lambda a: a["intercepto"])["nome"]

    ebit_max = 2 * max(ebit_avaliado, ebit_ind if ebit_ind is not None else ebit_avaliado)
    if ebit_max <= 0:
        ebit_max = 2 * max(abs(ebit_avaliado), bases[0][1], 1.0)
    pontos = [{"ebit": x, "lpa_divida": _lpa(x, bases[0][1], bases[0][2], t),
               "lpa_acoes": _lpa(x, bases[1][1], bases[1][2], t)} for x in (0, ebit_max)]
    avisos = []
    if ebit_ind is not None and ebit_ind < 0:
        avisos.append("O EBIT de indiferença é negativo: a alternativa por dívida domina em qualquer EBIT positivo.")
    return {
        "valor": cenario.valor, "taxa_divida": cenario.taxa_divida, "preco_emissao": cenario.preco_emissao,
        "novas_acoes": novas_acoes, "alternativas": alternativas, "ebit_avaliado": ebit_avaliado,
        "origem_ebit": "projetado" if cenario.ebit_projetado is not None else "atual",
        "ebit_indiferenca": ebit_ind, "lpa_indiferenca": lpa_ind, "melhor_no_ebit": melhor,
        "dominante": dominante, "aliquota": t, "pontos_grafico": pontos, "avisos": avisos,
    }


# ============================================================================
# Simulação da estrutura ótima (Hamada + ratings sintéticos) e MM com impostos
# ============================================================================
def rating_sintetico(cobertura: float,
                     tabela: Sequence[Tuple[float, str, float]] = TABELA_SPREADS) -> Tuple[str, float]:
    """(rating, spread) da faixa de cobertura de juros."""
    for minimo, rating, spread in tabela:
        if cobertura >= minimo:
            return rating, spread
    return tabela[-1][1], tabela[-1][2]


def kd_sintetico(ebit: float, divida: float, rf: float,
                 tabela: Sequence[Tuple[float, str, float]] = TABELA_SPREADS,
                 max_iteracoes: int = MAX_ITERACOES_KD) -> Dict[str, Any]:
    """Kd = Rf + spread(cobertura), com cobertura = EBIT / (D × Kd).

    A relação é circular: parte-se do spread da melhor faixa e itera-se até estabilizar. Se as faixas
    entrarem em ciclo (ou o limite de iterações for atingido), adota-se o maior Kd visitado (conservador).
    """
    kd = rf + tabela[0][2]
    historico: List[float] = []
    iteracoes = 0
    while iteracoes < max_iteracoes:
        iteracoes += 1
        novo = rf + rating_sintetico(ebit / (divida * kd), tabela)[1]
        if abs(novo - kd) < 1e-12:
            break
        historico.append(kd)
        if any(abs(novo - h) < 1e-12 for h in historico):
            inicio = next(i for i, h in enumerate(historico) if abs(novo - h) < 1e-12)
            kd = max(historico[inicio:])
            break
        kd = novo
    else:
        kd = max(historico + [kd])
    cobertura = ebit / (divida * kd)
    rating, spread = rating_sintetico(cobertura, tabela)
    return {"kd": kd, "cobertura": cobertura, "rating": rating, "spread": kd - rf, "iteracoes": iteracoes}


PREMISSAS_SIMULACAO = [
    "Kd de cada nível = Rf + spread do rating sintético pela cobertura de juros (EBIT / juros), tabela de "
    "Damodaran (empresas não financeiras de grande porte, jan/2026); a relação circular é resolvida por iteração.",
    "Valor da empresa (V = D + E) mantido constante; só a composição entre dívida e capital próprio muda.",
    "Beta re-alavancado por Hamada: βL = βu × [1 + (1 − t) × D/E].",
    "Com cobertura < 1, o benefício fiscal é parcial: alíquota usada = t × cobertura.",
    "Por causa das faixas discretas de rating, a curva pode ter pequenos \"dentes\" (não é estritamente convexa).",
    "O Kd simulado (Rf + spread) difere do Kd contábil; por isso o WACC simulado no D/V atual pode diferir "
    "do WACC calculado.",
]


def simular_estrutura(dados: DadosFinanceiros, passos: Iterable[int] = range(0, 81, 10)) -> Dict[str, Any]:
    """Tabela do WACC por nível de endividamento (D/V em %), ponto ótimo e benefício fiscal de MM."""
    _, meta, _ = custo_capital(dados)
    m = dados.mercado
    ebit = dados.dre.ebit_calc
    d, e, t = meta["d"], meta["e"], meta["aliquota"]
    faltando = []
    if not _valido(m.taxa_livre_risco):
        faltando.append("taxa livre de risco (Rf)")
    if not _valido(m.beta):
        faltando.append("beta")
    if not _valido(m.premio_risco_mercado):
        faltando.append("prêmio de risco de mercado")
    if not _valido(ebit):
        faltando.append("EBIT")
    if d is None:
        faltando.append("dívida (empréstimos e financiamentos)")
    if e is None or e <= 0:
        faltando.append("valor do capital próprio (preço da ação, ou PL positivo)")
    if faltando:
        return {"faltando": faltando}

    rf, premio = m.taxa_livre_risco, m.premio_risco_mercado
    beta_u = m.beta / (1 + (1 - t) * d / e)
    v = d + e
    pontos = []
    for passo in passos:
        w = passo / 100
        if not 0 <= w < 1:
            raise ValueError("Os níveis de D/V da simulação devem estar entre 0% e 99%.")
        beta_l = beta_u * (1 + (1 - t) * w / (1 - w))
        ke = rf + beta_l * premio
        if w == 0:
            pontos.append({"dv": w, "beta": beta_l, "ke": ke, "cobertura": None, "rating": "—",
                           "spread": None, "kd": None, "aliquota": t, "wacc": ke})
            continue
        r = kd_sintetico(ebit, w * v, rf)
        t_w = t * max(r["cobertura"], 0.0) if r["cobertura"] < 1 else t
        pontos.append({"dv": w, "beta": beta_l, "ke": ke, "cobertura": r["cobertura"], "rating": r["rating"],
                       "spread": r["spread"], "kd": r["kd"], "aliquota": t_w,
                       "wacc": w * r["kd"] * (1 - t_w) + (1 - w) * ke})
    otimo = min(pontos, key=lambda p: p["wacc"])
    return {
        "pontos": pontos,
        "beta_desalavancado": beta_u,
        "otimo": {"dv": otimo["dv"], "wacc": otimo["wacc"]},
        "atual": {"dv": meta["dv"], "wacc_calculado": meta["wacc"]},
        "modigliani_miller": {"valor_alavancado": v, "beneficio_fiscal": t * d, "valor_desalavancado": v - t * d},
        "aliquota": t,
        "base_pesos": meta["base_pesos"],
        "premissas": list(PREMISSAS_SIMULACAO),
    }
