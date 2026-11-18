"""Custo de capital, alavancagem, EBIT-LPA e simulação da estrutura ótima."""

from __future__ import annotations

import math
import unittest

try:
    from tests import auxiliar
except ImportError:  # executado com a pasta tests/ no caminho de importação
    import auxiliar

import app
import estrutura_capital as ec


def por_nome(indicadores):
    return {i.nome: i for i in indicadores}


class TestCustoCapital(unittest.TestCase):
    def test_valores_do_exemplo(self) -> None:
        inds, meta, _ = ec.custo_capital(auxiliar.dados_exemplo())
        v = {n: i.valor for n, i in por_nome(inds).items()}
        self.assertEqual(list(v), [
            "Custo da Dívida (Kd)", "Alíquota Efetiva de IR/CS", "Alíquota Aplicada", "Kd após Impostos",
            "Custo do Capital Próprio (Ke)", "Valor do Capital Próprio (E)", "Dívida (D)",
            "Peso da Dívida (D/V)", "Peso do Capital Próprio (E/V)", "WACC"])
        self.assertAlmostEqual(v["Custo da Dívida (Kd)"], 0.14, places=6)
        self.assertAlmostEqual(v["Alíquota Efetiva de IR/CS"], 0.34, places=6)
        self.assertAlmostEqual(v["Alíquota Aplicada"], 0.34, places=6)
        self.assertAlmostEqual(v["Kd após Impostos"], 0.0924, places=6)
        self.assertAlmostEqual(v["Custo do Capital Próprio (Ke)"], 0.176, places=6)
        self.assertAlmostEqual(v["Valor do Capital Próprio (E)"], 1_800_000, places=3)
        self.assertAlmostEqual(v["Dívida (D)"], 520_000, places=3)
        self.assertAlmostEqual(v["Peso da Dívida (D/V)"], 0.2241, places=4)
        self.assertAlmostEqual(v["Peso do Capital Próprio (E/V)"], 0.7759, places=4)
        self.assertAlmostEqual(v["WACC"], 0.1573, places=4)
        for chave, valor in {"base_pesos": "mercado", "kd_utilizado": "contábil",
                             "origem_aliquota": "efetiva"}.items():
            self.assertEqual(meta[chave], valor)

    def test_sem_beta(self) -> None:
        inds = por_nome(ec.custo_capital(auxiliar.dados_de(mercado={"beta": None}))[0])
        for nome in ("Custo do Capital Próprio (Ke)", "WACC"):
            self.assertIsNone(inds[nome].valor)
            self.assertIn("informe Rf, beta e prêmio", inds[nome].motivo)
        self.assertIsNotNone(inds["Custo da Dívida (Kd)"].valor)
        self.assertIsNotNone(inds["Alíquota Aplicada"].valor)

    def test_sem_preco_usa_pl_contabil(self) -> None:
        inds, meta, avisos = ec.custo_capital(auxiliar.dados_de(mercado={"preco_acao": None}))
        self.assertAlmostEqual(por_nome(inds)["Valor do Capital Próprio (E)"].valor, 600_000)
        self.assertEqual(meta["base_pesos"], "contábil")
        self.assertTrue(any("PL contábil" in a for a in avisos))

    def test_sem_preco_e_pl_negativo(self) -> None:
        inds = por_nome(ec.custo_capital(auxiliar.dados_de(
            mercado={"preco_acao": None}, balanco={"patrimonio_liquido": -50_000}))[0])
        for nome in ("Peso da Dívida (D/V)", "Peso do Capital Próprio (E/V)", "WACC"):
            self.assertIsNone(inds[nome].valor)
            self.assertTrue(inds[nome].motivo)

    def test_sem_divida(self) -> None:
        dados = auxiliar.dados_de(balanco={"emprestimos_cp": 0, "emprestimos_lp": 0})
        inds, _, avisos = ec.custo_capital(dados)
        inds = por_nome(inds)
        self.assertIsNone(inds["Custo da Dívida (Kd)"].valor)
        self.assertIn("sem dívida", inds["Custo da Dívida (Kd)"].motivo)
        self.assertEqual(inds["Peso da Dívida (D/V)"].valor, 0)
        self.assertAlmostEqual(inds["WACC"].valor, inds["Custo do Capital Próprio (Ke)"].valor)
        self.assertTrue(any("100% capital próprio" in a for a in avisos))

    def test_lair_negativo_usa_aliquota_nominal(self) -> None:
        dados = auxiliar.dados_de(dre={"lucro_antes_impostos": -10_000})
        inds, meta, avisos = ec.custo_capital(dados)
        self.assertAlmostEqual(por_nome(inds)["Alíquota Aplicada"].valor, 0.34)
        self.assertEqual(meta["origem_aliquota"], "nominal 34%")
        self.assertTrue(avisos)

    def test_avisos_de_kd_contabil(self) -> None:
        _, _, avisos = ec.custo_capital(auxiliar.dados_de(dre={"despesas_financeiras": 900_000}))
        self.assertTrue(any("implausível" in a for a in avisos))
        _, _, avisos = ec.custo_capital(auxiliar.dados_de(dre={"despesas_financeiras": 5_000}))
        self.assertTrue(any("Atenção" in a and "2%" in a for a in avisos))

    def test_kd_informado(self) -> None:
        inds, meta, _ = ec.custo_capital(auxiliar.dados_de(mercado={"custo_divida": 0.12}))
        self.assertEqual(meta["kd_utilizado"], "informado")
        dv = 520_000 / 2_320_000
        esperado = dv * 0.12 * 0.66 + (1 - dv) * 0.176
        self.assertAlmostEqual(por_nome(inds)["WACC"].valor, esperado, places=9)

    def test_sem_exercicio_anterior(self) -> None:
        inds, _, avisos = ec.custo_capital(auxiliar.dados_de(exercicio_anterior=None))
        self.assertAlmostEqual(por_nome(inds)["Custo da Dívida (Kd)"].valor, 70_000 / 520_000)
        self.assertTrue(any("exercício anterior" in a for a in avisos))

    def test_normalizar_taxa_percentual(self) -> None:
        avisos = []
        self.assertAlmostEqual(ec.normalizar_taxa(11, "Taxa livre de risco", avisos), 0.11)
        self.assertEqual(len(avisos), 1)
        self.assertAlmostEqual(ec.normalizar_taxa(0.11, "Taxa livre de risco", avisos), 0.11)
        self.assertIsNone(ec.normalizar_taxa(None, "Taxa livre de risco", avisos))
        with self.assertRaises(ValueError):
            ec.normalizar_taxa(float("nan"), "Taxa livre de risco", avisos)

    def test_aplicar_parametros_sobrescreve_mercado(self) -> None:
        avisos = []
        dados = ec.aplicar_parametros(auxiliar.dados_exemplo(), {"beta": 1.5, "custo_divida": 13}, avisos)
        self.assertEqual(dados.mercado.beta, 1.5)
        self.assertAlmostEqual(dados.mercado.custo_divida, 0.13)
        self.assertEqual(dados.mercado.taxa_livre_risco, 0.11)
        self.assertTrue(avisos)


