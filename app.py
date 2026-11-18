#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py - Aplicação de Análise de Demonstrações Financeiras (ponto de entrada)
=============================================================================
CAD 167 – Administração Financeira (UFMG) – Trabalho 1

Arquitetura em 3 camadas (cada uma em um arquivo):
  - cvm_loader.py                          -> DADOS: captura as demonstrações reais da CVM
  - analise_demonstracoes_financeiras.py   -> CÁLCULO: indicadores financeiros por módulo
  - estrutura_capital.py                   -> CÁLCULO: WACC, alavancagem, EBIT-LPA e estrutura ótima
  - avaliacao_investimentos.py             -> CÁLCULO: VPL, TIR, paybacks de projetos
  - app.py (este arquivo)                  -> APLICAÇÃO: serviço (API p/ front-end) + linha de comando

COMO USAR (o mais simples): execute e siga o menu
    python app.py

Interface web (navegador):
    python servidor_web.py

Atalhos sem menu:
    python app.py --exemplo                              # dados fictícios (roda sem internet)
    python app.py --empresa "weg" --ano 2025             # dados reais da CVM
    python app.py --empresa "weg" --preco 45,30 --acoes 4.197.317.998
    python app.py --json meus_dados.json                 # dados de um arquivo JSON
    python app.py --empresa "weg" --zip dfp_cia_aberta_2025.zip   # usa .zip já baixado (offline)
    python app.py --exemplo --rf 11 --beta 1,2 --premio 5,5      # custo de capital (taxas em %)
    python app.py --exemplo --captacao 300.000 --taxa-divida 15 --preco-emissao 15   # EBIT-LPA
    python app.py --exemplo --projeto "1.000;500;400;300;100" --taxa-projeto 10      # projeto

Relatórios gerados em  relatorios/<empresa>/ :
    relatorio.txt   -> o mesmo relatório do console
    relatorio.html  -> versão para abrir no navegador
    relatorio.json  -> indicadores estruturados (pensado para integração com front-end)
    dados_entrada.json -> dados capturados (reutilizáveis com --json, sem novo download)

PARA O FRONT-END FUTURO: importe as funções da seção "API DE SERVIÇO" abaixo
(analisar_cvm, analisar_json, analisar_exemplo, buscar_empresas). Elas não imprimem nem pedem
dados: recebem parâmetros e devolvem `ResultadoAnalise`, que tem o método `para_dict()`
(JSON-serializável), ideal para uma API REST (Flask/FastAPI) ou interface web.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import re
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import avaliacao_investimentos as ai
import cvm_loader as cvm
import estrutura_capital as ec
from analise_demonstracoes_financeiras import (
    DADOS_EXEMPLO,
    AnalisadorFinanceiro,
    DadosFinanceiros,
    Indicador,
    _num_br,
    _valido,
    formatar_monetario_mil,
    formatar_valor,
)

PASTA_RELATORIOS_PADRAO = "relatorios"
LARGURA = 84
MODULO_ESTRUTURA = "4. ESTRUTURA DE CAPITAL E ALAVANCAGEM"
MODULO_WACC = "7. CUSTO DE CAPITAL (WACC)"


# ============================================================================
# API DE SERVIÇO (sem interação com o usuário - reutilizável por um front-end)
# ============================================================================
@dataclass
class ResultadoAnalise:
    """Resultado completo de uma análise: dados de entrada, indicadores, textos e avisos."""
    dados: DadosFinanceiros
    modulos: Dict[str, List[Indicador]]
    texto: str                                   # relatório formatado para console/arquivo
    fonte: str = ""
    avisos: List[str] = field(default_factory=list)
    arquivos: List[str] = field(default_factory=list)   # caminhos dos relatórios salvos
    estrutura_capital: Dict[str, Any] = field(default_factory=dict)   # meta do WACC, simulação, EBIT-LPA
    avaliacao_projeto: Optional[Dict[str, Any]] = None
    avisos_carga: List[str] = field(default_factory=list)  # avisos da captura (para refazer a análise)

    def para_dict(self) -> Dict:
        """Representação JSON-serializável (para APIs e front-ends)."""
        return {
            "empresa": self.dados.empresa,
            "periodo": self.dados.periodo,
            "fonte": self.fonte,
            "avisos": self.avisos,
            "dados_entrada": cvm.dados_para_dict(self.dados),
            "modulos": {
                nome: [{"nome": i.nome, "valor": i.valor, "valor_formatado": formatar_valor(i),
                        "unidade": i.unidade, "formula": i.formula, "motivo": i.motivo} for i in indicadores]
                for nome, indicadores in self.modulos.items()
            },
            "estrutura_capital": self.estrutura_capital,
            "avaliacao_projeto": self.avaliacao_projeto,
        }


def _sem_repetir(itens: Sequence[str]) -> List[str]:
    vistos: List[str] = []
    for item in itens:
        if item not in vistos:
            vistos.append(item)
    return vistos


