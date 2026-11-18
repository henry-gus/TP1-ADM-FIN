"""Validação dos blocos parametros, captacao e projeto nas rotas (sem abrir porta)."""

from __future__ import annotations

import unittest

try:
    from tests import auxiliar
except ImportError:  # executado com a pasta tests/ no caminho de importação
    import auxiliar

import servidor_web as sw

WACC = "7. CUSTO DE CAPITAL (WACC)"


def valor(resposta, nome):
    return next(i for i in resposta["modulos"][WACC] if i["nome"] == nome)["valor"]


class TestParametros(unittest.TestCase):
    def test_exemplo_com_parametros(self) -> None:
        r = sw.rota_exemplo(None, {"parametros": {"rf": "11", "beta": "1,2", "premio": "5,5", "kd": ""}})
        self.assertAlmostEqual(valor(r, "WACC"), 0.1573, places=4)
        self.assertEqual(r["estrutura_capital"]["custo_capital_meta"]["kd_utilizado"], "contábil")

    def test_taxa_invalida(self) -> None:
        with self.assertRaises(sw.ErroRequisicao) as ctx:
            sw.rota_exemplo(None, {"parametros": {"rf": "abc"}})
        self.assertEqual(str(ctx.exception), "Taxa livre de risco inválida: 'abc'. Exemplo: 13,75")

    def test_dados_com_parametros_sobrescrevem_mercado(self) -> None:
        r = sw.rota_analisar_dados(None, {"dados": auxiliar.dict_de(), "parametros": {"beta": "1,5", "kd": "12"}})
        self.assertEqual(r["dados_entrada"]["mercado"]["beta"], 1.5)
        self.assertAlmostEqual(r["dados_entrada"]["mercado"]["custo_divida"], 0.12)
        self.assertEqual(r["estrutura_capital"]["custo_capital_meta"]["kd_utilizado"], "informado")

    def test_corpo_sem_blocos_e_motivo_em_todos(self) -> None:
        for r in (sw.rota_exemplo(None, {}), sw.rota_analisar_dados(None, {"dados": auxiliar.dict_de()})):
            self.assertIsNone(r["estrutura_capital"]["ebit_lpa"])
            self.assertIsNone(r["avaliacao_projeto"])
            for lista in r["modulos"].values():
                for indicador in lista:
                    self.assertIn("motivo", indicador)

    def test_exercicio_anterior_invalido(self) -> None:
        with self.assertRaises(sw.ErroRequisicao):
            sw.rota_analisar_dados(None, {"dados": auxiliar.dict_de(exercicio_anterior={"vendas": "x"})})


class TestCaptacao(unittest.TestCase):
    def test_exemplo(self) -> None:
        r = sw.rota_exemplo(None, {"captacao": {"valor": "300.000", "taxa": "15", "preco_emissao": "15,00",
                                                "ebit_projetado": ""}})
        self.assertAlmostEqual(r["estrutura_capital"]["ebit_lpa"]["ebit_indiferenca"], 340_000)

    def test_preco_zero(self) -> None:
        with self.assertRaises(sw.ErroRequisicao) as ctx:
            sw.rota_exemplo(None, {"captacao": {"valor": "300.000", "taxa": "15", "preco_emissao": "0"}})
        self.assertEqual(str(ctx.exception), "Preço de emissão deve ser maior que zero.")

    def test_preco_vazio(self) -> None:
        with self.assertRaises(sw.ErroRequisicao) as ctx:
            sw.rota_exemplo(None, {"captacao": {"valor": "300.000", "taxa": "15", "preco_emissao": ""}})
        self.assertIn("Preço de emissão", str(ctx.exception))

    def test_sem_bloco(self) -> None:
        self.assertIsNone(sw.rota_exemplo(None, {})["estrutura_capital"]["ebit_lpa"])


class TestProjeto(unittest.TestCase):
    CORPO = {"investimento": "1.000", "fluxos": ["500", "400", "300", "100"]}

    def test_taxa_informada(self) -> None:
        r = sw.rota_exemplo(None, {"projeto": {**self.CORPO, "taxa": "10"}})
        self.assertAlmostEqual(r["avaliacao_projeto"]["vpl"], 78.82, places=2)

    def test_taxa_vazia_usa_wacc(self) -> None:
        r = sw.rota_exemplo(None, {"projeto": {**self.CORPO, "taxa": ""}})
        self.assertAlmostEqual(r["avaliacao_projeto"]["taxa"], 0.1573, places=4)
        self.assertEqual(r["avaliacao_projeto"]["origem_taxa"], "WACC")
        self.assertLess(r["avaliacao_projeto"]["vpl"], 0)

    def test_validacoes(self) -> None:
        casos = [
            ({"investimento": "1.000", "fluxos": []}, "Informe de 1 a 20 fluxos anuais."),
            ({"investimento": "1.000", "fluxos": ["500", "x"]}, "Fluxo do ano 2 inválido: 'x'."),
            ({"investimento": "0", "fluxos": ["500"]}, "Investimento inicial deve ser maior que zero."),
        ]
        for projeto, mensagem in casos:
            with self.subTest(projeto=projeto):
                with self.assertRaises(sw.ErroRequisicao) as ctx:
                    sw.rota_exemplo(None, {"projeto": projeto})
                self.assertEqual(str(ctx.exception), mensagem)

    def test_sem_wacc_exige_taxa(self) -> None:
        corpo = {"dados": auxiliar.dict_de(mercado={"beta": None}), "projeto": {**self.CORPO, "taxa": ""}}
        with self.assertRaises(sw.ErroRequisicao) as ctx:
            sw.rota_analisar_dados(None, corpo)
        self.assertTrue(str(ctx.exception).startswith(
            "Informe a taxa de desconto: o WACC não pôde ser calculado"))


if __name__ == "__main__":
    unittest.main()
