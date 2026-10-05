#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
servidor_web.py - Front-end web da Análise de Demonstrações Financeiras
=======================================================================
CAD 167 – Administração Financeira (UFMG) – Trabalho 1

Servidor HTTP (apenas biblioteca padrão) que expõe a API de serviço de `app.py` em JSON
e serve a interface da pasta `web/`.

COMO USAR:
    python servidor_web.py                 # abre http://127.0.0.1:8000 no navegador
    python servidor_web.py --porta 8080 --sem-navegador

Rotas da API:
    GET  /api/config                       -> ano padrão
    POST /api/dfp/preparar   {ano}         -> inicia (em segundo plano) o download da DFP do ano
    GET  /api/dfp/status?ano=2025          -> andamento do download
    GET  /api/empresas?ano=2025&termo=weg  -> busca empresas no arquivo da CVM
    POST /api/analisar/cvm   {cnpj, nome, cd_cvm, ano, consolidado, preco, acoes}
    POST /api/analisar/dados {dados}       -> analisa dados no formato de dados_entrada.json
    GET  /api/analisar/exemplo             -> dados fictícios de exemplo
"""

from __future__ import annotations

import argparse
import json
import math
import mimetypes
import threading
import traceback
import webbrowser
import zipfile
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import app
import cvm_loader as cvm
from analise_demonstracoes_financeiras import DadosFinanceiros

PASTA_WEB = Path(__file__).resolve().parent / "web"
TAMANHO_MAXIMO_CORPO = 2 * 1024 * 1024


class ErroRequisicao(Exception):
    """Erro de entrada do usuário (vira HTTP 400 com mensagem amigável)."""


# ----------------------------------------------------------------------------
# Download da DFP em segundo plano (para mostrar progresso na interface)
# ----------------------------------------------------------------------------
class GerenciadorDownloads:
    def __init__(self) -> None:
        self._trava = threading.Lock()
        self._estados: Dict[int, Dict[str, Any]] = {}

    def _arquivo_pronto(self, ano: int) -> Optional[Path]:
        destino = cvm.PASTA_CACHE_PADRAO / f"dfp_cia_aberta_{ano}.zip"
        return destino if destino.exists() and zipfile.is_zipfile(destino) else None

    def status(self, ano: int) -> Dict[str, Any]:
        with self._trava:
            estado = self._estados.get(ano)
            if estado and estado["estado"] == "baixando":
                return dict(estado)
        caminho = self._arquivo_pronto(ano)
        if not caminho:
            if estado and estado["estado"] == "erro":
                return dict(estado)
            return {"estado": "ausente", "baixado": 0, "total": None, "erro": None}
        try:
            empresas = len(cvm.listar_empresas(caminho))
        except (cvm.ErroCVM, zipfile.BadZipFile, OSError) as erro:
            return {"estado": "erro", "baixado": 0, "total": None,
                    "erro": f"O arquivo {caminho} está inválido ou corrompido ({erro}). Apague-o e baixe novamente."}
        return {"estado": "pronto", "baixado": 0, "total": None, "erro": None, "empresas": empresas}

    def preparar(self, ano: int) -> Dict[str, Any]:
        """Inicia o download, se necessário, e devolve o status atual."""
        with self._trava:
            atual = self._estados.get(ano)
            if atual and atual["estado"] == "baixando":
                return dict(atual)
            pronto = self._arquivo_pronto(ano) is not None
            if not pronto:
                self._estados[ano] = {"estado": "baixando", "baixado": 0, "total": None, "erro": None}
        if pronto:
            atual = self.status(ano)
            if atual["estado"] != "erro":
                return atual
            # Arquivo no cache é um zip, mas não uma DFP legível: baixa de novo
            with self._trava:
                if self._estados.get(ano, {}).get("estado") == "baixando":
                    return dict(self._estados[ano])
                self._estados[ano] = {"estado": "baixando", "baixado": 0, "total": None, "erro": None}
        threading.Thread(target=self._baixar, args=(ano,), daemon=True).start()
        return self.status(ano)

    def _baixar(self, ano: int) -> None:
        def progresso(baixado: int, total: Optional[int]) -> None:
            with self._trava:
                self._estados[ano].update(baixado=baixado, total=total)

        try:
            cvm.obter_zip_dfp(ano, cvm.PASTA_CACHE_PADRAO, forcar_download=True, progresso=progresso)
            # Indexa as empresas já agora, para a primeira busca ser rápida
            cvm.listar_empresas(cvm.PASTA_CACHE_PADRAO / f"dfp_cia_aberta_{ano}.zip")
            novo = {"estado": "pronto", "erro": None}
        except cvm.ErroCVM as erro:
            novo = {"estado": "erro", "erro": str(erro)}
        except Exception as erro:  # noqa: BLE001 - qualquer falha precisa chegar à interface
            novo = {"estado": "erro", "erro": f"Falha inesperada no download: {erro}"}
        with self._trava:
            self._estados[ano].update(novo)

    def caminho(self, ano: int) -> Path:
        caminho = self._arquivo_pronto(ano)
        if not caminho:
            raise ErroRequisicao(f"O arquivo da CVM de {ano} ainda não foi baixado.")
        return caminho


DOWNLOADS = GerenciadorDownloads()


# ----------------------------------------------------------------------------
# Conversão dos resultados para JSON
# ----------------------------------------------------------------------------
def _limpar(valor: Any) -> Any:
    """Troca NaN/infinito por None (JSON válido)."""
    if isinstance(valor, float) and not math.isfinite(valor):
        return None
    if isinstance(valor, dict):
        return {k: _limpar(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_limpar(v) for v in valor]
    return valor


def _resultado_para_json(res: app.ResultadoAnalise) -> Dict[str, Any]:
    d = res.para_dict()
    d["texto"] = res.texto
    d["relatorio_html"] = app._gerar_html(res)
    return _limpar(d)


def _ano(valor: Any) -> int:
    if isinstance(valor, bool):
        raise ErroRequisicao("Ano inválido.")
    try:
        ano = int(valor)
    except (TypeError, ValueError):
        raise ErroRequisicao("Ano inválido.") from None
    if not 2010 <= ano <= cvm.ano_padrao() + 1:
        raise ErroRequisicao(f"Ano fora do intervalo disponível (2010 a {cvm.ano_padrao() + 1}).")
    return ano


def _numero_opcional(valor: Any, nome: str) -> Optional[float]:
    """Número positivo opcional (preço, nº de ações), aceitando o formato brasileiro."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None
    numero: Optional[float] = None
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        numero = float(valor)
    elif isinstance(valor, str):
        try:
            numero = cvm.ler_numero_br(valor)
        except ValueError:
            pass
    if numero is None or not math.isfinite(numero):
        raise ErroRequisicao(f"{nome} inválido: '{valor}'. Exemplos: 45,30 ou 4.197.317.998")
    if numero <= 0:
        raise ErroRequisicao(f"{nome} deve ser maior que zero.")
    return numero


