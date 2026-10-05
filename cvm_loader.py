#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cvm_loader.py - Captura de dados reais da CVM (Dados Abertos) para a análise financeira
=======================================================================================
CAD 167 – Administração Financeira (UFMG) – Trabalho 1

Este módulo é a CAMADA DE DADOS do projeto. Ele:
  1. baixa (e guarda em cache) o arquivo anual DFP da CVM (demonstrações das companhias abertas);
  2. permite BUSCAR empresas pelo nome ou CNPJ;
  3. lê Balanço (BPA/BPP), DRE e DFC da empresa escolhida;
  4. converte tudo para o objeto `DadosFinanceiros` usado por `analise_demonstracoes_financeiras.py`.

Não usa bibliotecas externas (apenas a biblioteca padrão do Python), para rodar em qualquer máquina.
Não imprime nada nem pede dados ao usuário: toda a interação fica em `app.py`. Assim, um
front-end futuro pode chamar estas funções diretamente.

Funções principais (API):
    obter_zip_dfp(ano)                    -> Path do .zip (baixa se necessário)
    buscar_empresas(termo, caminho_zip)   -> lista de EmpresaCVM
    carregar_dados(empresa, ano, ...)     -> ResultadoCarga (dados + avisos)
    salvar_dados_json(dados, caminho)     -> grava JSON compatível com `--json` do script de análise

Uso rápido (linha de comando), gerando um JSON que o script de análise consegue ler:
    python cvm_loader.py "weg" --ano 2025 --saida dados.json

Convenções:
  - Valores convertidos automaticamente para R$ mil (a CVM informa a escala em ESCALA_MOEDA).
  - Usa o ÚLTIMO exercício do arquivo e a VERSÃO mais recente de cada demonstração (reapresentações).
  - Despesas/custos da DRE vêm negativos na CVM e são convertidos para valores positivos.
  - Número de ações e preço NÃO constam da DFP: devem ser informados pelo usuário (opcionais).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import unicodedata
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Callable, Dict, Iterator, List, Optional, Tuple, Union

from analise_demonstracoes_financeiras import (
    BalancoPatrimonial,
    DadosFinanceiros,
    DadosMercado,
    DFC,
    DRE,
)

# Endereço oficial dos arquivos anuais (DFP) no Portal de Dados Abertos da CVM
URL_DFP = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip"
PASTA_CACHE_PADRAO = Path("cache_cvm")

# Função de progresso: recebe (bytes_baixados, total_de_bytes_ou_None)
Progresso = Callable[[int, Optional[int]], None]


class ErroCVM(Exception):
    """Erro esperado (rede, arquivo ou empresa não encontrados). A mensagem é amigável ao usuário."""


# ----------------------------------------------------------------------------
# Utilitários de texto e números
# ----------------------------------------------------------------------------
def normalizar(texto: str) -> str:
    """Minúsculas e sem acentos, para comparar textos ('ÚLTIMO' == 'ultimo')."""
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode("ascii")
    return sem_acento.lower().strip()


def so_digitos(texto: str) -> str:
    """Mantém apenas dígitos (útil para comparar CNPJs)."""
    return re.sub(r"\D", "", texto or "")


def ler_numero_br(texto: str) -> float:
    """
    Converte texto digitado em número. Aceita '18,50', '18.50', '4.197.317.998', 'R$ 1.234,56'.
    Levanta ValueError se não for um número.
    """
    t = (texto or "").replace("R$", "").replace(" ", "").strip()
    if not t:
        raise ValueError("valor vazio")
    if "," in t:                       # formato brasileiro: ponto = milhar, vírgula = decimal
        t = t.replace(".", "").replace(",", ".")
    elif t.count(".") > 1:             # vários pontos: só podem ser separadores de milhar
        t = t.replace(".", "")
    return float(t)


def ano_padrao() -> int:
    """Ano do último exercício com DFP normalmente disponível (ano anterior ao atual)."""
    return date.today().year - 1


