"""Leitura do exercício atual e do anterior (ÚLTIMO e PENÚLTIMO) e do LAIR a partir de um zip sintético."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Dict, Iterable, Tuple

try:
    from tests import auxiliar  # noqa: F401  (ajusta o caminho de importação)
except ImportError:
    import auxiliar  # noqa: F401

import cvm_loader as cvm

CNPJ = "11.111.111/0001-11"
COLUNAS = ["CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM", "GRUPO_DFP", "MOEDA", "ESCALA_MOEDA",
           "ORDEM_EXERC", "DT_FIM_EXERC", "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA"]

# (código, descrição, valor no ÚLTIMO, valor no PENÚLTIMO), em R$ mil
CONTAS = {
    "BPA": [("1", "Ativo Total", 3000, 2800), ("1.01", "Ativo Circulante", 1000, 900),
            ("1.01.01", "Caixa e Equivalentes de Caixa", 100, 80), ("1.01.02", "Aplicações Financeiras", 20, 10),
            ("1.01.03", "Contas a Receber", 300, 280), ("1.01.04", "Estoques", 200, 190),
            ("1.02", "Ativo Não Circulante", 2000, 1900), ("1.02.03", "Imobilizado", 1500, 1400)],
    "BPP": [("2", "Passivo Total", 3000, 2800), ("2.01", "Passivo Circulante", 700, 650),
            ("2.01.02", "Fornecedores", 150, 140), ("2.01.04", "Empréstimos e Financiamentos", 120, 100),
            ("2.02.01", "Empréstimos e Financiamentos", 400, 380), ("2.03", "Patrimônio Líquido", 600, 540)],
    "DRE": [("3.01", "Receita de Venda de Bens e/ou Serviços", 2000, 1800),
            ("3.02", "Custo dos Bens e/ou Serviços Vendidos", -1200, -1100),
            ("3.03", "Resultado Bruto", 800, 700), ("3.04", "Despesas/Receitas Operacionais", -450, -400),
            ("3.05", "Resultado Antes do Resultado Financeiro e dos Tributos", 350, 300),
            ("3.06.02", "Despesas Financeiras", -70, -60),
            ("3.07", "Resultado Antes dos Tributos sobre o Lucro", 280, 240),
            ("3.08", "Imposto de Renda e Contribuição Social sobre o Lucro", -95, -90),
            ("3.11", "Lucro/Prejuízo Consolidado do Período", 185, 150)],
}


def _csv(demonstracao: str, ordens: Iterable[str]) -> bytes:
    linhas = [";".join(COLUNAS)]
    for codigo, descricao, ultimo, penultimo in CONTAS[demonstracao]:
        for ordem in ordens:
            valor = ultimo if ordem == "ÚLTIMO" else penultimo
            data = "2025-12-31" if ordem == "ÚLTIMO" else "2024-12-31"
            linhas.append(";".join([CNPJ, "2025-12-31", "1", "EMPRESA SINTÉTICA S.A.", "999", "DF Consolidado",
                                    "REAL", "MIL", ordem, data, codigo, descricao, str(valor), "S"]))
    return ("\n".join(linhas) + "\n").encode("latin-1")


def zip_sintetico(ordens: Tuple[str, ...] = ("ÚLTIMO", "PENÚLTIMO")) -> bytes:
    memoria = io.BytesIO()
    with zipfile.ZipFile(memoria, "w") as zf:
        for demonstracao in CONTAS:
            zf.writestr(f"dfp_cia_aberta_{demonstracao}_con_2025.csv", _csv(demonstracao, ordens))
    return memoria.getvalue()


class TestLeituraDoisExercicios(unittest.TestCase):
    def _carregar(self, ordens: Tuple[str, ...]):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / "dfp_cia_aberta_2025.zip"
            caminho.write_bytes(zip_sintetico(ordens))
            empresa = cvm.EmpresaCVM(CNPJ, "EMPRESA SINTÉTICA S.A.")
            return cvm.carregar_dados(empresa, 2025, numero_acoes=1_000_000, caminho_zip=caminho)

    def test_ler_contas_separa_os_exercicios(self) -> None:
        with zipfile.ZipFile(io.BytesIO(zip_sintetico())) as zf:
            atual, anterior, data_ref = cvm._ler_contas(zf, "dfp_cia_aberta_DRE_con_2025.csv", CNPJ)
        self.assertEqual(data_ref, "2025-12-31")
        self.assertEqual(atual["3.01"].valor, 2000)
        self.assertEqual(anterior["3.01"].valor, 1800)
        self.assertEqual(atual["3.07"].valor, 280)

    def test_carregar_dados_preenche_lair_e_exercicio_anterior(self) -> None:
        dados = self._carregar(("ÚLTIMO", "PENÚLTIMO")).dados
        self.assertEqual(dados.dre.lucro_antes_impostos, 280)
        ant = dados.exercicio_anterior
        self.assertIsNotNone(ant)
        esperado: Dict[str, float] = {"vendas": 1800, "ebit": 300, "lucro_liquido": 150, "emprestimos_cp": 100,
                                      "emprestimos_lp": 380, "caixa": 90, "patrimonio_liquido": 540}
        for campo, valor in esperado.items():
            self.assertEqual(getattr(ant, campo), valor, campo)
        self.assertIsNone(cvm.dados_para_dict(dados)["mercado"]["beta"])

    def test_sem_penultimo(self) -> None:
        carga = self._carregar(("ÚLTIMO",))
        self.assertIsNone(carga.dados.exercicio_anterior)
        self.assertTrue(any("Exercício anterior não encontrado" in a for a in carga.avisos))
        self.assertIsNone(cvm.dados_para_dict(carga.dados)["exercicio_anterior"])


class TestLerNumeroBr(unittest.TestCase):
    def test_formatos(self) -> None:
        for texto, esperado in {"18,50": 18.5, "18.50": 18.5, "4.197.317.998": 4_197_317_998,
                                "300.000": 300_000, "1.000": 1000, "0.055": 0.055, "R$ 1.234,56": 1234.56,
                                "-1.500": -1500, "13,75": 13.75}.items():
            with self.subTest(texto=texto):
                self.assertAlmostEqual(cvm.ler_numero_br(texto), esperado)


if __name__ == "__main__":
    unittest.main()