class TestEndividamentoAlavancagem(unittest.TestCase):
    def test_valores_do_exemplo(self) -> None:
        inds, _ = ec.endividamento_alavancagem(auxiliar.dados_exemplo())
        self.assertEqual([i.nome for i in inds], [
            "Dívida Líquida", "Dívida Líquida / EBITDA", "Dívida / (Dívida + PL)",
            "Grau de Alavancagem Operacional (GAO)", "Grau de Alavancagem Financeira (GAF)",
            "Grau de Alavancagem Combinada (GAC)"])
        v = [i.valor for i in inds]
        self.assertAlmostEqual(v[0], 400_000)
        self.assertAlmostEqual(v[1], 400_000 / 440_000)
        self.assertAlmostEqual(v[2], 0.4643, places=4)
        self.assertAlmostEqual(v[3], 1.50, places=6)
        self.assertAlmostEqual(v[4], 1.392, places=6)
        self.assertAlmostEqual(v[5], 2.088, places=6)

    def test_sem_exercicio_anterior(self) -> None:
        inds = por_nome(ec.endividamento_alavancagem(auxiliar.dados_de(exercicio_anterior=None))[0])
        for nome in ("Grau de Alavancagem Operacional (GAO)", "Grau de Alavancagem Financeira (GAF)",
                     "Grau de Alavancagem Combinada (GAC)"):
            self.assertIsNone(inds[nome].valor)
            self.assertIn("sem exercício anterior", inds[nome].motivo)
        self.assertIsNotNone(inds["Dívida Líquida"].valor)
        self.assertIsNotNone(inds["Dívida / (Dívida + PL)"].valor)

    def test_vendas_iguais(self) -> None:
        inds = por_nome(ec.endividamento_alavancagem(
            auxiliar.dados_de(exercicio_anterior={"vendas": 2_000_000}))[0])
        self.assertIsNone(inds["Grau de Alavancagem Operacional (GAO)"].valor)
        self.assertIn("variação das vendas igual a zero", inds["Grau de Alavancagem Operacional (GAO)"].motivo)
        self.assertIsNone(inds["Grau de Alavancagem Combinada (GAC)"].valor)

    def test_ebit_anterior_negativo(self) -> None:
        inds, avisos = ec.endividamento_alavancagem(auxiliar.dados_de(exercicio_anterior={"ebit": -50_000}))
        self.assertIsNotNone(por_nome(inds)["Grau de Alavancagem Operacional (GAO)"].valor)
        self.assertTrue(any("sem interpretação econômica" in a for a in avisos))

    def test_modulo_4_estendido_no_app(self) -> None:
        modulo = app.analisar_exemplo().modulos["4. ESTRUTURA DE CAPITAL E ALAVANCAGEM"]
        self.assertEqual(len(modulo), 8)
        self.assertEqual(modulo[0].nome, "Capital de Terceiros / Capital Próprio")
        self.assertEqual(modulo[1].nome, "Cobertura de Juros (TIE)")


