#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de Demonstrações Financeiras
====================================
CAD 167 – Administração Financeira (UFMG) – Trabalho 1

Recebe Balanço Patrimonial, DRE, DFC e dados de mercado e calcula, por módulo:
  1. Liquidez e Gestão de Capital de Giro
  2. Lucratividade e Rentabilidade
  3. Eficiência e Decomposição DuPont
  4. Estrutura de Capital e Alavancagem
  5. Múltiplos e Avaliação de Mercado
  (+ resumo dos Fluxos de Caixa, como informação complementar)

Captura de dados (três formas):
  - dicionário Python (DADOS_EXEMPLO, usado por padrão);
  - arquivo JSON:          python analise_demonstracoes_financeiras.py --json dados.json
  - DataFrame do pandas:   DadosFinanceiros.from_dataframe(df)  (formato longo:
                           colunas "demonstracao", "conta", "valor")

Geração de relatórios: console (sempre) e, opcionalmente, arquivos .txt e .json:
  python analise_demonstracoes_financeiras.py --saida-txt rel.txt --saida-json rel.json

Convenções:
  - Valores monetários em R$ mil; número de ações em milhares (LPA e VPA saem em R$/ação).
  - Indicadores de balanço usam saldos de fim de período (não médias).
  - Divisão por zero ou dado ausente => indicador "n/d" (None), sem interromper o programa.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, fields, asdict
from typing import Any, Dict, List, Optional

DIAS_NO_ANO = 365  # base de dias para o prazo médio de recebimento


# ----------------------------------------------------------------------------
# Funções utilitárias (tratamento seguro de dados ausentes e divisões por zero)
# ----------------------------------------------------------------------------
def _valido(x: Optional[float]) -> bool:
    """Retorna True se x é um número utilizável (não None e não NaN)."""
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def dividir(numerador: Optional[float], denominador: Optional[float]) -> Optional[float]:
    """Divisão segura: devolve None se faltar dado ou se o denominador for zero."""
    if not _valido(numerador) or not _valido(denominador) or denominador == 0:
        return None
    return numerador / denominador


def somar(*valores: Optional[float]) -> Optional[float]:
    """Soma ignorando valores ausentes; devolve None se TODOS estiverem ausentes."""
    validos = [v for v in valores if _valido(v)]
    return sum(validos) if validos else None