# ----------------------------------------------------------------------------
# Download do arquivo da CVM (com cache local)
# ----------------------------------------------------------------------------
def obter_zip_dfp(
    ano: int,
    pasta_cache: Union[str, Path] = PASTA_CACHE_PADRAO,
    forcar_download: bool = False,
    progresso: Optional[Progresso] = None,
) -> Path:
    """
    Devolve o caminho do .zip da DFP do ano, baixando-o da CVM se ainda não estiver no cache.
    Se o download falhar, levanta ErroCVM explicando como baixar manualmente.
    """
    pasta = Path(pasta_cache)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"dfp_cia_aberta_{ano}.zip"

    # Reaproveita o arquivo já baixado (evita baixar dezenas de MB a cada execução)
    if destino.exists() and not forcar_download and zipfile.is_zipfile(destino):
        return destino

    url = URL_DFP.format(ano=ano)
    temporario = destino.with_suffix(".part")
    instrucao_manual = (
        f"Baixe manualmente o arquivo em {url} e informe o caminho dele "
        f"(opção --zip, ou copie-o para a pasta '{pasta}')."
    )
    try:
        pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (trabalho CAD167)"})
        with urllib.request.urlopen(pedido, timeout=60) as resposta, open(temporario, "wb") as saida:
            total_txt = resposta.headers.get("Content-Length")
            total = int(total_txt) if total_txt else None
            baixado = 0
            while True:
                bloco = resposta.read(256 * 1024)
                if not bloco:
                    break
                saida.write(bloco)
                baixado += len(bloco)
                if progresso:
                    progresso(baixado, total)
        temporario.replace(destino)
    except urllib.error.HTTPError as erro:
        temporario.unlink(missing_ok=True)
        if erro.code == 404:
            raise ErroCVM(f"A CVM ainda não publicou a DFP de {ano} (erro 404). Tente o ano anterior.") from erro
        raise ErroCVM(f"A CVM respondeu com erro HTTP {erro.code}. {instrucao_manual}") from erro
    except (urllib.error.URLError, TimeoutError, OSError) as erro:
        temporario.unlink(missing_ok=True)
        raise ErroCVM(f"Não foi possível baixar o arquivo da CVM ({erro}). {instrucao_manual}") from erro

    if not zipfile.is_zipfile(destino):
        destino.unlink(missing_ok=True)
        raise ErroCVM(f"O arquivo baixado não é um .zip válido. {instrucao_manual}")
    return destino


# ----------------------------------------------------------------------------
# Leitura dos CSVs dentro do .zip
# ----------------------------------------------------------------------------
def _achar_arquivo(zf: zipfile.ZipFile, demonstracao: str, escopo: str) -> Optional[str]:
    """Localiza no zip o CSV de uma demonstração, ex.: ('bpa', 'con') -> '..._BPA_con_2025.csv'."""
    alvo = f"_{demonstracao}_{escopo}_".lower()
    for nome in zf.namelist():
        if alvo in nome.lower() and nome.lower().endswith(".csv"):
            return nome
    return None


def _linhas_csv(zf: zipfile.ZipFile, nome: str) -> Iterator[Dict[str, str]]:
    """Lê um CSV da CVM (separador ';', codificação latin-1) linha a linha, sem carregar tudo na memória."""
    with zf.open(nome) as bruto:
        texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
        yield from csv.DictReader(texto, delimiter=";")


@dataclass(frozen=True)
class EmpresaCVM:
    """Identificação de uma companhia aberta."""
    cnpj: str
    nome: str
    cd_cvm: str = ""


@lru_cache(maxsize=4)
def _indice_empresas(caminho_zip: str, data_modificacao: float) -> Tuple[EmpresaCVM, ...]:
    """Lista única de empresas do arquivo (cacheada: o arquivo é percorrido uma só vez)."""
    with zipfile.ZipFile(caminho_zip) as zf:
        arquivo = _achar_arquivo(zf, "bpa", "ind") or _achar_arquivo(zf, "bpa", "con")
        if not arquivo:
            raise ErroCVM("O .zip não contém o Balanço Patrimonial (BPA). É mesmo um arquivo DFP da CVM?")
        vistas: Dict[str, EmpresaCVM] = {}
        for linha in _linhas_csv(zf, arquivo):
            cnpj = (linha.get("CNPJ_CIA") or "").strip()
            if cnpj and cnpj not in vistas:
                vistas[cnpj] = EmpresaCVM(cnpj, (linha.get("DENOM_CIA") or "").strip(),
                                          (linha.get("CD_CVM") or "").strip())
    return tuple(sorted(vistas.values(), key=lambda e: e.nome))


def listar_empresas(caminho_zip: Union[str, Path]) -> List[EmpresaCVM]:
    """Todas as empresas disponíveis no arquivo DFP."""
    caminho = Path(caminho_zip)
    return list(_indice_empresas(str(caminho), caminho.stat().st_mtime))