class TestEbitLpa(unittest.TestCase):
    def test_indiferenca(self) -> None:
        self.assertAlmostEqual(ec.indiferenca((115_000, 100_000), (70_000, 120_000), 0.34), 340_000)
        self.assertIsNone(ec.indiferenca((115_000, 100_000), (70_000, 100_000), 0.34))

    def test_exemplo(self) -> None:
        r = ec.analise_ebit_lpa(auxiliar.dados_exemplo(), ec.CenarioCaptacao(300_000, 0.15, 15))
        self.assertAlmostEqual(r["ebit_indiferenca"], 340_000)
        self.assertAlmostEqual(r["lpa_indiferenca"], 1.485, places=3)
        lpa = {a["nome"]: a["lpa_no_ebit"] for a in r["alternativas"]}
        self.assertAlmostEqual(lpa["Dívida"], 1.551, places=3)
        self.assertAlmostEqual(lpa["Ações"], 1.54, places=3)
        self.assertEqual(r["melhor_no_ebit"], "Dívida")
        self.assertAlmostEqual(r["aliquota"], 0.34)
        self.assertEqual(r["ebit_avaliado"], 350_000)
        pontos = r["pontos_grafico"]
        self.assertEqual(len(pontos), 2)
        self.assertEqual(pontos[0]["ebit"], 0)
        self.assertAlmostEqual(pontos[1]["ebit"], 2 * 350_000)

    def test_retas_paralelas_tem_dominante(self) -> None:
        r = ec.analise_ebit_lpa(auxiliar.dados_exemplo(), ec.CenarioCaptacao(300_000, 0.15, 1e15))
        self.assertIsNone(r["ebit_indiferenca"])
        self.assertEqual(r["dominante"], "Ações")

    def test_validacoes(self) -> None:
        casos = {
            (0, 0.15, 15): "Valor a captar deve ser maior que zero.",
            (300_000, 0, 15): "Taxa da nova dívida deve ser maior que zero.",
            (300_000, 0.15, -1): "Preço de emissão deve ser maior que zero.",
        }
        for args, mensagem in casos.items():
            with self.subTest(args=args):
                with self.assertRaises(ValueError) as ctx:
                    ec.CenarioCaptacao(*args)
                self.assertEqual(str(ctx.exception), mensagem)

    def test_ebit_projetado(self) -> None:
        r = ec.analise_ebit_lpa(auxiliar.dados_exemplo(), ec.CenarioCaptacao(300_000, 0.15, 15, 500_000))
        self.assertEqual(r["ebit_avaliado"], 500_000)
        self.assertAlmostEqual(r["pontos_grafico"][1]["ebit"], 1_000_000)

    def test_sem_numero_de_acoes(self) -> None:
        r = ec.analise_ebit_lpa(auxiliar.dados_de(mercado={"numero_acoes": None}),
                                ec.CenarioCaptacao.de({"valor": 300_000, "taxa_divida": 0.15, "preco_emissao": 15}))
        self.assertIn("motivo", r)