def _booleano(valor: Any, padrao: bool = True) -> bool:
    if valor is None:
        return padrao
    if isinstance(valor, str):
        return valor.strip().lower() not in ("false", "0", "nao", "não", "n", "")
    return bool(valor)


# ----------------------------------------------------------------------------
# Rotas
# ----------------------------------------------------------------------------
def rota_config(_q, _c) -> Dict[str, Any]:
    return {"ano_padrao": cvm.ano_padrao()}


def rota_dfp_status(q, _c) -> Dict[str, Any]:
    return DOWNLOADS.status(_ano(q.get("ano")))


def rota_dfp_preparar(_q, corpo) -> Dict[str, Any]:
    return DOWNLOADS.preparar(_ano(corpo.get("ano")))


def rota_empresas(q, _c) -> Dict[str, Any]:
    termo = (q.get("termo") or "").strip()
    if len(termo) < 2:
        return {"empresas": []}
    caminho = DOWNLOADS.caminho(_ano(q.get("ano")))
    achadas = cvm.buscar_empresas(termo, caminho, limite=25)
    return {"empresas": [{"cnpj": e.cnpj, "nome": e.nome, "cd_cvm": e.cd_cvm} for e in achadas]}


def rota_analisar_cvm(_q, corpo) -> Dict[str, Any]:
    ano = _ano(corpo.get("ano"))
    if not corpo.get("cnpj"):
        raise ErroRequisicao("Selecione uma empresa.")
    empresa = cvm.EmpresaCVM(cnpj=str(corpo["cnpj"]), nome=str(corpo.get("nome") or corpo["cnpj"]),
                             cd_cvm=str(corpo.get("cd_cvm") or ""))
    preco = _numero_opcional(corpo.get("preco"), "Preço da ação")
    acoes = _numero_opcional(corpo.get("acoes"), "Número de ações")
    res = app.analisar_cvm(empresa, ano, consolidado=_booleano(corpo.get("consolidado")),
                           preco_acao=preco, numero_acoes=acoes, caminho_zip=DOWNLOADS.caminho(ano))
    return _resultado_para_json(res)


