#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py - Aplicação de Análise de Demonstrações Financeiras (ponto de entrada)
=============================================================================
CAD 167 – Administração Financeira (UFMG) – Trabalho 1

Arquitetura em 3 camadas (cada uma em um arquivo):
  - cvm_loader.py                          -> DADOS: captura as demonstrações reais da CVM
  - analise_demonstracoes_financeiras.py   -> CÁLCULO: indicadores financeiros por módulo
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
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

import cvm_loader as cvm
from analise_demonstracoes_financeiras import (
    DADOS_EXEMPLO,
    AnalisadorFinanceiro,
    DadosFinanceiros,
    Indicador,
    formatar_valor,
)

PASTA_RELATORIOS_PADRAO = "relatorios"


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
                        "unidade": i.unidade, "formula": i.formula} for i in indicadores]
                for nome, indicadores in self.modulos.items()
            },
        }


def analisar_dados(dados: DadosFinanceiros, avisos: Optional[Sequence[str]] = None,
                   fonte: str = "") -> ResultadoAnalise:
    """Executa a análise sobre dados já carregados (qualquer origem)."""
    analisador = AnalisadorFinanceiro(dados)
    avisos_lista = list(avisos or [])
    texto = analisador.formatar_relatorio()
    if fonte:
        texto += f"\nFonte dos dados: {fonte}"
    if avisos_lista:
        texto += "\n\nAvisos sobre os dados:\n" + "\n".join(f"  - {a}" for a in avisos_lista)
    return ResultadoAnalise(dados=dados, modulos=analisador.gerar_relatorio(), texto=texto,
                            fonte=fonte, avisos=avisos_lista)


def analisar_exemplo() -> ResultadoAnalise:
    """Análise com os dados fictícios embutidos (funciona sem internet)."""
    return analisar_dados(DadosFinanceiros.from_dict(DADOS_EXEMPLO), fonte="dados fictícios de exemplo")


def analisar_json(caminho: Union[str, Path]) -> ResultadoAnalise:
    """Análise de um arquivo JSON no formato de `dados_entrada.json`."""
    try:
        dados = DadosFinanceiros.from_json(str(caminho))
    except FileNotFoundError as erro:
        raise cvm.ErroCVM(f"Arquivo não encontrado: {caminho}") from erro
    except (json.JSONDecodeError, TypeError) as erro:
        raise cvm.ErroCVM(f"O arquivo {caminho} não é um JSON válido de demonstrações ({erro}).") from erro
    return analisar_dados(dados, fonte=f"arquivo {caminho}")


def analisar_cvm(
    empresa: Union[cvm.EmpresaCVM, str],
    ano: Optional[int] = None,
    consolidado: bool = True,
    preco_acao: Optional[float] = None,
    numero_acoes: Optional[float] = None,
    caminho_zip: Optional[Union[str, Path]] = None,
    progresso: Optional[cvm.Progresso] = None,
) -> ResultadoAnalise:
    """Captura os dados da CVM e executa a análise (veja `cvm.carregar_dados` para os parâmetros)."""
    carga = cvm.carregar_dados(empresa, ano or cvm.ano_padrao(), consolidado=consolidado,
                               preco_acao=preco_acao, numero_acoes=numero_acoes,
                               caminho_zip=caminho_zip, progresso=progresso)
    return analisar_dados(carga.dados, carga.avisos, carga.fonte)


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


def _gerar_html(res: ResultadoAnalise) -> str:
    """Relatório em HTML autônomo (abre em qualquer navegador, sem internet)."""
    e = html.escape
    partes = [
        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>",
        f"<title>Análise financeira - {e(res.dados.empresa)}</title>",
        "<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222}"
        "h1{margin-bottom:0}h2{background:#1f3a5f;color:#fff;padding:.4rem .7rem;font-size:1.05rem;margin-top:2rem}"
        "table{width:100%;border-collapse:collapse}td{padding:.35rem .6rem;border-bottom:1px solid #ddd}"
        "td.v{text-align:right;font-weight:600;white-space:nowrap}td.f{color:#666;font-size:.9rem}"
        ".aviso{background:#fff4d6;border-left:4px solid #e0a800;padding:.5rem .8rem;margin:.4rem 0}"
        "small{color:#666}</style></head><body>",
        f"<h1>{e(res.dados.empresa)}</h1><p>{e(res.dados.periodo)}<br>",
        f"<small>{e(res.fonte)} &middot; valores monetários em R$ mil</small></p>",
    ]
    for modulo, indicadores in res.modulos.items():
        partes.append(f"<h2>{e(modulo)}</h2><table>")
        for ind in indicadores:
            partes.append(f"<tr><td>{e(ind.nome)}</td><td class='v'>{e(formatar_valor(ind))}</td>"
                          f"<td class='f'>{e(ind.formula)}</td></tr>")
        partes.append("</table>")
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