def buscar_empresas(termo: str, caminho_zip: Union[str, Path], limite: int = 20) -> List[EmpresaCVM]:
    """
    Busca empresas por parte do nome (sem distinção de acentos/maiúsculas) ou por CNPJ.
    Ex.: buscar_empresas('weg', zip), buscar_empresas('84.429.695', zip)
    """
    palavras = normalizar(termo).split()
    digitos = so_digitos(termo)
    busca_por_cnpj = len(digitos) >= 5 and not re.search(r"[a-zA-Z]", termo)
    achadas: List[EmpresaCVM] = []
    for empresa in listar_empresas(caminho_zip):
        if busca_por_cnpj:
            if digitos in so_digitos(empresa.cnpj):
                achadas.append(empresa)
        elif palavras and all(p in normalizar(empresa.nome) for p in palavras):
            achadas.append(empresa)
    # Nomes que COMEÇAM com o termo aparecem primeiro
    achadas.sort(key=lambda e: (not normalizar(e.nome).startswith(normalizar(termo)), e.nome))
    return achadas[:limite]


def resolver_empresa(termo: str, caminho_zip: Union[str, Path]) -> EmpresaCVM:
    """Encontra UMA empresa pelo termo. Levanta ErroCVM se não achar ou se houver ambiguidade."""
    achadas = buscar_empresas(termo, caminho_zip, limite=10)
    if not achadas:
        raise ErroCVM(f"Nenhuma empresa encontrada para '{termo}'.")
    exatas = [e for e in achadas if normalizar(e.nome) == normalizar(termo) or so_digitos(e.cnpj) == so_digitos(termo)]
    if len(exatas) == 1:
        return exatas[0]
    if len(achadas) > 1:
        nomes = "; ".join(e.nome for e in achadas[:8])
        raise ErroCVM(f"'{termo}' corresponde a várias empresas ({nomes}). Seja mais específico ou use o CNPJ.")
    return achadas[0]


# ----------------------------------------------------------------------------
# Extração das contas de uma empresa
# ----------------------------------------------------------------------------
@dataclass
class Conta:
    """Uma linha de demonstração da CVM, já convertida para R$ mil."""
    codigo: str
    descricao: str
    valor: float


_ESCALAS_PARA_MIL = {"unidade": 0.001, "mil": 1.0, "milhao": 1000.0, "milhoes": 1000.0}


def _ler_contas(zf: zipfile.ZipFile, arquivo: str, cnpj: str) -> Tuple[Dict[str, Conta], str]:
    """
    Lê as contas do ÚLTIMO exercício de uma empresa, usando a versão mais recente do documento.
    Devolve ({codigo_da_conta: Conta}, data_de_referencia).
    """
    candidatas = []  # (versao, codigo, descricao, valor_em_mil, data_ref)
    for linha in _linhas_csv(zf, arquivo):
        if (linha.get("CNPJ_CIA") or "").strip() != cnpj:
            continue
        if not normalizar(linha.get("ORDEM_EXERC", "")).startswith("ult"):
            continue  # ignora o exercício anterior (PENÚLTIMO)
        try:
            valor = float((linha.get("VL_CONTA") or "").replace(",", "."))
        except ValueError:
            continue
        fator = _ESCALAS_PARA_MIL.get(normalizar(linha.get("ESCALA_MOEDA", "")), 1.0)
        try:
            versao = int(linha.get("VERSAO") or 1)
        except ValueError:
            versao = 1
        candidatas.append((versao, (linha.get("CD_CONTA") or "").strip(),
                           (linha.get("DS_CONTA") or "").strip(), valor * fator,
                           (linha.get("DT_REFER") or "").strip()))
    if not candidatas:
        return {}, ""
    versao_maxima = max(c[0] for c in candidatas)
    contas = {cod: Conta(cod, desc, val) for v, cod, desc, val, _ in candidatas if v == versao_maxima}
    data_ref = next(c[4] for c in candidatas if c[0] == versao_maxima)
    return contas, data_ref


def _valor(contas: Dict[str, Conta], codigo: str, sinal: float = 1.0) -> Optional[float]:
    """Valor de uma conta (ou None se não existir), opcionalmente com o sinal invertido."""
    conta = contas.get(codigo)
    return None if conta is None else sinal * conta.valor