def rota_analisar_dados(_q, corpo) -> Dict[str, Any]:
    dados = corpo.get("dados")
    if not isinstance(dados, dict):
        raise ErroRequisicao("Envie os dados no formato de dados_entrada.json.")
    for secao in ("balanco", "dre", "dfc", "mercado"):
        contas = dados.get(secao)
        if contas is None:
            continue
        if not isinstance(contas, dict):
            raise ErroRequisicao(f"A seção '{secao}' deve ser um objeto com as contas (ex.: {{\"caixa\": 1000}}).")
        for conta, valor in contas.items():
            numero_valido = isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
            if valor is not None and not numero_valido:
                raise ErroRequisicao(f"Valor inválido em {secao}.{conta}: {valor!r} (use números, em R$ mil).")
    dados = {**dados, "empresa": str(dados.get("empresa") or "Empresa").strip() or "Empresa",
             "periodo": str(dados.get("periodo") or "").strip()}
    fonte = str(corpo.get("fonte") or "dados informados pelo usuário")
    return _resultado_para_json(app.analisar_dados(DadosFinanceiros.from_dict(dados), fonte=fonte))


def rota_exemplo(_q, _c) -> Dict[str, Any]:
    return _resultado_para_json(app.analisar_exemplo())


ROTAS_GET = {
    "/api/config": rota_config,
    "/api/dfp/status": rota_dfp_status,
    "/api/empresas": rota_empresas,
    "/api/analisar/exemplo": rota_exemplo,
}
ROTAS_POST = {
    "/api/dfp/preparar": rota_dfp_preparar,
    "/api/analisar/cvm": rota_analisar_cvm,
    "/api/analisar/dados": rota_analisar_dados,
}


class Manipulador(BaseHTTPRequestHandler):
    server_version = "AnaliseFinanceira/1.0"

    def log_message(self, formato: str, *args: Any) -> None:  # silencia o log por requisição
        pass

    def _responder(self, status: int, corpo: bytes, tipo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _json(self, status: int, dados: Dict[str, Any]) -> None:
        self._responder(status, json.dumps(dados, ensure_ascii=False).encode("utf-8"),
                        "application/json; charset=utf-8")

    def _executar(self, rota, corpo: Dict[str, Any]) -> None:
        consulta = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
        try:
            self._json(HTTPStatus.OK, rota(consulta, corpo))
        except (ErroRequisicao, cvm.ErroCVM) as erro:
            self._json(HTTPStatus.BAD_REQUEST, {"erro": str(erro)})
        except Exception as erro:  # noqa: BLE001
            traceback.print_exc()
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {"erro": f"Erro interno: {erro}"})

    def do_GET(self) -> None:  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho in ROTAS_GET:
            self._executar(ROTAS_GET[caminho], {})
        elif caminho.startswith("/api/"):
            self._json(HTTPStatus.NOT_FOUND, {"erro": "Rota não encontrada."})
        else:
            self._estatico(caminho)

    def do_POST(self) -> None:  # noqa: N802
        caminho = urlparse(self.path).path
        if caminho not in ROTAS_POST:
            self._json(HTTPStatus.NOT_FOUND, {"erro": "Rota não encontrada."})
            return
        try:
            tamanho = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            tamanho = -1
        if tamanho < 0:
            self._json(HTTPStatus.BAD_REQUEST, {"erro": "Cabeçalho Content-Length inválido."})
            return
        if tamanho > TAMANHO_MAXIMO_CORPO:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"erro": "Requisição muito grande."})
            return
        try:
            corpo = json.loads(self.rfile.read(tamanho) or b"{}")
            if not isinstance(corpo, dict):
                raise ValueError
        except ValueError:
            self._json(HTTPStatus.BAD_REQUEST, {"erro": "JSON inválido."})
            return
        self._executar(ROTAS_POST[caminho], corpo)

    def _estatico(self, caminho: str) -> None:
        relativo = "index.html" if caminho in ("", "/") else caminho.lstrip("/")
        arquivo = (PASTA_WEB / relativo).resolve()
        if PASTA_WEB not in arquivo.parents or not arquivo.is_file():
            self._responder(HTTPStatus.NOT_FOUND, "Não encontrado".encode("utf-8"), "text/plain; charset=utf-8")
            return
        tipo = mimetypes.guess_type(arquivo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        self._responder(HTTPStatus.OK, arquivo.read_bytes(), tipo)


def main() -> None:
    parser = argparse.ArgumentParser(description="Interface web da análise de demonstrações financeiras")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--porta", type=int, default=8000)
    parser.add_argument("--sem-navegador", action="store_true", help="não abre o navegador automaticamente")
    args = parser.parse_args()

    try:
        servidor = ThreadingHTTPServer((args.host, args.porta), Manipulador)
    except OSError as erro:
        raise SystemExit(f"Não foi possível usar a porta {args.porta} ({erro.strerror}). "
                         f"Talvez o servidor já esteja aberto em http://{args.host}:{args.porta} — "
                         f"ou escolha outra porta: python servidor_web.py --porta 8080") from None
    url = f"http://{args.host}:{args.porta}"
    print(f"Interface disponível em {url}  (Ctrl+C para encerrar)")
    if not args.sem_navegador:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