def analisar_dados(dados: DadosFinanceiros, avisos: Optional[Sequence[str]] = None,
                   fonte: str = "", *, parametros: Any = None, captacao: Any = None,
                   projeto: Any = None) -> ResultadoAnalise:
    """Executa a análise sobre dados já carregados (qualquer origem).

    parametros: ParametrosMercado ou dict (frações), sobrepostos a dados.mercado.
    captacao:   CenarioCaptacao ou dict -> análise EBIT-LPA.
    projeto:    Projeto ou dict -> avaliação do projeto (taxa padrão: WACC).
    """
    avisos_carga = list(avisos or [])
    avisos_lista = list(avisos_carga)
    dados = ec.aplicar_parametros(dados, parametros, avisos_lista)
    analisador = AnalisadorFinanceiro(dados)
    modulos = dict(analisador.gerar_relatorio())

    indicadores_alav, avisos_alav = ec.endividamento_alavancagem(dados)
    modulos[MODULO_ESTRUTURA] = list(modulos[MODULO_ESTRUTURA]) + indicadores_alav
    indicadores_wacc, meta, avisos_wacc = ec.custo_capital(dados)
    modulos[MODULO_WACC] = indicadores_wacc
    avisos_lista += avisos_alav + avisos_wacc

    estrutura: Dict[str, Any] = {
        "custo_capital_meta": {k: meta[k] for k in ("base_pesos", "kd_utilizado", "origem_aliquota")},
        "simulacao": ec.simular_estrutura(dados),
        "ebit_lpa": ec.analise_ebit_lpa(dados, ec.CenarioCaptacao.de(captacao)) if captacao is not None else None,
    }
    avaliacao = None
    if projeto is not None:
        avaliacao = ai.avaliar_projeto(ai.Projeto.de(projeto), meta["wacc"], meta["motivo_wacc"])

    res = ResultadoAnalise(dados=dados, modulos=modulos, texto="", fonte=fonte,
                           avisos=_sem_repetir(avisos_lista), estrutura_capital=estrutura,
                           avaliacao_projeto=avaliacao, avisos_carga=avisos_carga)
    texto = analisador.formatar_relatorio(modulos, _secoes_texto(res), _notas_modulos(res, meta))
    if fonte:
        texto += f"\nFonte dos dados: {fonte}"
    if res.avisos:
        texto += "\n\nAvisos sobre os dados:\n" + "\n".join(f"  - {a}" for a in res.avisos)
    res.texto = texto
    return res


def refazer_analise(res: ResultadoAnalise, *, captacao: Any = None, projeto: Any = None) -> ResultadoAnalise:
    """Refaz a análise com os mesmos dados (já com os parâmetros de mercado) e um novo cenário/projeto."""
    return analisar_dados(res.dados, res.avisos_carga, res.fonte, captacao=captacao, projeto=projeto)


def analisar_exemplo(*, parametros: Any = None, captacao: Any = None, projeto: Any = None) -> ResultadoAnalise:
    """Análise com os dados fictícios embutidos (funciona sem internet)."""
    return analisar_dados(DadosFinanceiros.from_dict(DADOS_EXEMPLO), fonte="dados fictícios de exemplo",
                          parametros=parametros, captacao=captacao, projeto=projeto)


def analisar_json(caminho: Union[str, Path], *, parametros: Any = None, captacao: Any = None,
                  projeto: Any = None) -> ResultadoAnalise:
    """Análise de um arquivo JSON no formato de `dados_entrada.json`."""
    try:
        dados = DadosFinanceiros.from_json(str(caminho))
    except FileNotFoundError as erro:
        raise cvm.ErroCVM(f"Arquivo não encontrado: {caminho}") from erro
    except (json.JSONDecodeError, TypeError) as erro:
        raise cvm.ErroCVM(f"O arquivo {caminho} não é um JSON válido de demonstrações ({erro}).") from erro
    return analisar_dados(dados, fonte=f"arquivo {caminho}", parametros=parametros, captacao=captacao,
                          projeto=projeto)


def analisar_cvm(
    empresa: Union[cvm.EmpresaCVM, str],
    ano: Optional[int] = None,
    consolidado: bool = True,
    preco_acao: Optional[float] = None,
    numero_acoes: Optional[float] = None,
    caminho_zip: Optional[Union[str, Path]] = None,
    progresso: Optional[cvm.Progresso] = None,
    *,
    parametros: Any = None,
    captacao: Any = None,
    projeto: Any = None,
) -> ResultadoAnalise:
    """Captura os dados da CVM e executa a análise (veja `cvm.carregar_dados` para os parâmetros)."""
    carga = cvm.carregar_dados(empresa, ano or cvm.ano_padrao(), consolidado=consolidado,
                               preco_acao=preco_acao, numero_acoes=numero_acoes,
                               caminho_zip=caminho_zip, progresso=progresso)
    return analisar_dados(carga.dados, carga.avisos, carga.fonte, parametros=parametros,
                          captacao=captacao, projeto=projeto)


# ----------------------------------------------------------------------------
# Seções novas do relatório (texto)
# ----------------------------------------------------------------------------
def _pct(v: Optional[float], casas: int = 2) -> str:
    return f"{_num(v * 100, casas)}%" if _valido(v) else "n/d"


def _mil(v: Optional[float]) -> str:
    return formatar_monetario_mil(v) if _valido(v) else "n/d"


def _num(v: Optional[float], casas: int = 2) -> str:
    """Número no formato brasileiro, arredondando meio para cima (1,485 -> 1,49 apesar do ponto flutuante)."""
    if not _valido(v):
        return "n/d"
    return _num_br(v + math.copysign(abs(v) * 1e-12, v), casas)


def _quebrar(texto: str, recuo: str = "    ") -> List[str]:
    return textwrap.wrap(texto, LARGURA, initial_indent=recuo + "- ", subsequent_indent=recuo + "  ")