def _depreciacao_amortizacao(dfc: Dict[str, Conta]) -> Optional[float]:
    """
    A D&A não tem código fixo na CVM. Soma as linhas de 'depreciação/amortização' dos ajustes do
    lucro no DFC (método indireto, contas 6.01.01.xx), ignorando amortização de custos de captação.
    """
    total: Optional[float] = None
    for codigo, conta in dfc.items():
        if not re.fullmatch(r"6\.01\.01\.\d{2}", codigo):
            continue
        descricao = normalizar(conta.descricao)
        if ("deprecia" in descricao or "amortiza" in descricao) and not re.search(
                r"captac|emprestimo|debenture|juros|financ", descricao):
            total = (total or 0.0) + conta.valor
    return total


# Palavras esperadas na descrição de contas-chave: serve para detectar planos de contas fora do padrão
_PALAVRAS_ESPERADAS = {
    "1.01.01": ["caixa"], "1.01.03": ["receber"], "1.01.04": ["estoque"], "1.02.03": ["imobilizado"],
    "2.01.02": ["fornecedor"], "2.01.04": ["emprestimo", "financiamento"], "2.02.01": ["emprestimo", "financiamento"],
    "3.01": ["receita", "venda"], "3.02": ["custo"], "3.05": ["resultado"], "3.11": ["lucro", "prejuizo"],
}


@dataclass
class ResultadoCarga:
    """Resultado da captura: os dados prontos para análise + avisos sobre qualidade/limitações."""
    dados: DadosFinanceiros
    empresa: EmpresaCVM
    fonte: str
    avisos: List[str] = field(default_factory=list)


def carregar_dados(
    empresa: Union[EmpresaCVM, str],
    ano: int,
    consolidado: bool = True,
    preco_acao: Optional[float] = None,
    numero_acoes: Optional[float] = None,
    caminho_zip: Optional[Union[str, Path]] = None,
    pasta_cache: Union[str, Path] = PASTA_CACHE_PADRAO,
    progresso: Optional[Progresso] = None,
) -> ResultadoCarga:
    """
    Captura as demonstrações de uma empresa na CVM e devolve `ResultadoCarga`.

    Parâmetros:
        empresa       - EmpresaCVM (de buscar_empresas) ou texto (nome/CNPJ; deve ser único).
        ano           - ano do exercício (ex.: 2025).
        consolidado   - True = demonstrações consolidadas; False = individuais.
        preco_acao    - preço da ação em R$ (opcional; necessário para P/L, Market-to-Book e EV).
        numero_acoes  - número TOTAL de ações, em unidades (opcional). Convertido para milhares.
        caminho_zip   - usar um .zip já baixado em vez de baixar da CVM.
    """
    caminho = Path(caminho_zip) if caminho_zip else obter_zip_dfp(ano, pasta_cache, progresso=progresso)
    if not caminho.exists():
        raise ErroCVM(f"Arquivo não encontrado: {caminho}")
    if isinstance(empresa, str):
        empresa = resolver_empresa(empresa, caminho)

    avisos: List[str] = []
    try:
        with zipfile.ZipFile(caminho) as zf:
            escopo = "con" if consolidado else "ind"
            bpa, data_ref = _ler_contas_escopo(zf, "bpa", escopo, empresa.cnpj)
            if not bpa and escopo == "con":  # empresa sem consolidado: usa o individual
                avisos.append("A empresa não publicou demonstrações consolidadas neste ano; foram usadas as individuais.")
                escopo = "ind"
                bpa, data_ref = _ler_contas_escopo(zf, "bpa", escopo, empresa.cnpj)
            if not bpa:
                raise ErroCVM(f"Não há dados de {empresa.nome} para o exercício de {ano} neste arquivo.")
            bpp, _ = _ler_contas_escopo(zf, "bpp", escopo, empresa.cnpj)
            dre, _ = _ler_contas_escopo(zf, "dre", escopo, empresa.cnpj)
            dfc, _ = _ler_contas_escopo(zf, "dfc_mi", escopo, empresa.cnpj)
            if not dfc:  # algumas empresas usam o método direto (sem linhas de depreciação)
                dfc, _ = _ler_contas_escopo(zf, "dfc_md", escopo, empresa.cnpj)
    except zipfile.BadZipFile as erro:
        raise ErroCVM(f"O arquivo {caminho} está corrompido. Apague-o e baixe novamente.") from erro

    todas = {**bpa, **bpp, **dre, **dfc}
    balanco, dre_obj, dfc_obj = _montar_demonstracoes(bpa, bpp, dre, dfc, avisos)
    _verificar_qualidade(todas, bpa, bpp, avisos)

    mercado = DadosMercado(
        preco_acao=preco_acao,
        numero_acoes=(numero_acoes / 1000.0) if numero_acoes else None,  # o script de análise usa milhares
    )
    if preco_acao is None or not numero_acoes:
        avisos.append("Preço e/ou número de ações não informados: LPA, VPA, P/L, Market-to-Book e EV aparecem como n/d.")

    periodo = f"Exercício encerrado em {_formatar_data(data_ref)}" if data_ref else f"Exercício de {ano}"
    dados = DadosFinanceiros(empresa=empresa.nome, periodo=periodo, balanco=balanco, dre=dre_obj,
                             dfc=dfc_obj, mercado=mercado)
    fonte = f"CVM - DFP {ano} ({'consolidado' if escopo == 'con' else 'individual'}), valores em R$ mil"
    return ResultadoCarga(dados=dados, empresa=empresa, fonte=fonte, avisos=avisos)