def _mostrar_resultado(res: ResultadoAnalise, salvar: bool, pasta: str) -> None:
    """Imprime o relatório e, opcionalmente, salva os arquivos."""
    print("\n" + res.texto + "\n")
    if salvar:
        arquivos = salvar_relatorios(res, pasta)
        print("Relatórios salvos em:")
        for caminho in arquivos:
            print(f"  - {caminho}")
        print(f"Dica: abra {arquivos[1]} no navegador para ver a versão visual.\n")


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
        print("P/L, Market-to-Book, Valor de Mercado e EV, ou pule para analisar os demais indicadores.")
        preco = _perguntar_numero("Preço da ação em R$ (ex.: 45,30)")
        acoes = _perguntar_numero("Número de ações, para substituir o da CVM (ex.: 4.197.317.998)") if preco is not None else None
        resultado = analisar_cvm(empresa, ano, consolidado, preco, acoes, caminho_zip=caminho)
        _mostrar_resultado(resultado, salvar=True, pasta=pasta)
    except cvm.ErroCVM as erro:
        print(f"\nErro: {erro}\n")


def _menu_interativo(pasta: str) -> None:
    """Menu principal."""
    while True:
        print("=" * 60)
        print(" ANÁLISE DE DEMONSTRAÇÕES FINANCEIRAS - CAD 167".center(60))
        print("=" * 60)
        print("  1. Analisar uma empresa real (dados da CVM)")
        print("  2. Analisar um arquivo JSON de dados")
        print("  3. Executar com dados fictícios de exemplo")
        print("  0. Sair")
        opcao = input("Escolha uma opção: ").strip()
        try:
            if opcao == "1":
                _fluxo_cvm_interativo(pasta)
            elif opcao == "2":
                caminho = _perguntar("Caminho do arquivo JSON", "dados.json")
                _mostrar_resultado(analisar_json(caminho), salvar=True, pasta=pasta)
            elif opcao == "3":
                _mostrar_resultado(analisar_exemplo(), salvar=True, pasta=pasta)
            elif opcao == "0":
                print("Até logo!")
                return
            else:
                print("Opção inválida.\n")
        except cvm.ErroCVM as erro:
            print(f"\nErro: {erro}\n")
        except (KeyboardInterrupt, EOFError):
            print("\nEncerrado.")
            return


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Ponto de entrada. Sem argumentos abre o menu; com argumentos executa direto."""
    # Garante acentuação correta no console do Windows
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    parser = argparse.ArgumentParser(
        description="Análise de Demonstrações Financeiras (sem argumentos: abre o menu interativo).")
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
    args = parser.parse_args(argv)

    if not (args.exemplo or args.json or args.empresa):
        _menu_interativo(args.pasta_saida)
        return 0

    try:
        if args.exemplo:
            resultado = analisar_exemplo()
        elif args.json:
            resultado = analisar_json(args.json)
        else:
            resultado = analisar_cvm(
                args.empresa, args.ano, consolidado=not args.individual,
                preco_acao=cvm.ler_numero_br(args.preco) if args.preco else None,
                numero_acoes=cvm.ler_numero_br(args.acoes) if args.acoes else None,
                caminho_zip=args.zip, progresso=_progresso_console)
            print()
    except (cvm.ErroCVM, ValueError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    _mostrar_resultado(resultado, salvar=not args.nao_salvar, pasta=args.pasta_saida)
    return 0


if __name__ == "__main__":
    sys.exit(main())
