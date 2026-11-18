"""Os indicadores que já existiam (módulos 1 a 6) não podem mudar com as extensões."""

from __future__ import annotations

import json
import unittest

try:
    from tests import auxiliar
except ImportError:  # executado com a pasta tests/ no caminho de importação
    import auxiliar

import app
from analise_demonstracoes_financeiras import AnalisadorFinanceiro

MODULOS_INALTERADOS = (
    "1. LIQUIDEZ E GESTÃO DE CAPITAL DE GIRO",
    "2. LUCRATIVIDADE E RENTABILIDADE",
    "3. EFICIÊNCIA E DECOMPOSIÇÃO DUPONT",
    "5. MÚLTIPLOS E AVALIAÇÃO DE MERCADO",
    "6. FLUXOS DE CAIXA (COMPLEMENTAR)",
)
MODULO_4 = "4. ESTRUTURA DE CAPITAL E ALAVANCAGEM"


class TestCompatibilidade(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with open(auxiliar.PASTA_DADOS / "base_modulos_exemplo.json", encoding="utf-8") as arquivo:
            cls.base = json.load(arquivo)
        cls.atual = app.analisar_exemplo().para_dict()["modulos"]

    def _comparar(self, esperado, obtido) -> None:
        self.assertEqual(esperado["nome"], obtido["nome"])
        if esperado["valor"] is None:
            self.assertIsNone(obtido["valor"], esperado["nome"])
        else:
            self.assertAlmostEqual(esperado["valor"], obtido["valor"], places=9, msg=esperado["nome"])
        for chave in ("valor_formatado", "unidade", "formula"):
            self.assertEqual(esperado[chave], obtido[chave], f"{esperado['nome']}: {chave}")

    def test_modulos_1_a_6_inalterados(self) -> None:
        for modulo in MODULOS_INALTERADOS:
            with self.subTest(modulo=modulo):
                self.assertIn(modulo, self.atual)
                esperado, obtido = self.base[modulo], self.atual[modulo]
                self.assertEqual([i["nome"] for i in esperado], [i["nome"] for i in obtido])
                for e, o in zip(esperado, obtido):
                    self._comparar(e, o)

    def test_modulo_4_preserva_os_indicadores_originais(self) -> None:
        esperado = self.base[MODULO_4]
        obtido = self.atual[MODULO_4][:len(esperado)]
        self.assertEqual(len(esperado), 2)
        for e, o in zip(esperado, obtido):
            self._comparar(e, o)

    def test_gerar_relatorio_mantem_os_seis_modulos(self) -> None:
        relatorio = AnalisadorFinanceiro(auxiliar.dados_exemplo()).gerar_relatorio()
        self.assertEqual(list(relatorio), list(self.base))


if __name__ == "__main__":
    unittest.main()