def subtrair(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Subtração segura: None se qualquer operando estiver ausente."""
    if not _valido(a) or not _valido(b):
        return None
    return a - b


def multiplicar(*valores: Optional[float]) -> Optional[float]:
    """Produto seguro: None se qualquer fator estiver ausente."""
    if not all(_valido(v) for v in valores):
        return None
    resultado = 1.0
    for v in valores:
        resultado *= v  # type: ignore[operator]
    return resultado


# ----------------------------------------------------------------------------
# Estruturas de dados das demonstrações
# ----------------------------------------------------------------------------
@dataclass
class BalancoPatrimonial:
    """Balanço Patrimonial. Totais podem ser informados ou calculados a partir das contas."""
    caixa: Optional[float] = None                        # Caixa e equivalentes
    contas_receber: Optional[float] = None
    estoques: Optional[float] = None
    outros_ativos_circulantes: Optional[float] = None
    ativo_circulante: Optional[float] = None             # opcional (senão, soma das contas)
    imobilizado: Optional[float] = None                  # "ativos fixos"
    intangivel: Optional[float] = None
    outros_ativos_nao_circulantes: Optional[float] = None
    ativo_nao_circulante: Optional[float] = None         # opcional
    ativo_total: Optional[float] = None                  # opcional
    fornecedores: Optional[float] = None
    emprestimos_cp: Optional[float] = None               # dívida de curto prazo
    outros_passivos_circulantes: Optional[float] = None
    passivo_circulante: Optional[float] = None           # opcional
    emprestimos_lp: Optional[float] = None               # dívida de longo prazo
    outros_passivos_nao_circulantes: Optional[float] = None
    patrimonio_liquido: Optional[float] = None

    # --- valores derivados: usam o total informado ou, na falta dele, a soma das contas ---
    @property
    def total_ativo_circulante(self) -> Optional[float]:
        if _valido(self.ativo_circulante):
            return self.ativo_circulante
        return somar(self.caixa, self.contas_receber, self.estoques, self.outros_ativos_circulantes)

    @property
    def total_ativo_nao_circulante(self) -> Optional[float]:
        if _valido(self.ativo_nao_circulante):
            return self.ativo_nao_circulante
        return somar(self.imobilizado, self.intangivel, self.outros_ativos_nao_circulantes)

    @property
    def total_ativo(self) -> Optional[float]:
        if _valido(self.ativo_total):
            return self.ativo_total
        return somar(self.total_ativo_circulante, self.total_ativo_nao_circulante)

    @property
    def total_passivo_circulante(self) -> Optional[float]:
        if _valido(self.passivo_circulante):
            return self.passivo_circulante
        return somar(self.fornecedores, self.emprestimos_cp, self.outros_passivos_circulantes)

    @property
    def divida_total(self) -> Optional[float]:
        """Dívida total = empréstimos/financiamentos de curto + longo prazo."""
        return somar(self.emprestimos_cp, self.emprestimos_lp)


@dataclass
class DRE:
    """Demonstração do Resultado do Exercício."""
    vendas: Optional[float] = None                       # receita líquida de vendas
    cmv: Optional[float] = None                          # custo das mercadorias vendidas
    lucro_bruto: Optional[float] = None                  # opcional (senão, Vendas - CMV)
    despesas_operacionais: Optional[float] = None        # vendas, administrativas etc.
    depreciacao_amortizacao: Optional[float] = None
    ebit: Optional[float] = None                         # opcional (senão, LB - desp. operacionais)
    despesas_financeiras: Optional[float] = None
    imposto_renda: Optional[float] = None
    lucro_liquido: Optional[float] = None                # opcional (senão, derivado)

    @property
    def lucro_bruto_calc(self) -> Optional[float]:
        if _valido(self.lucro_bruto):
            return self.lucro_bruto
        return subtrair(self.vendas, self.cmv)

    @property
    def ebit_calc(self) -> Optional[float]:
        if _valido(self.ebit):
            return self.ebit
        return subtrair(self.lucro_bruto_calc, self.despesas_operacionais)

    @property
    def lucro_liquido_calc(self) -> Optional[float]:
        if _valido(self.lucro_liquido):
            return self.lucro_liquido
        lair = subtrair(self.ebit_calc, self.despesas_financeiras)
        if not _valido(lair):
            return None
        return lair - (self.imposto_renda if _valido(self.imposto_renda) else 0.0)


@dataclass
class DFC:
    """Demonstração dos Fluxos de Caixa (resumo por atividade)."""
    fluxo_operacional: Optional[float] = None
    fluxo_investimento: Optional[float] = None
    fluxo_financiamento: Optional[float] = None

    @property
    def variacao_caixa(self) -> Optional[float]:
        return somar(self.fluxo_operacional, self.fluxo_investimento, self.fluxo_financiamento)


@dataclass
class DadosMercado:
    """Dados de mercado necessários aos múltiplos."""
    preco_acao: Optional[float] = None                   # R$ por ação
    numero_acoes: Optional[float] = None                 # em milhares de ações


def _construir(classe, dados: Optional[Dict[str, Any]]):
    """Cria um dataclass a partir de um dict, ignorando chaves desconhecidas."""
    dados = dados or {}
    campos = {f.name for f in fields(classe)}
    return classe(**{k: v for k, v in dados.items() if k in campos})


@dataclass
class DadosFinanceiros:
    """Agrupa as demonstrações de uma empresa e oferece formas de captura de dados."""
    empresa: str
    periodo: str
    balanco: BalancoPatrimonial
    dre: DRE
    dfc: DFC
    mercado: DadosMercado

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DadosFinanceiros":
        """Formato: {"empresa", "periodo", "balanco": {...}, "dre": {...}, "dfc": {...}, "mercado": {...}}"""
        return cls(
            empresa=d.get("empresa", "Empresa"),
            periodo=str(d.get("periodo", "")),
            balanco=_construir(BalancoPatrimonial, d.get("balanco")),
            dre=_construir(DRE, d.get("dre")),
            dfc=_construir(DFC, d.get("dfc")),
            mercado=_construir(DadosMercado, d.get("mercado")),
        )

    @classmethod
    def from_json(cls, caminho: str) -> "DadosFinanceiros":
        """Lê um arquivo JSON no mesmo formato de from_dict."""
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return cls.from_dict(json.load(arquivo))

    @classmethod
    def from_dataframe(cls, df, empresa: str = "Empresa", periodo: str = "") -> "DadosFinanceiros":
        """DataFrame em formato longo com colunas: demonstracao, conta, valor."""
        estrutura: Dict[str, Any] = {"empresa": empresa, "periodo": periodo}
        for _, linha in df.iterrows():
            estrutura.setdefault(str(linha["demonstracao"]), {})[str(linha["conta"])] = linha["valor"]
        return cls.from_dict(estrutura)


# ----------------------------------------------------------------------------
# Resultado: cada indicador carrega nome, valor, unidade e fórmula
# ----------------------------------------------------------------------------
@dataclass
class Indicador:
    nome: str
    valor: Optional[float]
    unidade: str      # "x", "%", "dias", "R$ mil", "R$/ação"
    formula: str


def _num_br(valor: float, casas: int = 2) -> str:
    """Formata número no padrão brasileiro (1.234,56)."""
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_valor(ind: Indicador) -> str:
    """Formata o valor de acordo com a unidade; 'n/d' quando não calculável."""
    if not _valido(ind.valor):
        return "n/d"
    v = ind.valor  # type: ignore[assignment]
    if ind.unidade == "%":
        return f"{_num_br(v * 100)}%"
    if ind.unidade == "x":
        return f"{_num_br(v)}x"
    if ind.unidade == "dias":
        return f"{_num_br(v, 1)} dias"
    if ind.unidade == "R$ mil":
        return f"R$ {_num_br(v, 0)} mil"
    if ind.unidade == "R$/ação":
        return f"R$ {_num_br(v)}"
    return _num_br(v)


# ----------------------------------------------------------------------------
# Analisador: um método por módulo
# ----------------------------------------------------------------------------
class AnalisadorFinanceiro:
    """Calcula os indicadores de análise de demonstrações financeiras."""

    def __init__(self, dados: DadosFinanceiros, usar_cmv_no_giro_estoque: bool = True) -> None:
        self.dados = dados
        self.bp = dados.balanco
        self.dre = dados.dre
        self.dfc = dados.dfc
        self.mercado = dados.mercado
        self.usar_cmv = usar_cmv_no_giro_estoque

    # --- 1. Liquidez e Gestão de Capital de Giro ---------------------------------------
    def liquidez_capital_giro(self) -> List[Indicador]:
        ac, pc = self.bp.total_ativo_circulante, self.bp.total_passivo_circulante
        ativo_sem_estoque = subtrair(ac, self.bp.estoques)
        vendas_por_dia = dividir(self.dre.vendas, DIAS_NO_ANO)
        # Giro do estoque: CMV (padrão) ou Vendas, se o CMV não existir ou se escolhido assim
        base_giro = self.dre.cmv if (self.usar_cmv and _valido(self.dre.cmv)) else self.dre.vendas
        nome_base = "CMV" if base_giro is self.dre.cmv and _valido(self.dre.cmv) else "Vendas"
        return [
            Indicador("Liquidez Corrente", dividir(ac, pc), "x",
                      "Ativo Circulante / Passivo Circulante"),
            Indicador("Liquidez Seca", dividir(ativo_sem_estoque, pc), "x",
                      "(Ativo Circulante - Estoque) / Passivo Circulante"),
            Indicador("Prazo Médio de Recebimento", dividir(self.bp.contas_receber, vendas_por_dia), "dias",
                      "Contas a Receber / (Vendas / 365)"),
            Indicador("Giro do Estoque", dividir(base_giro, self.bp.estoques), "x",
                      f"{nome_base} / Estoque"),
        ]

    # --- 2. Lucratividade e Rentabilidade ----------------------------------------------
    def lucratividade(self) -> List[Indicador]:
        vendas = self.dre.vendas
        ebit = self.dre.ebit_calc
        return [
            Indicador("Margem Bruta", dividir(self.dre.lucro_bruto_calc, vendas), "%",
                      "Lucro Bruto / Vendas"),
            Indicador("Margem Operacional", dividir(ebit, vendas), "%",
                      "EBIT / Vendas"),
            Indicador("Margem Líquida", dividir(self.dre.lucro_liquido_calc, vendas), "%",
                      "Lucro Líquido / Vendas"),
            Indicador("EBITDA",
                      (ebit + self.dre.depreciacao_amortizacao)
                      if _valido(ebit) and _valido(self.dre.depreciacao_amortizacao) else None,
                      "R$ mil", "EBIT + Depreciação e Amortização"),
        ]

    # --- 3. Eficiência e DuPont --------------------------------------------------------
    def eficiencia_dupont(self) -> List[Indicador]:
        vendas, ll = self.dre.vendas, self.dre.lucro_liquido_calc
        at, pl = self.bp.total_ativo, self.bp.patrimonio_liquido
        margem_liquida = dividir(ll, vendas)
        giro_ativo = dividir(vendas, at)
        multiplicador = dividir(at, pl)
        return [
            Indicador("Giro do Ativo Total", giro_ativo, "x", "Vendas / Ativo Total"),
            Indicador("Giro dos Ativos Fixos", dividir(vendas, self.bp.imobilizado), "x",
                      "Vendas / Ativos Fixos (Imobilizado)"),
            Indicador("ROA", dividir(ll, at), "%", "Lucro Líquido / Ativo Total"),
            Indicador("ROE", dividir(ll, pl), "%", "Lucro Líquido / Patrimônio Líquido"),
            Indicador("DuPont - Margem Líquida", margem_liquida, "%", "Lucro Líquido / Vendas"),
            Indicador("DuPont - Giro do Ativo Total", giro_ativo, "x", "Vendas / Ativo Total"),
            Indicador("DuPont - Multiplicador de Capital", multiplicador, "x",
                      "Ativo Total / Patrimônio Líquido"),
            Indicador("DuPont - ROE (produto dos 3 fatores)",
                      multiplicar(margem_liquida, giro_ativo, multiplicador), "%",
                      "Margem Líquida x Giro do Ativo x (Ativo / PL)"),
        ]

    # --- 4. Estrutura de Capital e Alavancagem -----------------------------------------
    def estrutura_capital(self) -> List[Indicador]:
        return [
            Indicador("Capital de Terceiros / Capital Próprio",
                      dividir(self.bp.divida_total, self.bp.patrimonio_liquido), "x",
                      "Dívida Total / Patrimônio Líquido"),
            Indicador("Cobertura de Juros (TIE)",
                      dividir(self.dre.ebit_calc, self.dre.despesas_financeiras), "x",
                      "EBIT / Despesas Financeiras"),
        ]

    # --- 5. Múltiplos e Avaliação de Mercado -------------------------------------------
    def multiplos_mercado(self) -> List[Indicador]:
        acoes, preco = self.mercado.numero_acoes, self.mercado.preco_acao
        pl = self.bp.patrimonio_liquido
        lpa = dividir(self.dre.lucro_liquido_calc, acoes)
        vpa = dividir(pl, acoes)
        valor_mercado_pl = multiplicar(preco, acoes)          # capitalização de mercado
        ev = None
        if _valido(valor_mercado_pl) and _valido(self.bp.divida_total):
            ev = valor_mercado_pl + self.bp.divida_total - (self.bp.caixa if _valido(self.bp.caixa) else 0.0)
        return [
            Indicador("Lucro por Ação (LPA)", lpa, "R$/ação", "Lucro Líquido / Nº de Ações"),
            Indicador("Valor Contábil por Ação (VPA)", vpa, "R$/ação", "Patrimônio Líquido / Nº de Ações"),
            Indicador("Preço/Lucro (P/L)", dividir(preco, lpa), "x", "Preço da Ação / LPA"),
            Indicador("Market-to-Book", dividir(valor_mercado_pl, pl), "x",
                      "Valor de Mercado do PL / Valor Contábil do PL"),
            Indicador("Valor de Mercado do PL", valor_mercado_pl, "R$ mil", "Preço da Ação x Nº de Ações"),
            Indicador("Enterprise Value (EV)", ev, "R$ mil",
                      "Valor de Mercado do PL + Dívida Total - Caixa"),
        ]

    # --- Complemento: Fluxos de Caixa --------------------------------------------------
    def fluxos_caixa(self) -> List[Indicador]:
        return [
            Indicador("Fluxo de Caixa Operacional", self.dfc.fluxo_operacional, "R$ mil", "DFC - atividades operacionais"),
            Indicador("Fluxo de Caixa de Investimento", self.dfc.fluxo_investimento, "R$ mil", "DFC - atividades de investimento"),
            Indicador("Fluxo de Caixa de Financiamento", self.dfc.fluxo_financiamento, "R$ mil", "DFC - atividades de financiamento"),
            Indicador("Variação Líquida de Caixa", self.dfc.variacao_caixa, "R$ mil", "FCO + FCI + FCF"),
        ]

    # --- Relatório ----------------------------------------------------------------------
    def gerar_relatorio(self) -> Dict[str, List[Indicador]]:
        """Retorna o relatório estruturado: {módulo: [indicadores]}."""
        return {
            "1. LIQUIDEZ E GESTÃO DE CAPITAL DE GIRO": self.liquidez_capital_giro(),
            "2. LUCRATIVIDADE E RENTABILIDADE": self.lucratividade(),
            "3. EFICIÊNCIA E DECOMPOSIÇÃO DUPONT": self.eficiencia_dupont(),
            "4. ESTRUTURA DE CAPITAL E ALAVANCAGEM": self.estrutura_capital(),
            "5. MÚLTIPLOS E AVALIAÇÃO DE MERCADO": self.multiplos_mercado(),
            "6. FLUXOS DE CAIXA (COMPLEMENTAR)": self.fluxos_caixa(),
        }

    def formatar_relatorio(self) -> str:
        """Monta o relatório em texto formatado para o console/arquivo."""
        largura = 84
        linhas = ["=" * largura,
                  "RELATÓRIO DE ANÁLISE DE DEMONSTRAÇÕES FINANCEIRAS".center(largura),
                  f"{self.dados.empresa} - {self.dados.periodo}".center(largura),
                  "(valores monetários em R$ mil)".center(largura),
                  "=" * largura]
        for modulo, indicadores in self.gerar_relatorio().items():
            linhas += ["", modulo, "-" * largura]
            for ind in indicadores:
                linhas.append(f"  {ind.nome:<40}{formatar_valor(ind):>18}   {ind.formula}")
        linhas += ["", "=" * largura,
                   "n/d = não disponível (dado ausente ou divisão por zero)."]
        return "\n".join(linhas)

    def exportar_json(self, caminho: str) -> None:
        """Salva o relatório estruturado em JSON."""
        conteudo = {
            "empresa": self.dados.empresa,
            "periodo": self.dados.periodo,
            "modulos": {m: [asdict(i) for i in inds] for m, inds in self.gerar_relatorio().items()},
        }
        with open(caminho, "w", encoding="utf-8") as arquivo:
            json.dump(conteudo, arquivo, ensure_ascii=False, indent=2)


# ----------------------------------------------------------------------------
# Dados fictícios de exemplo (Empresa Teste S.A.) - R$ mil
# ----------------------------------------------------------------------------
DADOS_EXEMPLO: Dict[str, Any] = {
    "empresa": "Empresa Teste S.A.",
    "periodo": "Exercício de 2025",
    "balanco": {
        "caixa": 120_000, "contas_receber": 280_000, "estoques": 200_000,
        "outros_ativos_circulantes": 20_000,
        "imobilizado": 700_000, "intangivel": 80_000, "outros_ativos_nao_circulantes": 100_000,
        "fornecedores": 150_000, "emprestimos_cp": 120_000, "outros_passivos_circulantes": 130_000,
        "emprestimos_lp": 400_000, "outros_passivos_nao_circulantes": 100_000,
        "patrimonio_liquido": 600_000,
    },
    "dre": {
        "vendas": 2_000_000, "cmv": 1_200_000, "despesas_operacionais": 450_000,
        "depreciacao_amortizacao": 90_000, "despesas_financeiras": 70_000,
        "imposto_renda": 95_200,
    },
    "dfc": {
        "fluxo_operacional": 310_000, "fluxo_investimento": -180_000, "fluxo_financiamento": -60_000,
    },
    "mercado": {"preco_acao": 18.00, "numero_acoes": 100_000},  # ações em milhares
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Análise de Demonstrações Financeiras")
    parser.add_argument("--json", help="arquivo JSON com as demonstrações (padrão: dados de exemplo)")
    parser.add_argument("--saida-txt", help="salva o relatório em arquivo de texto")
    parser.add_argument("--saida-json", help="salva o relatório estruturado em JSON")
    args = parser.parse_args()

    dados = DadosFinanceiros.from_json(args.json) if args.json else DadosFinanceiros.from_dict(DADOS_EXEMPLO)
    analisador = AnalisadorFinanceiro(dados)

    relatorio = analisador.formatar_relatorio()
    print(relatorio)

    if args.saida_txt:
        with open(args.saida_txt, "w", encoding="utf-8") as arquivo:
            arquivo.write(relatorio)
        print(f"\nRelatório de texto salvo em: {args.saida_txt}")
    if args.saida_json:
        analisador.exportar_json(args.saida_json)
        print(f"Relatório JSON salvo em: {args.saida_json}")


if __name__ == "__main__":
    main()