def _notas_modulos(res: ResultadoAnalise, meta: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """Linhas de observação exibidas abaixo dos módulos 4 e 7."""
    notas: Dict[str, List[str]] = {}
    ant = res.dados.exercicio_anterior
    if ant is not None:
        dre = res.dados.dre
        notas[MODULO_ESTRUTURA] = [
            "Exercícios comparados (atual × anterior, R$ mil):",
            f"  Vendas {_num(dre.vendas, 0)} × {_num(ant.vendas, 0)}; EBIT {_num(dre.ebit_calc, 0)} × "
            f"{_num(ant.ebit, 0)}; Lucro líquido {_num(dre.lucro_liquido_calc, 0)} × {_num(ant.lucro_liquido, 0)}.",
        ]
    meta = meta or res.estrutura_capital.get("custo_capital_meta") or {}
    if meta:
        notas[MODULO_WACC] = [f"Pesos a valor {'de mercado' if meta['base_pesos'] == 'mercado' else 'contábil'}; "
                              f"Kd {meta['kd_utilizado']}; alíquota {meta['origem_aliquota']}."]
    return notas


def _texto_simulacao(sim: Optional[Dict[str, Any]]) -> str:
    titulo = ["SIMULAÇÃO DA ESTRUTURA DE CAPITAL ÓTIMA", "-" * LARGURA]
    if not sim:
        return ""
    if "faltando" in sim:
        return "\n".join(titulo + [f"  Simulação indisponível: faltam {', '.join(sim['faltando'])}."])
    pontos = sim["pontos"]
    atual_dv = sim["atual"]["dv"]
    mais_proximo = min(range(len(pontos)), key=lambda i: abs(pontos[i]["dv"] - atual_dv)) if _valido(atual_dv) else None
    linhas = titulo + [
        f"  Beta desalavancado (Hamada): {_num(sim['beta_desalavancado'], 4)}   "
        f"Alíquota: {_pct(sim['aliquota'])}   Pesos a valor "
        f"{'de mercado' if sim['base_pesos'] == 'mercado' else 'contábil'}",
        "",
        f"  {'D/V':>5}{'Beta':>9}{'Ke':>10}{'Cobertura':>12}{'Rating':>9}{'Kd':>10}{'WACC':>10}",
    ]
    for i, p in enumerate(pontos):
        marca = []
        if p["dv"] == sim["otimo"]["dv"]:
            marca.append("◄ ótimo")
        if i == mais_proximo:
            marca.append("• atual")
        cobertura = f"{_num(p['cobertura'])}x" if p["cobertura"] is not None else "—"
        kd = _pct(p["kd"]) if p["kd"] is not None else "—"
        linhas.append(f"  {_pct(p['dv'], 0):>5}{_num(p['beta']):>9}{_pct(p['ke']):>10}{cobertura:>12}"
                      f"{p['rating']:>9}{kd:>10}{_pct(p['wacc']):>10}  {' '.join(marca)}".rstrip())
    mm = sim["modigliani_miller"]
    linhas += [
        "",
        f"  Ótimo: D/V = {_pct(sim['otimo']['dv'], 0)}, WACC de {_pct(sim['otimo']['wacc'])}. "
        f"Atual: D/V = {_pct(atual_dv)}, WACC calculado de {_pct(sim['atual']['wacc_calculado'])}.",
        "",
        "  Modigliani-Miller com impostos (dívida perpétua):",
        f"    {'Valor da empresa alavancada (VL = D + E)':<52}{_mil(mm['valor_alavancado'])}",
        f"    {'Benefício fiscal da dívida (t × D)':<52}{_mil(mm['beneficio_fiscal'])}",
        f"    {'Valor da empresa não alavancada (VU = VL − t × D)':<52}{_mil(mm['valor_desalavancado'])}",
        "",
        "  Premissas:",
    ]
    for premissa in sim["premissas"]:
        linhas += _quebrar(premissa)
    return "\n".join(linhas)


def _texto_ebit_lpa(r: Optional[Dict[str, Any]]) -> str:
    if r is None:
        return ""
    linhas = ["ANÁLISE EBIT-LPA", "-" * LARGURA]
    if "motivo" in r:
        return "\n".join(linhas + [f"  Análise indisponível: {r['motivo']}."])
    linhas += [
        f"  Captação de R$ {_num(r['valor'], 0)} mil: dívida a {_pct(r['taxa_divida'])} a.a. ou emissão de "
        f"{_num(r['novas_acoes'], 0)} mil ações a R$ {_num(r['preco_emissao'])}",
        "",
        f"  {'Alternativa':<14}{'Juros (R$ mil)':>18}{'Ações (mil)':>16}{'LPA no EBIT avaliado':>24}",
    ]
    for a in r["alternativas"]:
        linhas.append(f"  {a['nome']:<14}{_num(a['juros'], 0):>18}{_num(a['acoes'], 0):>16}"
                      f"{'R$ ' + _num(a['lpa_no_ebit']):>24}")
    linhas += ["", f"  EBIT avaliado ({r['origem_ebit']}): {_mil(r['ebit_avaliado'])}   "
                   f"Alíquota: {_pct(r['aliquota'])}"]
    if r["ebit_indiferenca"] is not None:
        linhas.append(f"  EBIT de indiferença: {_mil(r['ebit_indiferenca'])}   "
                      f"LPA de indiferença: R$ {_num(r['lpa_indiferenca'])}")
        linhas.append("  Acima do EBIT de indiferença, a dívida dá o maior LPA; abaixo dele, as ações.")
    else:
        linhas.append(f"  Sem ponto de indiferença (retas paralelas): a alternativa \"{r['dominante']}\" "
                      "domina em qualquer EBIT.")
    melhor = r["melhor_no_ebit"]
    linhas.append("  No EBIT avaliado as duas alternativas empatam." if melhor == "Empate"
                  else f"  No EBIT avaliado, a alternativa com maior LPA é: {melhor}.")
    for aviso in r.get("avisos", []):
        linhas += _quebrar(aviso, "  ")
    return "\n".join(linhas)


_RECOMENDACOES = {"aceitar": "ACEITAR (VPL > 0)", "rejeitar": "REJEITAR (VPL < 0)",
                  "indiferente": "INDIFERENTE (VPL = 0)"}


def _anos(v: Optional[float]) -> str:
    return f"{_num(v)} anos" if v is not None else "não recuperado no horizonte"


def _texto_projeto(r: Optional[Dict[str, Any]]) -> str:
    if r is None:
        return ""
    tir = _pct(r["tir"]) if r["tir"] is not None else f"n/d ({r['motivo_tir']})"
    il = f"{_num(r['indice_lucratividade'])}x" if r["indice_lucratividade"] is not None else "n/d"
    linhas = [
        "AVALIAÇÃO DE PROJETO DE INVESTIMENTO", "-" * LARGURA,
        f"  {'Taxa de desconto':<32}{_pct(r['taxa'])} ({r['origem_taxa']})",
        f"  {'VPL':<32}R$ {_num(r['vpl'])} mil",
        f"  {'TIR':<32}{tir}",
        f"  {'Payback simples':<32}{_anos(r['payback_simples'])}",
        f"  {'Payback descontado':<32}{_anos(r['payback_descontado'])}",
        f"  {'Índice de lucratividade':<32}{il}",
        f"  {'Recomendação':<32}{_RECOMENDACOES[r['recomendacao']]}",
    ]
    for aviso in r["avisos"]:
        linhas += _quebrar(aviso, "  ")
    linhas += ["", f"  {'Ano':>4}{'Fluxo':>16}{'Descontado':>16}{'Acumulado':>16}{'Acum. descontado':>20}"]
    for t in r["tabela"]:
        linhas.append(f"  {t['ano']:>4}{_num(t['fluxo']):>16}{_num(t['fluxo_descontado']):>16}"
                      f"{_num(t['acumulado']):>16}{_num(t['acumulado_descontado']):>20}")
    linhas.append("  (valores em R$ mil)")
    return "\n".join(linhas)


def _secoes_texto(res: ResultadoAnalise) -> List[str]:
    secoes = [_texto_simulacao(res.estrutura_capital.get("simulacao")),
              _texto_ebit_lpa(res.estrutura_capital.get("ebit_lpa")),
              _texto_projeto(res.avaliacao_projeto)]
    return [s for s in secoes if s]

def buscar_empresas(termo: str, ano: Optional[int] = None, caminho_zip: Optional[Union[str, Path]] = None,
                    progresso: Optional[cvm.Progresso] = None) -> List[cvm.EmpresaCVM]:
    """Busca empresas por nome/CNPJ (baixa o arquivo da CVM se necessário)."""
    caminho = Path(caminho_zip) if caminho_zip else cvm.obter_zip_dfp(ano or cvm.ano_padrao(), progresso=progresso)
    return cvm.buscar_empresas(termo, caminho)


# ----------------------------------------------------------------------------
# Geração de relatórios em arquivo
# ----------------------------------------------------------------------------
def _slug(texto: str) -> str:
    """'Empresa Teste S.A.' -> 'empresa_teste_s_a' (nome seguro para pasta)."""
    return re.sub(r"[^a-z0-9]+", "_", cvm.normalizar(texto)).strip("_") or "empresa"


def _html_tabela(cabecalho: Sequence[str], linhas: Sequence[Sequence[str]], destaques: Sequence[bool] = ()) -> str:
    e = html.escape
    partes = ["<table class='grade'><tr>" + "".join(f"<th>{e(c)}</th>" for c in cabecalho) + "</tr>"]
    for i, linha in enumerate(linhas):
        classe = " class='destaque'" if i < len(destaques) and destaques[i] else ""
        partes.append(f"<tr{classe}>" + "".join(f"<td>{e(c)}</td>" for c in linha) + "</tr>")
    return "".join(partes) + "</table>"


def _html_simulacao(sim: Optional[Dict[str, Any]]) -> str:
    e = html.escape
    if not sim:
        return ""
    partes = ["<h2>SIMULAÇÃO DA ESTRUTURA DE CAPITAL ÓTIMA</h2>"]
    if "faltando" in sim:
        return partes[0] + f"<p>Simulação indisponível: faltam {e(', '.join(sim['faltando']))}.</p>"
    pontos, otimo = sim["pontos"], sim["otimo"]
    atual_dv = sim["atual"]["dv"]
    proximo = min(range(len(pontos)), key=lambda i: abs(pontos[i]["dv"] - atual_dv)) if _valido(atual_dv) else None
    linhas = []
    for i, p in enumerate(pontos):
        marca = " ".join(m for m, ok in (("◄ ótimo", p["dv"] == otimo["dv"]), ("• atual", i == proximo)) if ok)
        linhas.append([_pct(p["dv"], 0), _num(p["beta"]), _pct(p["ke"]),
                       f"{_num(p['cobertura'])}x" if p["cobertura"] is not None else "—", p["rating"],
                       _pct(p["kd"]) if p["kd"] is not None else "—", _pct(p["wacc"]), marca])
    mm = sim["modigliani_miller"]
    partes += [
        f"<p>Beta desalavancado (Hamada): <b>{_num(sim['beta_desalavancado'], 4)}</b> &middot; alíquota "
        f"{_pct(sim['aliquota'])} &middot; ótimo em D/V = <b>{_pct(otimo['dv'], 0)}</b> com WACC de "
        f"<b>{_pct(otimo['wacc'])}</b> &middot; atual: D/V = {_pct(atual_dv)}, WACC calculado de "
        f"{_pct(sim['atual']['wacc_calculado'])}.</p>",
        _html_tabela(["D/V", "Beta", "Ke", "Cobertura", "Rating", "Kd", "WACC", ""], linhas,
                     [p["dv"] == otimo["dv"] for p in pontos]),
        "<h3>Modigliani-Miller com impostos (dívida perpétua)</h3>",
        _html_tabela(["Item", "Valor"], [["Valor da empresa alavancada (VL = D + E)", _mil(mm["valor_alavancado"])],
                                          ["Benefício fiscal da dívida (t × D)", _mil(mm["beneficio_fiscal"])],
                                          ["Valor da empresa não alavancada (VU = VL − t × D)",
                                           _mil(mm["valor_desalavancado"])]]),
        "<h3>Premissas</h3><ul>" + "".join(f"<li>{e(p)}</li>" for p in sim["premissas"]) + "</ul>",
    ]
    return "".join(partes)


def _html_ebit_lpa(r: Optional[Dict[str, Any]]) -> str:
    e = html.escape
    if r is None:
        return ""
    partes = ["<h2>ANÁLISE EBIT-LPA</h2>"]
    if "motivo" in r:
        return partes[0] + f"<p>Análise indisponível: {e(r['motivo'])}.</p>"
    partes.append(f"<p>Captação de {e(_mil(r['valor']))}: dívida a {_pct(r['taxa_divida'])} a.a. ou emissão de "
                  f"{_num(r['novas_acoes'], 0)} mil ações a R$ {_num(r['preco_emissao'])}. EBIT avaliado "
                  f"({e(r['origem_ebit'])}): {e(_mil(r['ebit_avaliado']))}; alíquota {_pct(r['aliquota'])}.</p>")
    partes.append(_html_tabela(["Alternativa", "Juros (R$ mil)", "Ações (mil)", "LPA no EBIT avaliado"],
                               [[a["nome"], _num(a["juros"], 0), _num(a["acoes"], 0), f"R$ {_num(a['lpa_no_ebit'])}"]
                                for a in r["alternativas"]],
                               [a["nome"] == r["melhor_no_ebit"] for a in r["alternativas"]]))
    if r["ebit_indiferenca"] is not None:
        partes.append(f"<p>EBIT de indiferença: <b>{e(_mil(r['ebit_indiferenca']))}</b> &middot; LPA de "
                      f"indiferença: <b>R$ {_num(r['lpa_indiferenca'])}</b>. Acima desse EBIT a dívida dá o maior LPA; "
                      "abaixo, as ações.</p>")
    else:
        partes.append(f"<p>Sem ponto de indiferença: a alternativa “{e(r['dominante'])}” domina em qualquer EBIT.</p>")
    partes.append(f"<p>Maior LPA no EBIT avaliado: <b>{e(r['melhor_no_ebit'])}</b>.</p>")
    partes += [f"<div class='aviso'>{e(a)}</div>" for a in r.get("avisos", [])]
    return "".join(partes)


def _html_projeto(r: Optional[Dict[str, Any]]) -> str:
    e = html.escape
    if r is None:
        return ""
    tir = _pct(r["tir"]) if r["tir"] is not None else f"n/d ({r['motivo_tir']})"
    il = f"{_num(r['indice_lucratividade'])}x" if r["indice_lucratividade"] is not None else "n/d"
    partes = [
        "<h2>AVALIAÇÃO DE PROJETO DE INVESTIMENTO</h2>",
        _html_tabela(["Métrica", "Valor"], [
            ["Taxa de desconto", f"{_pct(r['taxa'])} ({r['origem_taxa']})"], ["VPL", f"R$ {_num(r['vpl'])} mil"],
            ["TIR", tir], ["Payback simples", _anos(r["payback_simples"])],
            ["Payback descontado", _anos(r["payback_descontado"])], ["Índice de lucratividade", il],
            ["Recomendação", _RECOMENDACOES[r["recomendacao"]]]]),
    ]
    partes += [f"<div class='aviso'>{e(a)}</div>" for a in r["avisos"]]
    partes.append("<h3>Fluxos ano a ano (R$ mil)</h3>")
    partes.append(_html_tabela(["Ano", "Fluxo", "Descontado", "Acumulado", "Acumulado descontado"],
                               [[str(t["ano"]), _num(t["fluxo"]), _num(t["fluxo_descontado"]), _num(t["acumulado"]),
                                 _num(t["acumulado_descontado"])] for t in r["tabela"]]))
    return "".join(partes)


def _secoes_html(res: ResultadoAnalise) -> List[str]:
    secoes = [_html_simulacao(res.estrutura_capital.get("simulacao")),
              _html_ebit_lpa(res.estrutura_capital.get("ebit_lpa")),
              _html_projeto(res.avaliacao_projeto)]
    return [s for s in secoes if s]


def _gerar_html(res: ResultadoAnalise, secoes_extras: Optional[List[str]] = None) -> str:
    """Relatório em HTML autônomo (abre em qualquer navegador, sem internet).

    secoes_extras: blocos HTML inseridos antes dos avisos (padrão: simulação, EBIT-LPA e projeto).
    """
    e = html.escape
    partes = [
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
        f"<title>Análise financeira - {e(res.dados.empresa)}</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222}"
        "h1{margin-bottom:0}h2{background:#1f3a5f;color:#fff;padding:.4rem .7rem;font-size:1.05rem;margin-top:2rem}"
        "h3{font-size:.95rem;margin:1.2rem 0 .4rem}"
        "table{width:100%;border-collapse:collapse}td,th{padding:.35rem .6rem;border-bottom:1px solid #ddd}"
        "th{text-align:left;font-size:.85rem;color:#555}table.grade td{font-variant-numeric:tabular-nums}"
        "tr.destaque td{background:#e7eef8;font-weight:600}"
        "td.v{text-align:right;font-weight:600;white-space:nowrap}td.f{color:#666;font-size:.9rem}"
        "td.v small{display:block;font-weight:400;color:#9a6b00;white-space:normal}"
        "p.nota{color:#555;font-size:.88rem;margin:.4rem .6rem}"
        ".aviso{background:#fff4d6;border-left:4px solid #e0a800;padding:.5rem .8rem;margin:.4rem 0}"
        "small{color:#666}</style></head><body>",
        f"<h1>{e(res.dados.empresa)}</h1><p>{e(res.dados.periodo)}<br>",
        f"<small>{e(res.fonte)} &middot; valores monetários em R$ mil</small></p>",
    ]
    notas = _notas_modulos(res)
    for modulo, indicadores in res.modulos.items():
        partes.append(f"<h2>{e(modulo)}</h2><table>")
        for ind in indicadores:
            motivo = f"<small>{e(ind.motivo)}</small>" if not _valido(ind.valor) and ind.motivo else ""
            partes.append(f"<tr><td>{e(ind.nome)}</td><td class='v'>{e(formatar_valor(ind))}{motivo}</td>"
                          f"<td class='f'>{e(ind.formula)}</td></tr>")
        partes.append("</table>")
        partes += [f"<p class='nota'>{e(n.strip())}</p>" for n in notas.get(modulo, [])]
    partes += secoes_extras if secoes_extras is not None else _secoes_html(res)
    if res.avisos:
        partes.append("<h2>Avisos sobre os dados</h2>")
        partes += [f"<div class='aviso'>{e(a)}</div>" for a in res.avisos]
    partes.append("<p><small>n/d = não disponível (dado ausente ou divisão por zero).</small></p></body></html>")
    return "".join(partes)


def salvar_relatorios(res: ResultadoAnalise, pasta_base: Union[str, Path] = PASTA_RELATORIOS_PADRAO) -> List[str]:
    """Grava relatório (.txt, .html, .json) e os dados de entrada em `pasta_base/<empresa>/`."""
    pasta = Path(pasta_base) / _slug(res.dados.empresa)
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "relatorio.txt").write_text(res.texto, encoding="utf-8")
    (pasta / "relatorio.html").write_text(_gerar_html(res), encoding="utf-8")
    (pasta / "relatorio.json").write_text(json.dumps(res.para_dict(), ensure_ascii=False, indent=2),
                                          encoding="utf-8")
    cvm.salvar_dados_json(res.dados, pasta / "dados_entrada.json")
    res.arquivos = [str(pasta / nome) for nome in
                    ("relatorio.txt", "relatorio.html", "relatorio.json", "dados_entrada.json")]
    return res.arquivos


