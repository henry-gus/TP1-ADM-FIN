"""VPL, TIR, paybacks, índice de lucratividade e recomendação."""

from __future__ import annotations

import unittest

try:
    from tests import auxiliar  # noqa: F401  (ajusta o caminho de importação)
except ImportError:
    import auxiliar  # noqa: F401

import avaliacao_investimentos as ai

# Projeto S de Brigham & Ehrhardt (Financial Management: Theory and Practice, orçamento de capital)
PROJETO_S = [-1000, 500, 400, 300, 100]


class TestProjetoS(unittest.TestCase):
    def test_metricas(self) -> None:
        self.assertAlmostEqual(ai.vpl(0.10, PROJETO_S), 78.82, places=2)
        taxa, motivo = ai.tir(PROJETO_S)
        self.assertAlmostEqual(taxa, 0.1449, places=4)
        self.assertIsNone(motivo)
        self.assertAlmostEqual(ai.payback(PROJETO_S), 2.33, places=2)
        self.assertAlmostEqual(ai.payback(PROJETO_S, 0.10), 2.95, places=2)
        self.assertAlmostEqual(ai.indice_lucratividade(0.10, PROJETO_S), 1.079, places=3)

    def test_avaliar_projeto(self) -> None:
        r = ai.avaliar_projeto(ai.Projeto(1000, [500, 400, 300, 100], 0.10), None)
        self.assertEqual(r["recomendacao"], "aceitar")
        self.assertEqual(r["origem_taxa"], "informada")
        self.assertEqual(r["fluxos"], PROJETO_S)
        self.assertEqual([linha["ano"] for linha in r["tabela"]], [0, 1, 2, 3, 4])
        for chave in ("ano", "fluxo", "fluxo_descontado", "acumulado", "acumulado_descontado"):
            self.assertIn(chave, r["tabela"][0])
        self.assertAlmostEqual(r["tabela"][-1]["acumulado_descontado"], r["vpl"])
        self.assertAlmostEqual(r["tabela"][-1]["acumulado"], 300)


class TestCasosLimite(unittest.TestCase):
    def test_nao_recuperado(self) -> None:
        fluxos = [-1000, 100, 100]
        self.assertIsNone(ai.payback(fluxos))
        r = ai.avaliar_projeto(ai.Projeto(1000, [100, 100], 0.10), None)
        self.assertIsNone(r["payback_simples"])
        self.assertTrue(any("não recuperado no horizonte" in a for a in r["avisos"]))

    def test_multiplas_tirs(self) -> None:
        self.assertEqual(ai.trocas_de_sinal([-100, 230, -132]), 2)
        r = ai.avaliar_projeto(ai.Projeto(100, [230, -132], 0.15), None)
        self.assertTrue(any("múltiplas TIRs" in a and "VPL" in a for a in r["avisos"]))

    def test_sem_troca_de_sinal(self) -> None:
        for fluxos in ([0, 100, 100], [-100, -50, -10]):
            taxa, motivo = ai.tir(fluxos)
            self.assertIsNone(taxa)
            self.assertEqual(motivo, "fluxos sem troca de sinal")

    def test_taxa_padrao_e_wacc(self) -> None:
        r = ai.avaliar_projeto(ai.Projeto(1000, [500, 400, 300, 100]), 0.1573)
        self.assertEqual(r["origem_taxa"], "WACC")
        self.assertAlmostEqual(r["taxa"], 0.1573)
        with self.assertRaises(ValueError) as ctx:
            ai.avaliar_projeto(ai.Projeto(1000, [500]), None)
        self.assertIn("Informe a taxa de desconto", str(ctx.exception))

    def test_validacoes(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            ai.Projeto(0, [100])
        self.assertEqual(str(ctx.exception), "Investimento inicial deve ser maior que zero.")
        for fluxos in ([], [10] * 21):
            with self.assertRaises(ValueError) as ctx:
                ai.Projeto(100, fluxos)
            self.assertEqual(str(ctx.exception), "Informe de 1 a 20 fluxos anuais.")
        with self.assertRaises(ValueError):
            ai.Projeto(100, [50], -1)
        with self.assertRaises(ValueError):
            ai.Projeto(100, [float("inf")])

    def test_projeto_de_dict(self) -> None:
        p = ai.Projeto.de({"investimento_inicial": 1000, "fluxos": [500, 600], "taxa": 0.1})
        self.assertEqual(p.fluxos, [500, 600])

    def test_vpl_zero_e_indiferente(self) -> None:
        r = ai.avaliar_projeto(ai.Projeto(100, [110], 0.10), None)
        self.assertEqual(r["recomendacao"], "indiferente")
        r = ai.avaliar_projeto(ai.Projeto(100, [100], 0.10), None)
        self.assertEqual(r["recomendacao"], "rejeitar")


if __name__ == "__main__":
    unittest.main()