def _ler_contas_escopo(zf: zipfile.ZipFile, demonstracao: str, escopo: str,
                       cnpj: str) -> Tuple[Dict[str, Conta], str]:
    """Localiza o CSV da demonstração/escopo no zip e extrai as contas da empresa."""
    arquivo = _achar_arquivo(zf, demonstracao, escopo)
    return _ler_contas(zf, arquivo, cnpj) if arquivo else ({}, "")


def _formatar_data(data_iso: str) -> str:
    """'2025-12-31' -> '31/12/2025'."""
    partes = data_iso.split("-")
    return f"{partes[2]}/{partes[1]}/{partes[0]}" if len(partes) == 3 else data_iso


def _montar_demonstracoes(bpa, bpp, dre, dfc, avisos: List[str]) -> Tuple[BalancoPatrimonial, DRE, DFC]:
    """Mapeia os códigos de conta padronizados da CVM para os campos do script de análise."""
    # Caixa = Caixa e equivalentes (1.01.01) + Aplicações financeiras (1.01.02)
    caixa = None
    for codigo in ("1.01.01", "1.01.02"):
        v = _valor(bpa, codigo)
        if v is not None:
            caixa = (caixa or 0.0) + v

    estoques = _valor(bpa, "1.01.04")
    if estoques is None:
        estoques = 0.0
        avisos.append("Conta de estoques (1.01.04) não encontrada: considerada 0 (empresa sem estoques?).")
    emprestimos_cp = _valor(bpp, "2.01.04")
    emprestimos_lp = _valor(bpp, "2.02.01")
    if emprestimos_cp is None or emprestimos_lp is None:
        avisos.append("Conta de empréstimos/financiamentos (2.01.04 ou 2.02.01) não encontrada: considerada 0.")

    balanco = BalancoPatrimonial(
        caixa=caixa,
        contas_receber=_valor(bpa, "1.01.03"),
        estoques=estoques,
        ativo_circulante=_valor(bpa, "1.01"),
        imobilizado=_valor(bpa, "1.02.03"),
        intangivel=_valor(bpa, "1.02.04"),
        ativo_nao_circulante=_valor(bpa, "1.02"),
        ativo_total=_valor(bpa, "1"),
        fornecedores=_valor(bpp, "2.01.02"),
        emprestimos_cp=emprestimos_cp if emprestimos_cp is not None else 0.0,
        passivo_circulante=_valor(bpp, "2.01"),
        emprestimos_lp=emprestimos_lp if emprestimos_lp is not None else 0.0,
        patrimonio_liquido=_valor(bpp, "2.03"),
    )

    # Na DRE da CVM, custos e despesas são negativos; o script de análise espera valores positivos
    dre_obj = DRE(
        vendas=_valor(dre, "3.01"),
        cmv=_valor(dre, "3.02", -1),
        lucro_bruto=_valor(dre, "3.03"),
        despesas_operacionais=_valor(dre, "3.04", -1),
        ebit=_valor(dre, "3.05"),
        despesas_financeiras=_valor(dre, "3.06.02", -1),
        imposto_renda=_valor(dre, "3.08", -1),
        lucro_liquido=_valor(dre, "3.11"),
        depreciacao_amortizacao=_depreciacao_amortizacao(dfc),
    )
    if dre_obj.depreciacao_amortizacao is None:
        avisos.append("Depreciação e amortização não localizada no DFC: EBITDA aparece como n/d.")
    else:
        avisos.append("Depreciação e amortização estimada pela soma das linhas correspondentes do DFC (confira).")

    dfc_obj = DFC(fluxo_operacional=_valor(dfc, "6.01"), fluxo_investimento=_valor(dfc, "6.02"),
                  fluxo_financiamento=_valor(dfc, "6.03"))

    obrigatorias = {
        "Ativo Circulante": balanco.ativo_circulante, "Passivo Circulante": balanco.passivo_circulante,
        "Ativo Total": balanco.ativo_total, "Patrimônio Líquido": balanco.patrimonio_liquido,
        "Receita (vendas)": dre_obj.vendas, "CMV": dre_obj.cmv, "EBIT": dre_obj.ebit,
        "Despesas financeiras": dre_obj.despesas_financeiras, "Lucro líquido": dre_obj.lucro_liquido,
        "Contas a receber": balanco.contas_receber, "Imobilizado": balanco.imobilizado,
    }
    for nome, valor in obrigatorias.items():
        if valor is None:
            avisos.append(f"Conta não encontrada: {nome}. Indicadores que dependem dela aparecem como n/d.")
    return balanco, dre_obj, dfc_obj