# ============================================================================
# INTERFACE DE LINHA DE COMANDO (menu interativo + atalhos)
# ============================================================================
def _progresso_console(baixado: int, total: Optional[int]) -> None:
    """Mostra o andamento do download no console."""
    mb = baixado / 1e6
    if total:
        print(f"\r  Baixando da CVM... {mb:.1f} de {total / 1e6:.1f} MB ({baixado * 100 // total}%)",
              end="", flush=True)
    else:
        print(f"\r  Baixando da CVM... {mb:.1f} MB", end="", flush=True)


def _perguntar(texto: str, padrao: str = "") -> str:
    """Faz uma pergunta; Enter aceita o valor padrão (mostrado entre colchetes)."""
    resposta = input(f"{texto}" + (f" [{padrao}]" if padrao else "") + ": ").strip()
    return resposta or padrao


def _perguntar_numero(texto: str) -> Optional[float]:
    """Pergunta um número (formato brasileiro ou não); Enter = pular (None)."""
    while True:
        resposta = input(f"{texto} (Enter para pular): ").strip()
        if not resposta:
            return None
        try:
            return cvm.ler_numero_br(resposta)
        except ValueError:
            print("  Número inválido. Exemplos: 45,30  ou  4.197.317.998")


def _perguntar_sim(texto: str, padrao: str = "n") -> bool:
    return _perguntar(f"{texto} (s/n)", padrao).lower().startswith("s")