class TestSimulacao(unittest.TestCase):
    def test_exemplo(self) -> None:
        sim = ec.simular_estrutura(auxiliar.dados_exemplo())
        pontos = sim["pontos"]
        self.assertEqual([round(p["dv"], 2) for p in pontos], [i / 10 for i in range(9)])
        bu = sim["beta_desalavancado"]
        self.assertAlmostEqual(bu, 1.0078, places=4)
        self.assertAlmostEqual(bu * (1 + 0.66 * 520_000 / 1_800_000), 1.2, places=9)
        self.assertEqual(sim["otimo"]["dv"], 0.7)
        self.assertAlmostEqual(sim["otimo"]["wacc"], 0.1409, places=4)
        self.assertEqual(sim["otimo"]["wacc"], min(p["wacc"] for p in pontos))
        zero = pontos[0]
        self.assertIsNone(zero["cobertura"])
        self.assertAlmostEqual(zero["wacc"], 0.11 + bu * 0.055)
        self.assertAlmostEqual(sim["atual"]["dv"], 520_000 / 2_320_000)

    def test_modigliani_miller(self) -> None:
        mm = ec.simular_estrutura(auxiliar.dados_exemplo())["modigliani_miller"]
        self.assertAlmostEqual(mm["valor_alavancado"], 2_320_000)
        self.assertAlmostEqual(mm["beneficio_fiscal"], 176_800)
        self.assertAlmostEqual(mm["valor_desalavancado"], 2_143_200)

    def test_tabela_de_spreads_nos_limites(self) -> None:
        self.assertEqual(ec.rating_sintetico(8.50), ("AAA", 0.0040))
        self.assertEqual(ec.rating_sintetico(8.49)[0], "AA")
        self.assertEqual(ec.rating_sintetico(0.19), ("D", 0.1900))
        self.assertEqual(ec.rating_sintetico(math.inf)[0], "AAA")

    def test_cobertura_menor_que_um_reduz_beneficio(self) -> None:
        dados = auxiliar.dados_de(dre={"despesas_operacionais": 750_000})   # EBIT = 50.000
        sim = ec.simular_estrutura(dados)
        p = sim["pontos"][-1]
        self.assertLess(p["cobertura"], 1)
        self.assertAlmostEqual(p["aliquota"], 0.34 * p["cobertura"])

    def test_pre_requisitos(self) -> None:
        self.assertIn("beta", ec.simular_estrutura(auxiliar.dados_de(mercado={"beta": None}))["faltando"])
        faltando = ec.simular_estrutura(auxiliar.dados_de(
            mercado={"preco_acao": None}, balanco={"patrimonio_liquido": -1}))["faltando"]
        self.assertTrue(any("capital próprio" in f for f in faltando))

    def test_iteracao_termina_e_adota_maior_kd_em_oscilacao(self) -> None:
        r = ec.kd_sintetico(350_000, 1_000_000, 0.11)
        self.assertLessEqual(r["iteracoes"], 30)
        # Tabela artificial em que o spread cresce com a cobertura: força um ciclo entre faixas
        tabela = ((3.0, "X", 0.10), (-math.inf, "Y", 0.01))
        r = ec.kd_sintetico(100_000, 1_000_000, 0.01, tabela=tabela)
        self.assertLessEqual(r["iteracoes"], 30)
        self.assertAlmostEqual(r["kd"], 0.11)


if __name__ == "__main__":
    unittest.main()