def _verificar_qualidade(todas: Dict[str, Conta], bpa, bpp, avisos: List[str]) -> None:
    """Checagens de consistência para alertar o usuário sobre possíveis problemas nos dados."""
    receita = todas.get("3.01")
    if receita and "intermediacao" in normalizar(receita.descricao):
        avisos.append("Esta empresa parece ser uma instituição financeira; o plano de contas é diferente e "
                      "os indicadores não são adequados. Prefira uma empresa não financeira.")
    for codigo, palavras in _PALAVRAS_ESPERADAS.items():
        conta = todas.get(codigo)
        if conta and not any(p in normalizar(conta.descricao) for p in palavras):
            avisos.append(f"A conta {codigo} tem a descrição '{conta.descricao}', diferente da esperada. Confira o mapeamento.")
    ativo, passivo = bpa.get("1"), bpp.get("2")
    if ativo and passivo and ativo.valor and abs(ativo.valor - passivo.valor) / abs(ativo.valor) > 0.005:
        avisos.append("Ativo Total e Passivo Total diferem em mais de 0,5%: verifique os dados de origem.")


# ----------------------------------------------------------------------------
# Exportação para JSON (mesmo formato lido por `analise_demonstracoes_financeiras.py --json`)
# ----------------------------------------------------------------------------
def dados_para_dict(dados: DadosFinanceiros) -> Dict:
    """Converte DadosFinanceiros em dicionário (JSON-serializável)."""
    return asdict(dados)


def salvar_dados_json(dados: DadosFinanceiros, caminho: Union[str, Path]) -> Path:
    """Grava os dados capturados em JSON, reutilizável sem precisar baixar nada novamente."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as arquivo:
        json.dump(dados_para_dict(dados), arquivo, ensure_ascii=False, indent=2)
    return caminho


# ----------------------------------------------------------------------------
# Uso direto: gera um JSON de dados a partir da CVM
# ----------------------------------------------------------------------------
def _main() -> None:
    parser = argparse.ArgumentParser(description="Captura demonstrações de uma empresa na CVM e salva em JSON")
    parser.add_argument("empresa", help="nome (ou parte do nome) ou CNPJ")
    parser.add_argument("--ano", type=int, default=ano_padrao())
    parser.add_argument("--individual", action="store_true", help="usa demonstrações individuais")
    parser.add_argument("--zip", help="usa um .zip da DFP já baixado")
    parser.add_argument("--preco", help="preço da ação em R$")
    parser.add_argument("--acoes", help="número total de ações")
    parser.add_argument("--saida", default="dados.json")
    args = parser.parse_args()
    try:
        resultado = carregar_dados(
            args.empresa, args.ano, consolidado=not args.individual, caminho_zip=args.zip,
            preco_acao=ler_numero_br(args.preco) if args.preco else None,
            numero_acoes=ler_numero_br(args.acoes) if args.acoes else None)
    except ErroCVM as erro:
        raise SystemExit(f"Erro: {erro}")
    salvar_dados_json(resultado.dados, args.saida)
    print(f"{resultado.empresa.nome} - {resultado.fonte}")
    for aviso in resultado.avisos:
        print(f"  Aviso: {aviso}")
    print(f"Dados salvos em {args.saida}. Analise com:\n"
          f"  python analise_demonstracoes_financeiras.py --json {args.saida}")


if __name__ == "__main__":
    _main()