def _perguntar_taxa(texto: str) -> Optional[float]:
    """Taxa digitada em percentual ("13,75"), devolvida em fração; Enter = não informada."""
    valor = _perguntar_numero(f"{texto} em % (ex.: 13,75)")
    return None if valor is None else valor / 100


def _perguntar_parametros() -> Optional[ec.ParametrosMercado]:
    """Pergunta opcional pelos parâmetros de mercado do custo de capital."""
    if not _perguntar_sim("\nInformar parâmetros de mercado (Rf, beta, prêmio, Kd)?"):
        return None
    print("Taxas em % ao ano. Deixe em branco o que não quiser informar.")
    return ec.ParametrosMercado(
        taxa_livre_risco=_perguntar_taxa("Taxa livre de risco (Rf)"),
        beta=_perguntar_numero("Beta alavancado (ex.: 1,2)"),
        premio_risco_mercado=_perguntar_taxa("Prêmio de risco de mercado"),
        custo_divida=_perguntar_taxa("Custo da dívida Kd (substitui o Kd contábil)"),
    )


def _ler_fluxos(texto: str) -> List[float]:
    """'500;400;300;100' -> [500, 400, 300, 100] (separador ';', pois a vírgula é decimal)."""
    fluxos = []
    for ano, parte in enumerate((p.strip() for p in texto.split(";")), 1):
        if not parte:
            continue
        try:
            fluxos.append(cvm.ler_numero_br(parte))
        except ValueError:
            raise ValueError(f"Fluxo do ano {ano} inválido: {parte!r}.") from None
    return fluxos


def _perguntar_projeto(taxa_obrigatoria: bool) -> Optional[Dict[str, Any]]:
    """Lê investimento, fluxos e taxa do projeto. None se o usuário desistir."""
    investimento = _perguntar_numero("Investimento inicial em R$ mil (ex.: 1.000)")
    if investimento is None:
        return None
    fluxos = _ler_fluxos(_perguntar("Fluxos anuais em R$ mil, separados por ';' (ex.: 500;400;300;100)"))
    rotulo = "Taxa de desconto" if taxa_obrigatoria else "Taxa de desconto (Enter = usar o WACC)"
    while True:
        taxa = _perguntar_taxa(rotulo)
        if taxa is not None or not taxa_obrigatoria:
            break
        print("  A taxa de desconto é obrigatória aqui.")
    return {"investimento_inicial": investimento, "fluxos": fluxos, "taxa": taxa}


def _salvar_e_avisar(res: ResultadoAnalise, pasta: str) -> None:
    arquivos = salvar_relatorios(res, pasta)
    print(f"Relatórios atualizados em {Path(arquivos[0]).parent}")


def _simulacoes_interativas(res: ResultadoAnalise, pasta: str) -> None:
    """Depois do relatório: oferece a análise EBIT-LPA e a avaliação de projeto."""
    captacao = projeto = None
    while True:
        try:
            if _perguntar_sim("Simular captação (EBIT-LPA)?"):
                valor = _perguntar_numero("Valor a captar em R$ mil (ex.: 300.000)")
                taxa = _perguntar_taxa("Taxa da nova dívida")
                preco = _perguntar_numero("Preço de emissão das novas ações em R$ (ex.: 15,00)")
                ebit = _perguntar_numero("EBIT projetado em R$ mil (Enter = EBIT atual)")
                captacao = ec.CenarioCaptacao(valor, taxa, preco, ebit)
                res = refazer_analise(res, captacao=captacao, projeto=projeto)
                print("\n" + _texto_ebit_lpa(res.estrutura_capital["ebit_lpa"]) + "\n")
                _salvar_e_avisar(res, pasta)
                continue
            if _perguntar_sim("Avaliar um projeto de investimento?"):
                projeto = _perguntar_projeto(taxa_obrigatoria=False)
                if projeto is None:
                    continue
                res = refazer_analise(res, captacao=captacao, projeto=projeto)
                print("\n" + _texto_projeto(res.avaliacao_projeto) + "\n")
                _salvar_e_avisar(res, pasta)
                continue
            return
        except (TypeError, ValueError) as erro:
            print(f"\nErro: {erro if isinstance(erro, ValueError) else 'campo obrigatório não informado.'}\n")


def _mostrar_resultado(res: ResultadoAnalise, salvar: bool, pasta: str) -> None:
    """Imprime o relatório e, opcionalmente, salva os arquivos."""
    print("\n" + res.texto + "\n")
    if salvar:
        arquivos = salvar_relatorios(res, pasta)
        print("Relatórios salvos em:")
        for caminho in arquivos:
            print(f"  - {caminho}")
        print(f"Dica: abra {arquivos[1]} no navegador para ver a versão visual.\n")


def _mostrar_e_simular(res: ResultadoAnalise, pasta: str) -> None:
    _mostrar_resultado(res, salvar=True, pasta=pasta)
    _simulacoes_interativas(res, pasta)


def _fluxo_cvm_interativo(pasta: str) -> None:
    """Passo a passo guiado: escolher ano, empresa, preço/ações e gerar a análise."""
    print("\n--- Dados reais da CVM ---")
    try:
        ano = int(_perguntar("Ano do exercício", str(cvm.ano_padrao())))
    except ValueError:
        print("Ano inválido.")
        return
    caminho_zip = _perguntar("Caminho de um .zip da DFP já baixado (Enter para baixar automaticamente)") or None
    try:
        if not caminho_zip:
            caminho = cvm.obter_zip_dfp(ano, progresso=_progresso_console)
            print()
        else:
            caminho = Path(caminho_zip)
        while True:
            termo = _perguntar("Nome ou CNPJ da empresa (ex.: weg, vale, magazine luiza)")
            if not termo:
                return
            achadas = cvm.buscar_empresas(termo, caminho, limite=15)
            if not achadas:
                print("  Nenhuma empresa encontrada. Tente outra parte do nome.")
                continue
            if len(achadas) == 1:
                empresa = achadas[0]
            else:
                print("\nEmpresas encontradas:")
                for i, emp in enumerate(achadas, 1):
                    print(f"  {i:>2}. {emp.nome}  (CNPJ {emp.cnpj})")
                escolha = _perguntar("Número da empresa (Enter para buscar de novo)")
                if not escolha.isdigit() or not 1 <= int(escolha) <= len(achadas):
                    continue
                empresa = achadas[int(escolha) - 1]
            break
        print(f"\nEmpresa selecionada: {empresa.nome}")
        consolidado = _perguntar("Usar demonstrações consolidadas? (s/n)", "s").lower().startswith("s")
        print("\nO número de ações vem da CVM, mas o preço da ação não. Informe o preço para calcular")
        print("P/L, Market-to-Book, Valor de Mercado, EV e os pesos do WACC a valor de mercado.")
        preco = _perguntar_numero("Preço da ação em R$ (ex.: 45,30)")
        acoes = _perguntar_numero("Número de ações, para substituir o da CVM (ex.: 4.197.317.998)") if preco is not None else None
        parametros = _perguntar_parametros()
        resultado = analisar_cvm(empresa, ano, consolidado, preco, acoes, caminho_zip=caminho,
                                 parametros=parametros)
        _mostrar_e_simular(resultado, pasta)
    except cvm.ErroCVM as erro:
        print(f"\nErro: {erro}\n")


def _fluxo_projeto_interativo() -> None:
    """Opção 4 do menu: avalia um projeto sem empresa associada (taxa obrigatória)."""
    print("\n--- Avaliação de projeto de investimento (valores em R$ mil) ---")
    projeto = _perguntar_projeto(taxa_obrigatoria=True)
    if projeto is not None:
        print("\n" + _texto_projeto(ai.avaliar_projeto(ai.Projeto.de(projeto), None)) + "\n")


def _menu_interativo(pasta: str) -> None:
    """Menu principal."""
    while True:
        print("=" * 60)
        print(" ANÁLISE DE DEMONSTRAÇÕES FINANCEIRAS - CAD 167".center(60))
        print("=" * 60)
        print("  1. Analisar uma empresa real (dados da CVM)")
        print("  2. Analisar um arquivo JSON de dados")
        print("  3. Executar com dados fictícios de exemplo")
        print("  4. Avaliar projeto de investimento (VPL, TIR)")
        print("  0. Sair")
        opcao = input("Escolha uma opção: ").strip()
        try:
            if opcao == "1":
                _fluxo_cvm_interativo(pasta)
            elif opcao == "2":
                caminho = _perguntar("Caminho do arquivo JSON", "dados.json")
                _mostrar_e_simular(analisar_json(caminho, parametros=_perguntar_parametros()), pasta)
            elif opcao == "3":
                print("Os dados de exemplo já trazem Rf = 11%, beta = 1,2 e prêmio = 5,5%.")
                _mostrar_e_simular(analisar_exemplo(parametros=_perguntar_parametros()), pasta)
            elif opcao == "4":
                _fluxo_projeto_interativo()
            elif opcao == "0":
                print("Até logo!")
                return
            else:
                print("Opção inválida.\n")
        except (cvm.ErroCVM, ValueError) as erro:
            print(f"\nErro: {erro}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrado.")
            return


def _taxa_cli(texto: Optional[str], opcao: str) -> Optional[float]:
    """Taxa em percentual na linha de comando ("13,75") -> fração."""
    return None if texto is None else _numero_cli(texto, opcao) / 100


def _numero_cli(texto: str, opcao: str) -> float:
    try:
        return cvm.ler_numero_br(texto)
    except ValueError:
        raise ValueError(f"{opcao} inválido: {texto!r}.") from None


EXEMPLOS_CLI = """exemplos:
  python app.py --exemplo
  python app.py --empresa "weg" --preco 45,30 --rf 13,75 --beta 1,1 --premio 6
  python app.py --empresa "embraer" --preco 70 --rf 13,75 --beta 1 --premio 6 --kd 14
  python app.py --exemplo --captacao 300.000 --taxa-divida 15 --preco-emissao 15
  python app.py --exemplo --projeto "1.000;500;400;300;100" --taxa-projeto 10

Taxas (--rf, --premio, --kd, --taxa-divida, --taxa-projeto) em % ao ano; valores em R$ mil."""


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Ponto de entrada. Sem argumentos abre o menu; com argumentos executa direto."""
    # Garante acentuação correta no console do Windows
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Análise de Demonstrações Financeiras (sem argumentos: abre o menu interativo).",
        epilog=EXEMPLOS_CLI, formatter_class=argparse.RawDescriptionHelpFormatter)
    origem = parser.add_mutually_exclusive_group()
    origem.add_argument("--exemplo", action="store_true", help="usa os dados fictícios de exemplo")
    origem.add_argument("--json", metavar="ARQUIVO", help="analisa um arquivo JSON de dados")
    origem.add_argument("--empresa", metavar="NOME_OU_CNPJ", help="analisa uma empresa da CVM")
    parser.add_argument("--ano", type=int, help="ano do exercício (padrão: ano anterior)")
    parser.add_argument("--individual", action="store_true", help="usa demonstrações individuais em vez de consolidadas")
    parser.add_argument("--preco", help="preço da ação em R$ (ex.: 45,30)")
    parser.add_argument("--acoes", help="número de ações (padrão: o informado à CVM; ex.: 4.197.317.998)")
    parser.add_argument("--zip", metavar="ARQUIVO", help="usa um .zip da DFP já baixado (modo offline)")
    parser.add_argument("--pasta-saida", default=PASTA_RELATORIOS_PADRAO, help="pasta dos relatórios")
    parser.add_argument("--nao-salvar", action="store_true", help="apenas imprime, sem gerar arquivos")
    custo = parser.add_argument_group("custo de capital (WACC)")
    custo.add_argument("--rf", help="taxa livre de risco em %% (ex.: 13,75)")
    custo.add_argument("--beta", help="beta alavancado atual (ex.: 1,2)")
    custo.add_argument("--premio", help="prêmio de risco de mercado em %% (ex.: 5,5)")
    custo.add_argument("--kd", help="custo da dívida em %%; substitui o Kd contábil no WACC")
    captacao = parser.add_argument_group("análise EBIT-LPA (dívida × ações)")
    captacao.add_argument("--captacao", help="valor a captar em R$ mil (ex.: 300.000)")
    captacao.add_argument("--taxa-divida", help="taxa da nova dívida em %%")
    captacao.add_argument("--preco-emissao", help="preço de emissão das novas ações em R$")
    captacao.add_argument("--ebit-projetado", help="EBIT de avaliação em R$ mil (padrão: EBIT atual)")
    projeto_args = parser.add_argument_group("avaliação de projeto de investimento")
    projeto_args.add_argument("--projeto", metavar="\"INV;F1;F2;...\"",
                              help="investimento inicial e fluxos anuais em R$ mil, separados por ';'")
    projeto_args.add_argument("--taxa-projeto", help="taxa de desconto em %% (padrão: WACC)")
    args = parser.parse_args(argv)

    if not (args.exemplo or args.json or args.empresa):
        _menu_interativo(args.pasta_saida)
        return 0

    try:
        parametros = ec.ParametrosMercado(
            taxa_livre_risco=_taxa_cli(args.rf, "--rf"),
            beta=_numero_cli(args.beta, "--beta") if args.beta is not None else None,
            premio_risco_mercado=_taxa_cli(args.premio, "--premio"),
            custo_divida=_taxa_cli(args.kd, "--kd"),
        )
        cenario = None
        if args.captacao is not None:
            if args.taxa_divida is None or args.preco_emissao is None:
                raise ValueError("--captacao exige --taxa-divida e --preco-emissao.")
            cenario = ec.CenarioCaptacao(
                _numero_cli(args.captacao, "--captacao"), _taxa_cli(args.taxa_divida, "--taxa-divida"),
                _numero_cli(args.preco_emissao, "--preco-emissao"),
                _numero_cli(args.ebit_projetado, "--ebit-projetado") if args.ebit_projetado is not None else None)
        projeto = None
        if args.projeto is not None:
            valores = _ler_fluxos(args.projeto)
            if len(valores) < 2:
                raise ValueError(f"Informe de 1 a {ai.MAX_FLUXOS} fluxos anuais.")
            projeto = ai.Projeto(valores[0], valores[1:], _taxa_cli(args.taxa_projeto, "--taxa-projeto"))
        opcoes = {"parametros": parametros, "captacao": cenario, "projeto": projeto}

        if args.exemplo:
            resultado = analisar_exemplo(**opcoes)
        elif args.json:
            resultado = analisar_json(args.json, **opcoes)
        else:
            resultado = analisar_cvm(
                args.empresa, args.ano, consolidado=not args.individual,
                preco_acao=_numero_cli(args.preco, "--preco") if args.preco else None,
                numero_acoes=_numero_cli(args.acoes, "--acoes") if args.acoes else None,
                caminho_zip=args.zip, progresso=_progresso_console, **opcoes)
            print()
    except (cvm.ErroCVM, ValueError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    _mostrar_resultado(resultado, salvar=not args.nao_salvar, pasta=args.pasta_saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
