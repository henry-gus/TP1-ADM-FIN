**UNIVERSIDADE FEDERAL DE MINAS GERAIS**  
**FACULDADE DE CIÊNCIAS ECONÔMICAS**  
**DEPARTAMENTO DE CIÊNCIAS ADMINISTRATIVAS – CAD**

Disciplina: Administração Financeira (CAD 167) · Turma: ICEX/SI  
Curso: Sistemas de Informação · Período letivo: 2º semestre de 2026  
Professor: Bruno Pérez Ferreira

# APLICAÇÃO DE ANÁLISE DE DEMONSTRAÇÕES FINANCEIRAS

**Trabalho 1**

**Autores:** Henrique Gustavo Ferreira Silva e Guilherme Novais de Souza

Belo Horizonte  
2026

## Resumo

Este trabalho apresenta o desenvolvimento de uma aplicação em Python para a análise de demonstrações financeiras de companhias abertas brasileiras. A aplicação captura o Balanço Patrimonial, a Demonstração do Resultado do Exercício (DRE) e a Demonstração dos Fluxos de Caixa (DFC) a partir dos Dados Abertos da Comissão de Valores Mobiliários (CVM), calcula indicadores agrupados em módulos (liquidez e capital de giro, lucratividade, eficiência e decomposição DuPont, estrutura de capital e alavancagem, múltiplos de mercado e custo de capital) e gera relatórios em texto, HTML e JSON. O tema de estrutura de capital é tratado por completo: custo médio ponderado de capital (WACC) com o CAPM, graus de alavancagem operacional, financeira e combinada, análise EBIT-LPA, simulação da estrutura ótima com o beta de Hamada e ratings sintéticos, e o benefício fiscal da dívida segundo Modigliani-Miller. A aplicação também avalia projetos de investimento (VPL, TIR, paybacks e índice de lucratividade) usando o WACC como taxa de desconto, o que toca o tema de gestão de investimentos. O software foi organizado em camadas independentes (dados, cálculo e aplicação), o que permitiu oferecer três formas de uso: interface web, menu em linha de comando e biblioteca. A validação foi feita por conferência manual dos cálculos com um conjunto de dados fictício, por um exemplo de livro-texto de orçamento de capital, por uma suíte de testes automatizados e por testes de robustez com dados ausentes, divisão por zero, escalas monetárias distintas e reapresentação de demonstrações. O trabalho evidencia como conceitos de Administração Financeira podem ser operacionalizados por um sistema de informação reprodutível.

**Palavras-chave:** análise de demonstrações financeiras; estrutura de capital; WACC; orçamento de capital; dados abertos; Python.

## Sumário

1. [Introdução](#1-introdução)
2. [Fundamentação teórica](#2-fundamentação-teórica)
3. [Desenvolvimento da aplicação](#3-desenvolvimento-da-aplicação)
4. [Resultados e validação](#4-resultados-e-validação)
5. [Atendimento aos critérios do enunciado](#5-atendimento-aos-critérios-do-enunciado)
6. [Limitações e trabalhos futuros](#6-limitações-e-trabalhos-futuros)
7. [Conclusão](#7-conclusão)
8. [Referências](#referências)
- [Apêndice A – Guia de execução](#apêndice-a--guia-de-execução)
- [Apêndice B – Formato dos dados de entrada](#apêndice-b--formato-dos-dados-de-entrada)

## 1. Introdução

### 1.1 Contextualização

A análise de demonstrações financeiras permite avaliar o desempenho passado e a situação atual de uma empresa a partir de informações contábeis, apoiando decisões de crédito, investimento e gestão. Na prática, o cálculo manual dos indicadores é repetitivo e sujeito a erros, sobretudo quando se comparam várias empresas ou exercícios. Sistemas de informação reduzem esse esforço e padronizam os critérios de cálculo.

### 1.2 Problema

Como transformar os conceitos de análise de demonstrações financeiras vistos na disciplina em uma aplicação prática que obtenha dados reais, calcule os indicadores de forma consistente e produza relatórios de fácil verificação?

### 1.3 Objetivos

**Objetivo geral.** Desenvolver uma aplicação que realize a análise de demonstrações financeiras de companhias abertas, constituindo um exemplo prático de um dos temas tratados na disciplina.

**Objetivos específicos.**

- Implementar o cálculo de indicadores de liquidez, lucratividade, eficiência, estrutura de capital e múltiplos de mercado.
- Estimar o custo de capital da empresa (WACC), medir sua alavancagem e simular a estrutura de capital que minimiza o WACC.
- Comparar alternativas de financiamento (dívida × ações) pela análise EBIT-LPA.
- Avaliar projetos de investimento descontados pelo custo de capital da empresa.
- Capturar dados reais a partir de uma fonte pública e oficial (CVM).
- Tratar de forma segura dados ausentes e divisões por zero.
- Gerar relatórios em múltiplos formatos a partir da execução.
- Estruturar o software de modo que o cálculo seja independente da interface, permitindo evoluções futuras.

### 1.4 Justificativa

O enunciado do Trabalho 1 solicita uma aplicação que constitua um exemplo prático de um dos temas da primeira metade do curso (análise de demonstrações financeiras, valor do dinheiro no tempo, ou risco e retorno) e que contemple a execução, a captura de dados, a descrição nos comentários do código e a geração de relatórios. O tema escolhido foi a análise de demonstrações financeiras, por permitir o uso de dados públicos reais e por reunir conceitos centrais da disciplina. A aplicação foi depois estendida para cobrir por completo o tema de **estrutura de capital** e para tocar o tema de **gestão de investimentos**, por meio do orçamento de capital; o tema de operações financeiras não faz parte do escopo.

## 2. Fundamentação teórica

### 2.1 Demonstrações financeiras

As companhias abertas brasileiras divulgam demonstrações padronizadas, previstas na Lei nº 6.404/1976 (Lei das Sociedades por Ações) e detalhadas nos pronunciamentos do Comitê de Pronunciamentos Contábeis (CPC). Três delas fundamentam este trabalho:

- **Balanço Patrimonial (BP):** posição patrimonial em uma data, composta por ativos, passivos e patrimônio líquido.
- **Demonstração do Resultado do Exercício (DRE):** receitas, custos, despesas e resultado em um período.
- **Demonstração dos Fluxos de Caixa (DFC):** entradas e saídas de caixa, classificadas em atividades operacionais, de investimento e de financiamento.

### 2.2 Análise por índices

A análise por índices relaciona contas das demonstrações para facilitar a interpretação e a comparação no tempo e entre empresas (GITMAN, 2010). Os índices são agrupados por aspecto avaliado. A aplicação implementa os grupos descritos a seguir. Em todas as fórmulas, "Vendas" refere-se à receita líquida de vendas.

### 2.3 Indicadores implementados

#### 2.3.1 Liquidez e gestão do capital de giro

| Indicador | Fórmula | Interpretação |
|---|---|---|
| Liquidez Corrente | Ativo Circulante / Passivo Circulante | Capacidade de cobrir obrigações de curto prazo com ativos de curto prazo. Valores acima de 1 indicam ativo circulante superior ao passivo circulante. |
| Liquidez Seca | (Ativo Circulante − Estoque) / Passivo Circulante | Versão mais conservadora, que exclui os estoques por serem os ativos circulantes menos líquidos. |
| Prazo Médio de Recebimento (dias) | Contas a Receber / (Vendas / 365) | Tempo médio, em dias, para receber as vendas a prazo. Deve ser comparado ao prazo concedido e ao setor. |
| Giro do Estoque | CMV / Estoque | Número de vezes que o estoque é renovado no período. Giro maior sugere gestão de estoque mais eficiente. |

#### 2.3.2 Lucratividade e rentabilidade

| Indicador | Fórmula | Interpretação |
|---|---|---|
| Margem Bruta | Lucro Bruto / Vendas | Percentual das vendas que sobra após o custo dos produtos vendidos. |
| Margem Operacional | EBIT / Vendas | Resultado das operações, antes de juros e tributos, por unidade de venda. |
| Margem Líquida | Lucro Líquido / Vendas | Parcela das vendas que se converte em lucro após todos os custos, despesas e tributos. |
| EBITDA | EBIT + Depreciação e Amortização | Medida do resultado operacional antes de depreciação e amortização. Aproxima a geração operacional, mas não é fluxo de caixa. |

#### 2.3.3 Eficiência e decomposição DuPont

| Indicador | Fórmula | Interpretação |
|---|---|---|
| Giro do Ativo Total | Vendas / Ativo Total | Quanto a empresa vende para cada unidade monetária investida em ativos. |
| Giro dos Ativos Fixos | Vendas / Ativos Fixos | Eficiência no uso do imobilizado para gerar vendas. |
| ROA | Lucro Líquido / Ativo Total | Retorno gerado pelo conjunto de ativos. |
| ROE | Lucro Líquido / Patrimônio Líquido | Retorno obtido sobre o capital dos acionistas. |

A **análise DuPont** decompõe o ROE em três fatores, mostrando se o retorno decorre de margem, de eficiência no uso dos ativos ou de alavancagem financeira:

$$
ROE = \underbrace{\frac{\text{Lucro Líquido}}{\text{Vendas}}}_{\text{Margem Líquida}} \times \underbrace{\frac{\text{Vendas}}{\text{Ativo Total}}}_{\text{Giro do Ativo}} \times \underbrace{\frac{\text{Ativo Total}}{\text{Patrimônio Líquido}}}_{\text{Multiplicador de Capital}}
$$

Como os termos intermediários se cancelam algebricamente, o produto dos três fatores deve ser idêntico ao ROE calculado diretamente. A aplicação exibe os dois valores, e a igualdade serve como verificação interna de consistência.

#### 2.3.4 Estrutura de capital e alavancagem

| Indicador | Fórmula | Interpretação |
|---|---|---|
| Capital de Terceiros / Capital Próprio | Dívida Total / Patrimônio Líquido | Grau de dependência de recursos de terceiros em relação aos recursos dos acionistas. |
| Cobertura de Juros (TIE, *Times Interest Earned*) | EBIT / Despesas Financeiras | Quantas vezes o resultado operacional cobre as despesas financeiras. |

| Dívida Líquida | Dívida Total − Caixa | Dívida que restaria se o caixa e as aplicações fossem usados para amortizá-la. Valor negativo indica caixa líquido. |
| Dívida Líquida / EBITDA | Dívida Líquida / EBITDA | Anos de geração operacional necessários para quitar a dívida líquida; métrica usual em contratos de crédito. |
| Dívida / (Dívida + PL) | Dívida Total / (Dívida Total + PL) | Participação da dívida no capital investido, a valores contábeis. |
| Grau de Alavancagem Operacional (GAO) | Δ% EBIT / Δ% Vendas | Sensibilidade do resultado operacional a variações nas vendas, causada pelos custos fixos. |
| Grau de Alavancagem Financeira (GAF) | Δ% Lucro Líquido / Δ% EBIT | Sensibilidade do lucro a variações no EBIT, causada pelos encargos financeiros fixos. |
| Grau de Alavancagem Combinada (GAC) | GAO × GAF | Efeito conjunto: variação do lucro líquido para cada 1% de variação nas vendas. |

Nesta aplicação, **Dívida Total** corresponde aos empréstimos e financiamentos de curto e longo prazo, e **Caixa** a caixa e equivalentes mais aplicações financeiras. Outras definições (por exemplo, todo o passivo exigível) são possíveis na literatura, e a escolha altera o valor do índice.

Os graus de alavancagem são medidos pelas variações observadas entre dois exercícios, Δ% = valor atual / valor anterior − 1 (GITMAN, 2010). Quando o valor anterior é negativo ou o EBIT muda de sinal entre os anos, o número pode ser calculado, mas não tem interpretação econômica, e a aplicação avisa. Se a variação do denominador for zero, o grau é indeterminado.

#### 2.3.5 Múltiplos e avaliação de mercado

| Indicador | Fórmula | Interpretação |
|---|---|---|
| Lucro por Ação (LPA) | Lucro Líquido / Nº de Ações | Lucro atribuível a cada ação. |
| Valor Contábil por Ação (VPA) | Patrimônio Líquido / Nº de Ações | Patrimônio líquido contábil por ação. |
| Preço/Lucro (P/L) | Preço da Ação / LPA | Quantos anos de lucro atual o mercado paga pela ação. |
| Market-to-Book | Valor de Mercado do PL / Valor Contábil do PL | Relação entre o valor atribuído pelo mercado e o valor contábil. |
| Enterprise Value (EV) | Valor de Mercado do PL + Dívida Total − Caixa | Valor da empresa como um todo, incluindo a dívida e descontando o caixa. |

O valor de mercado do patrimônio líquido é calculado como preço da ação multiplicado pelo número de ações (ROSS; WESTERFIELD; JAFFE, 2015).

#### 2.3.6 Custo de capital (WACC)

O custo médio ponderado de capital é a taxa mínima que os investimentos da empresa devem render para remunerar credores e acionistas (ROSS; WESTERFIELD; JAFFE, 2015):

$$
WACC = \frac{D}{D+E}\,K_d\,(1 - t) + \frac{E}{D+E}\,K_e
$$

| Componente | Cálculo na aplicação |
|---|---|
| Custo da dívida (Kd) | Despesas financeiras / dívida média (saldo atual e do exercício anterior). O usuário pode informar um Kd de mercado, que então substitui o contábil no WACC. |
| Alíquota (t) | Alíquota efetiva = IR e CS / lucro antes dos impostos. Se o lucro antes dos impostos não for positivo ou a efetiva sair de 0% a 100%, usa-se a nominal de 34% (IRPJ de 25% + CSLL de 9%). |
| Custo do capital próprio (Ke) | CAPM: Ke = Rf + β × (prêmio de risco de mercado). Rf, β e prêmio são informados pelo usuário. |
| Pesos | E = preço × número de ações (valor de mercado); D = dívida contábil, aproximação usual do valor de mercado da dívida. Sem preço, usa-se o PL contábil, com aviso. |

O benefício fiscal da dívida aparece no fator (1 − t): os juros são dedutíveis do lucro tributável, o que reduz o custo efetivo da dívida.

#### 2.3.7 Estrutura ótima de capital

Pela proposição I de Modigliani e Miller com impostos, o valor da empresa alavancada é o valor da empresa sem dívida somado ao valor presente do benefício fiscal; com dívida perpétua, esse valor é t × D (MODIGLIANI; MILLER, 1963):

$$
V_L = V_U + t \times D
$$

Na prática, o aumento da dívida também eleva o risco do acionista e o custo da dívida. A aplicação simula esse equilíbrio pelo procedimento de Damodaran (DAMODARAN, 2012):

1. **Beta desalavancado (Hamada):** βu = βL / [1 + (1 − t) × D/E], com a estrutura atual.
2. Para cada nível D/V de 0% a 80% (passos de 10 pontos), mantendo V = D + E constante, o beta é re-alavancado, βL = βu × [1 + (1 − t) × D/E], e Ke é recalculado pelo CAPM.
3. **Kd por rating sintético:** a cobertura de juros (EBIT / despesa de juros) define um rating e um spread, e Kd = Rf + spread. Como os juros dependem do próprio Kd, a relação é resolvida por iteração (até 30 passos; em caso de ciclo entre faixas, adota-se o maior Kd, por prudência).
4. Se a cobertura for menor que 1, não há lucro para deduzir todos os juros, e a alíquota do benefício fiscal é reduzida proporcionalmente (t × cobertura).
5. O ótimo é o nível com o menor WACC.

Tabela de spreads usada (Damodaran, *Ratings, Interest Coverage Ratios and Default Spread*, empresas não financeiras de grande porte, atualização de janeiro de 2026):

| Cobertura (EBIT / juros) | Rating | Spread | Cobertura | Rating | Spread |
|---|---|---|---|---|---|
| ≥ 8,50 | AAA | 0,40% | 2,00 – 2,25 | BB | 1,84% |
| 6,50 – 8,50 | AA | 0,55% | 1,75 – 2,00 | B+ | 2,75% |
| 5,50 – 6,50 | A+ | 0,70% | 1,50 – 1,75 | B | 3,21% |
| 4,25 – 5,50 | A | 0,78% | 1,25 – 1,50 | B− | 5,09% |
| 3,00 – 4,25 | A− | 0,89% | 0,80 – 1,25 | CCC | 8,85% |
| 2,50 – 3,00 | BBB | 1,11% | 0,65 – 0,80 | CC | 12,61% |
| 2,25 – 2,50 | BB+ | 1,38% | 0,20 – 0,65 | C | 16,00% |
| | | | < 0,20 | D | 19,00% |

Como a taxa livre de risco informada em reais já embute o risco-país, os spreads são somados a ela diretamente.

#### 2.3.8 Análise EBIT-LPA

Compara o lucro por ação de duas formas de financiar um mesmo valor: emitir dívida (mais juros, mesmo número de ações) ou emitir ações (mesmos juros, mais ações). Para cada alternativa, LPA = (EBIT − J)(1 − t) / N, uma reta em função do EBIT. O **EBIT de indiferença** é aquele em que os dois LPAs se igualam (GITMAN, 2010):

$$
EBIT^* = \frac{J_1 N_2 - J_2 N_1}{N_2 - N_1}
$$

Acima de EBIT*, a dívida produz maior LPA (alavancagem financeira favorável); abaixo, as ações. Se o número de ações for o mesmo nas duas alternativas, as retas são paralelas e uma delas domina em qualquer EBIT.

#### 2.3.9 Avaliação de projetos de investimento

| Método | Definição | Critério |
|---|---|---|
| Valor presente líquido (VPL) | Σ FCₜ / (1 + k)ᵗ, com o investimento no ano 0 | Aceitar se VPL > 0 |
| Taxa interna de retorno (TIR) | Taxa que zera o VPL | Aceitar se TIR > k |
| Payback simples | Tempo para recuperar o investimento com os fluxos nominais | Comparar com um prazo máximo |
| Payback descontado | Idem, com os fluxos descontados por k | Comparar com um prazo máximo |
| Índice de lucratividade (IL) | VP dos fluxos dos anos 1..n / investimento | Aceitar se IL > 1 |

A taxa de desconto padrão k é o WACC da empresa, adequado para projetos com risco semelhante ao da empresa (BRIGHAM; EHRHARDT, 2016). Quando os fluxos trocam de sinal mais de uma vez, pode haver mais de uma TIR, e prevalece o critério do VPL. A TIR é obtida por varredura da taxa entre −99% e 1.000% seguida de bisseção, método robusto que não depende de um chute inicial.

### 2.4 Cuidados na interpretação

Indicadores isolados têm pouco significado. Recomenda-se compará-los com o histórico da própria empresa, com empresas do mesmo setor e com a política de crédito e de estoque adotada. Diferenças de critério contábil, sazonalidade e eventos não recorrentes também afetam os resultados.

## 3. Desenvolvimento da aplicação

### 3.1 Requisitos

**Requisitos funcionais**

| Código | Requisito |
|---|---|
| RF1 | Receber BP, DRE e DFC como dicionário Python, arquivo JSON ou dados da CVM |
| RF2 | Calcular os indicadores dos cinco módulos |
| RF3 | Buscar empresas por nome ou CNPJ e capturar suas demonstrações da CVM |
| RF4 | Tratar divisão por zero e dados ausentes sem interromper a execução |
| RF5 | Gerar relatório em console, texto, HTML e JSON |
| RF6 | Oferecer interface web e interface em linha de comando |
| RF7 | Incluir dados fictícios para execução imediata |
| RF8 | Calcular o custo de capital (Kd, alíquota, Ke pelo CAPM, pesos e WACC) |
| RF9 | Calcular endividamento e graus de alavancagem a partir do exercício atual e do anterior |
| RF10 | Simular a estrutura ótima de capital e o benefício fiscal da dívida |
| RF11 | Comparar dívida e ações pela análise EBIT-LPA |
| RF12 | Avaliar projetos de investimento (VPL, TIR, paybacks e IL) |

**Requisitos não funcionais**

| Código | Requisito |
|---|---|
| RNF1 | Usar apenas a biblioteca padrão do Python, sem dependências a instalar |
| RNF2 | Código documentado em português, com type hints |
| RNF3 | Separação entre captura, cálculo e interface |
| RNF4 | Mensagens de erro compreensíveis para o usuário final |
| RNF5 | Execução reprodutível: dados de entrada salvos junto ao relatório |

### 3.2 Arquitetura

O sistema é dividido em camadas com responsabilidades distintas. A camada de cálculo não conhece a origem dos dados nem a interface, o que permite reutilizá-la em qualquer contexto.

```mermaid
flowchart TD
    CVM[(Dados Abertos da CVM<br/>arquivo DFP .zip)] --> L[cvm_loader.py<br/>captura e mapeamento]
    JSON[(Arquivo JSON)] --> A
    EX[(Dados de exemplo)] --> A
    L --> A[app.py<br/>serviço e relatórios]
    C[analise_demonstracoes_financeiras.py<br/>cálculo dos indicadores] --- A
    EC[estrutura_capital.py<br/>WACC, alavancagem, EBIT-LPA,<br/>estrutura ótima] --- A
    AI[avaliacao_investimentos.py<br/>VPL, TIR, paybacks] --- A
    A --> CLI[Menu no terminal]
    A --> S[servidor_web.py<br/>API HTTP JSON]
    S --> W[web/<br/>interface no navegador]
    A --> R[(relatorios/<br/>txt, html, json)]
```

| Arquivo | Camada | Responsabilidade |
|---|---|---|
| `analise_demonstracoes_financeiras.py` | Cálculo | Estruturas de dados das demonstrações, indicadores por módulo e formatação do relatório |
| `estrutura_capital.py` | Cálculo | Custo de capital, endividamento e alavancagem, análise EBIT-LPA, simulação da estrutura ótima e Modigliani-Miller |
| `avaliacao_investimentos.py` | Cálculo | VPL, TIR, paybacks, índice de lucratividade e recomendação de um projeto |
| `cvm_loader.py` | Dados | Download com cache, busca de empresas, leitura dos CSVs da CVM e mapeamento de contas |
| `app.py` | Aplicação | API de serviço (`ResultadoAnalise`), geração de relatórios e menu no terminal |
| `servidor_web.py` | Aplicação | Servidor HTTP com rotas JSON e entrega dos arquivos da pasta `web/` |
| `web/` | Apresentação | Interface web, servida a partir de `index.html` |

### 3.3 Camada de cálculo

**Estruturas de dados.** As demonstrações são representadas por `dataclasses` (`BalancoPatrimonial`, `DRE`, `DFC`, `DadosMercado` e, opcionalmente, `ExercicioAnterior`), agrupadas em `DadosFinanceiros`. `DadosMercado` também guarda os parâmetros do custo de capital (taxa livre de risco, beta, prêmio de mercado e custo da dívida), que ficam gravados nos dados de entrada para a análise poder ser repetida. Todos os campos são opcionais. Totais como ativo circulante, ativo total, EBIT e lucro líquido podem ser informados ou derivados das contas componentes, por meio de propriedades.

**Tratamento seguro.** Funções auxiliares (`dividir`, `somar`, `subtrair`, `multiplicar`) devolvem `None` quando falta algum operando ou quando o denominador é zero. O relatório exibe `n/d` (não disponível) nesses casos. A regra evita resultados enganosos: por exemplo, o EBITDA só é calculado se o EBIT e a depreciação e amortização estiverem disponíveis.

**Indicadores.** Cada indicador é um objeto `Indicador` com nome, valor, unidade (`x`, `%`, `dias`, `R$ mil`, `R$/ação`), fórmula e, quando não pode ser calculado, o motivo (por exemplo, "sem exercício anterior" ou "informe Rf, beta e prêmio de mercado"). O analisador (`AnalisadorFinanceiro`) possui um método por módulo e um método que consolida o relatório estruturado dos módulos 1 a 6.

**Estrutura de capital e investimentos.** Os módulos `estrutura_capital.py` e `avaliacao_investimentos.py` são funções puras sobre `DadosFinanceiros`: não imprimem nem leem dados do usuário, e entradas inválidas (por exemplo, preço de emissão igual a zero) geram `ValueError` com uma mensagem que nomeia o campo. O módulo 4 recebe os novos indicadores de endividamento e alavancagem ao final, sem alterar os dois originais, e o módulo 7 reúne o custo de capital. A simulação, a análise EBIT-LPA e a avaliação de projeto aparecem como seções complementares do relatório.

**Premissas de cálculo.**

1. Saldos de fim de período, sem médias entre exercícios (exceto a dívida média do custo da dívida).
2. Ano de 365 dias no prazo médio de recebimento.
3. Giro do estoque calculado sobre o CMV; se o CMV não existir, utiliza as vendas.
4. Dívida total igual a empréstimos e financiamentos de curto e longo prazo.
5. Ativos fixos iguais ao imobilizado.
6. Valores monetários em R$ mil e número de ações em milhares.
7. Taxas guardadas em fração (0,11 = 11%) e digitadas em percentual nas interfaces. Em arquivos JSON, um valor de taxa maior que 1 é interpretado como percentual, com aviso.
8. Alíquota nominal de 34% quando a alíquota efetiva não faz sentido.

### 3.4 Camada de dados: captura na CVM

**Fonte.** O Portal de Dados Abertos da CVM disponibiliza, para as companhias abertas, o arquivo anual de Demonstrações Financeiras Padronizadas (DFP) em formato `.zip`, contendo arquivos CSV por demonstração (BPA, BPP, DRE, DFC) e por escopo (consolidado ou individual) (COMISSÃO DE VALORES MOBILIÁRIOS, 2026).

**Procedimento.**

1. O arquivo do ano é baixado uma única vez e guardado em `cache_cvm/`. Se o download falhar, o programa explica como obter o arquivo manualmente.
2. As empresas são indexadas a partir do Balanço, permitindo busca por parte do nome (sem distinção de acentos ou maiúsculas) ou por CNPJ.
3. Para a empresa escolhida, são lidas, numa única passagem pelo arquivo, as linhas do último exercício (`ORDEM_EXERC` igual a ÚLTIMO) e do anterior (PENÚLTIMO), cada um na versão mais recente do documento, para considerar eventuais reapresentações. O exercício anterior vem do próprio DFP, como comparativo reapresentado, o que evita baixar o arquivo do ano anterior e mantém os dois anos sob os mesmos critérios. Ele alimenta a dívida média do custo da dívida e os graus de alavancagem.
4. O valor de cada conta é convertido para R$ mil conforme `ESCALA_MOEDA` (unidade, mil ou milhão).
5. Os campos de custos e despesas da DRE, negativos na CVM, são convertidos em valores positivos.
6. Se a empresa não publicou demonstrações consolidadas, o programa usa as individuais e avisa o usuário.

Os arquivos são lidos linha a linha, sem carregar o conteúdo inteiro na memória.

**Mapeamento de contas.** A CVM utiliza códigos de conta padronizados, que o programa associa aos campos do cálculo:

| Campo da aplicação | Código CVM | Descrição esperada |
|---|---|---|
| Ativo Total | 1 | Ativo Total |
| Ativo Circulante | 1.01 | Ativo Circulante |
| Caixa | 1.01.01 + 1.01.02 | Caixa e equivalentes + aplicações financeiras |
| Contas a Receber | 1.01.03 | Contas a receber |
| Estoques | 1.01.04 | Estoques |
| Imobilizado | 1.02.03 | Imobilizado |
| Intangível | 1.02.04 | Intangível |
| Passivo Circulante | 2.01 | Passivo Circulante |
| Fornecedores | 2.01.02 | Fornecedores |
| Empréstimos de curto prazo | 2.01.04 | Empréstimos e financiamentos |
| Empréstimos de longo prazo | 2.02.01 | Empréstimos e financiamentos |
| Patrimônio Líquido | 2.03 | Patrimônio líquido |
| Vendas | 3.01 | Receita de venda de bens e serviços |
| CMV | 3.02 | Custo dos bens e serviços vendidos |
| Lucro Bruto | 3.03 | Resultado bruto |
| EBIT | 3.05 | Resultado antes do resultado financeiro e dos tributos |
| Despesas financeiras | 3.06.02 | Despesas financeiras |
| Lucro antes dos impostos | 3.07 | Resultado antes dos tributos sobre o lucro |
| Imposto de renda | 3.08 | IR e CSLL sobre o lucro |
| Lucro Líquido | 3.11 | Lucro/prejuízo do período |
| Fluxo operacional, de investimento e de financiamento | 6.01, 6.02, 6.03 | DFC |
| Exercício anterior: vendas, EBIT, lucro líquido, empréstimos, caixa e PL | 3.01, 3.05, 3.11, 2.01.04, 2.02.01, 1.01.01 + 1.01.02, 2.03 | Mesmas contas, linhas PENÚLTIMO |

**Depreciação e amortização.** Essa conta não possui código fixo. O programa soma as linhas de depreciação e amortização dos ajustes do lucro no DFC pelo método indireto (contas 6.01.01.xx), excluindo amortizações de custos de captação e itens financeiros. Como o resultado é uma estimativa, o relatório emite aviso, e o EBITDA fica `n/d` quando a conta não é localizada.

**Preço e número de ações.** O preço da ação não consta da DFP e é informado pelo usuário. O número de ações é obtido da CVM, considerando as ações integralizadas menos as mantidas em tesouraria, e a aplicação informa nos avisos o valor utilizado. A CVM informa a quantidade de ações em milhares; a aplicação a converte para unidades e usa milhares no cálculo de LPA, VPA e valor de mercado.

**Verificações de qualidade.** O programa emite avisos quando: (a) a descrição de uma conta-chave difere da esperada; (b) ativo total e passivo total diferem em mais de 0,5%; (c) a empresa parece ser instituição financeira, por usar plano de contas próprio; (d) alguma conta obrigatória não é encontrada; (e) o valor patrimonial por ação resulta fora do usual, o que indica possível erro de unidade no número de ações. Estoques e empréstimos ausentes são considerados iguais a zero, com aviso.

### 3.5 Camada de aplicação

O módulo `app.py` oferece uma **API de serviço** sem interação com o usuário, formada por `analisar_exemplo`, `analisar_json`, `analisar_cvm`, `analisar_dados` e `buscar_empresas`. Todas devolvem um `ResultadoAnalise`, que contém dados de entrada, indicadores por módulo, texto do relatório, fonte, avisos, os resultados da estrutura de capital (metadados do WACC, simulação e análise EBIT-LPA) e a avaliação de projeto, e que possui o método `para_dict()` para serialização em JSON. As funções de análise aceitam três argumentos nomeados opcionais: `parametros` (parâmetros de mercado), `captacao` (cenário EBIT-LPA) e `projeto`. A função `salvar_relatorios` grava os arquivos de saída.

Como a lógica não depende da interface, o menu do terminal (`app.py`) e o servidor web (`servidor_web.py`) são apenas camadas de apresentação sobre o mesmo serviço. Na linha de comando, as opções `--rf`, `--beta`, `--premio`, `--kd`, `--captacao`, `--taxa-divida`, `--preco-emissao`, `--ebit-projetado`, `--projeto` e `--taxa-projeto` dão acesso às análises novas; o menu pergunta pelos parâmetros de mercado, oferece a simulação de captação e a avaliação de projeto depois do relatório e tem uma opção para avaliar um projeto isolado.

### 3.6 Interface web

O módulo `servidor_web.py` usa `ThreadingHTTPServer` da biblioteca padrão. Ele expõe as rotas abaixo e serve os arquivos da pasta `web/`, com `index.html` como página inicial.

| Método | Rota | Função |
|---|---|---|
| GET | `/api/config` | Ano padrão do exercício |
| POST | `/api/dfp/preparar` | Inicia o download da DFP em segundo plano |
| GET | `/api/dfp/status?ano=` | Estado do download: `ausente`, `baixando`, `pronto` ou `erro` |
| GET | `/api/empresas?ano=&termo=` | Busca de empresas (mínimo de 2 caracteres) |
| POST | `/api/analisar/cvm` | Análise de uma empresa da CVM |
| POST | `/api/analisar/dados` | Análise de dados enviados no formato JSON |
| GET | `/api/analisar/exemplo` | Análise dos dados fictícios |
| POST | `/api/analisar/exemplo` | Idem, com os blocos opcionais |

As três rotas de análise aceitam os blocos opcionais `parametros`, `captacao` e `projeto`, com taxas em percentual. Ao aplicar parâmetros, cenário ou projeto, a interface reenvia a última requisição com esses blocos, de modo que todo o cálculo continua no Python e os relatórios baixados sempre coincidem com a tela.

**Relatório na interface.** O resultado é apresentado em cartões de destaque (Liquidez Corrente, Margem Líquida, ROE, EBITDA, Dívida/PL e P/L), seguidos da decomposição DuPont, com verificação automática de que o produto dos três fatores confere com o ROE calculado diretamente. Gráficos mostram a estrutura do balanço, os fluxos de caixa e as margens. Em seguida, tabelas por módulo exibem cada indicador com sua fórmula, e uma lista de avisos informa as limitações dos dados utilizados. Indicadores que não podem ser calculados aparecem como `n/d`, com o motivo indicado. A seção **Estrutura de Capital** traz o formulário de parâmetros de mercado, o cartão do WACC com seus componentes, a curva do WACC (gráfico SVG gerado sem bibliotecas, com o ponto ótimo e a estrutura atual), o benefício fiscal da dívida e a análise EBIT-LPA, com o gráfico das duas retas e o ponto de indiferença. A seção **Avaliação de Projetos** recebe o investimento e os fluxos, sugere o WACC como taxa e mostra VPL, TIR, paybacks, IL, a recomendação e a tabela ano a ano.

**Decisões de projeto.**

- O download roda em uma *thread* separada, para a interface exibir o progresso sem travar.
- As entradas são validadas (ano entre 2010 e o ano seguinte ao padrão, números positivos, corpo de requisição limitado a 2 MB), e erros retornam JSON com a chave `erro` e status HTTP apropriado.
- O acesso a arquivos estáticos é restrito à pasta `web/`, evitando a leitura de arquivos fora dela.
- O servidor escuta por padrão em `127.0.0.1`, pois se destina a uso local e acadêmico.

### 3.7 Relatórios

Cada execução pode gerar, em `relatorios/<empresa>/`, os arquivos `relatorio.txt`, `relatorio.html` (autônomo, sem recursos externos), `relatorio.json` (indicadores estruturados) e `dados_entrada.json` (dados capturados, que permitem repetir a análise sem novo download).

## 4. Resultados e validação

### 4.1 Conferência com dados fictícios

O conjunto de dados fictício da "Empresa Teste S.A." (valores em R$ mil) foi usado para conferir os cálculos manualmente. Os valores abaixo coincidem com os produzidos pela aplicação.

**Dados de partida:** Ativo Circulante 620.000; Estoques 200.000; Contas a Receber 280.000; Imobilizado 700.000; Ativo Total 1.500.000; Passivo Circulante 400.000; Dívida Total 520.000 (120.000 de curto prazo e 400.000 de longo prazo); Patrimônio Líquido 600.000; Caixa 120.000; Vendas 2.000.000; CMV 1.200.000; EBIT 350.000; Depreciação e Amortização 90.000; Despesas Financeiras 70.000; Lucro Líquido 184.800; 100.000 mil ações a R$ 18,00.

| Indicador | Cálculo manual | Resultado |
|---|---|---|
| Liquidez Corrente | 620.000 / 400.000 | 1,55x |
| Liquidez Seca | (620.000 − 200.000) / 400.000 | 1,05x |
| Prazo Médio de Recebimento | 280.000 / (2.000.000 / 365) | 51,1 dias |
| Giro do Estoque | 1.200.000 / 200.000 | 6,00x |
| Margem Bruta | 800.000 / 2.000.000 | 40,00% |
| Margem Operacional | 350.000 / 2.000.000 | 17,50% |
| Margem Líquida | 184.800 / 2.000.000 | 9,24% |
| EBITDA | 350.000 + 90.000 | R$ 440.000 mil |
| Giro do Ativo Total | 2.000.000 / 1.500.000 | 1,33x |
| Giro dos Ativos Fixos | 2.000.000 / 700.000 | 2,86x |
| ROA | 184.800 / 1.500.000 | 12,32% |
| ROE | 184.800 / 600.000 | 30,80% |
| DuPont | 9,24% × 1,33 × 2,50 | 30,80% (igual ao ROE) |
| Capital de Terceiros / Próprio | 520.000 / 600.000 | 0,87x |
| Cobertura de Juros (TIE) | 350.000 / 70.000 | 5,00x |
| LPA | 184.800 / 100.000 | R$ 1,85 |
| VPA | 600.000 / 100.000 | R$ 6,00 |
| P/L | 18,00 / 1,848 | 9,74x |
| Market-to-Book | 1.800.000 / 600.000 | 3,00x |
| Enterprise Value | 1.800.000 + 520.000 − 120.000 | R$ 2.200.000 mil |

Para a estrutura de capital, o exemplo traz também: lucro antes dos impostos de 280.000; exercício anterior com vendas de 1.800.000, EBIT de 300.000, lucro líquido de 150.000, dívida de 480.000, caixa de 100.000 e PL de 540.000; e os parâmetros Rf = 11%, β = 1,2 e prêmio de mercado = 5,5%.

| Indicador | Cálculo manual | Resultado |
|---|---|---|
| Kd | 70.000 / ((520.000 + 480.000) / 2) | 14,00% |
| Alíquota efetiva | 95.200 / 280.000 | 34,00% |
| Kd após impostos | 14% × (1 − 0,34) | 9,24% |
| Ke | 11% + 1,2 × 5,5% | 17,60% |
| E | 18,00 × 100.000 | R$ 1.800.000 mil |
| D/V | 520.000 / 2.320.000 | 22,41% |
| WACC | 22,41% × 9,24% + 77,59% × 17,60% | 15,73% |
| Dívida Líquida | 520.000 − 120.000 | R$ 400.000 mil |
| Dívida Líquida / EBITDA | 400.000 / 440.000 | 0,91x |
| Dívida / (Dívida + PL) | 520.000 / 1.120.000 | 46,43% |
| GAO | (350/300 − 1) / (2.000/1.800 − 1) | 1,50x |
| GAF | (184,8/150 − 1) / (350/300 − 1) | 1,39x |
| GAC | 1,50 × 1,392 | 2,09x |
| Beta desalavancado | 1,2 / (1 + 0,66 × 520/1.800) | 1,0078 |
| Estrutura ótima | tabela de 0% a 80% | D/V = 70%, WACC ≈ 14,09% |
| Benefício fiscal (MM) | 0,34 × 520.000 | R$ 176.800 mil (VU = R$ 2.143.200 mil) |
| EBIT-LPA (captação de 300.000: dívida a 15% ou ações a R$ 15) | (115.000 × 120.000 − 70.000 × 100.000) / 20.000 | EBIT* = R$ 340.000 mil, LPA* = R$ 1,49; no EBIT atual, dívida R$ 1,55 > ações R$ 1,54 |

A simulação da estrutura ótima produz a curva abaixo (WACC em função de D/V). O mínimo é interior (70%); entre 50% e 70% há um pequeno "dente" causado pela mudança discreta de rating (BB+ → B+ → B), comportamento esperado do método.

| D/V | 0% | 10% | 20% | 30% | 40% | 50% | 60% | 70% | 80% |
|---|---|---|---|---|---|---|---|---|---|
| Rating | — | AAA | AA | A | A− | BB+ | B+ | B | CCC |
| WACC | 16,54% | 16,01% | 15,49% | 15,01% | 14,53% | 14,19% | 14,26% | **14,09%** | 16,99% |

Note que o WACC simulado em 20% (15,49%) difere do WACC calculado na estrutura atual (15,73%): na simulação o Kd vem da tabela de ratings (Rf + spread = 11,55%), e no cálculo vem das demonstrações (14,00%).

**Avaliação de projetos.** O Projeto S de Brigham e Ehrhardt (investimento de 1.000 e fluxos de 500, 400, 300 e 100, a 10%) foi usado como referência de livro-texto. A aplicação reproduz os valores publicados: VPL de 78,82, TIR de 14,49%, payback de 2,33 anos, payback descontado de 2,95 anos e IL de 1,08, com recomendação de aceitar. Descontado pelo WACC da empresa fictícia (15,73%), o mesmo projeto tem VPL de −19,95 e é rejeitado, o que ilustra a importância de usar a taxa adequada ao risco.

**Testes automatizados.** As conferências acima estão codificadas em uma suíte de testes com o `unittest` da biblioteca padrão (`python -m unittest discover -s tests`). Ela cobre também casos-limite (empresa sem dívida, sem preço da ação, com PL negativo, com lucro antes dos impostos negativo, sem exercício anterior, com vendas iguais nos dois anos, fluxos com múltiplas TIRs ou que não recuperam o investimento), a leitura dos dois exercícios em um arquivo da CVM sintético, a validação das rotas do servidor e a **compatibilidade**: os indicadores originais dos módulos 1 a 6 são comparados com uma linha de base gravada antes das extensões, garantindo que nenhum valor existente mudou.

### 4.2 Testes de robustez da captura

A cadeia de captura foi testada com um arquivo `.zip` sintético, construído com a mesma estrutura de nomes de arquivos e de colunas dos CSVs da CVM. Os cenários verificados e os resultados observados foram:

| Cenário | Resultado |
|---|---|
| Empresa com dados em escala "MIL" e em "UNIDADE" | Valores convertidos corretamente para R$ mil |
| Linhas do exercício anterior (PENÚLTIMO) | Lidas separadamente, como exercício anterior; sem elas, os graus de alavancagem ficam `n/d`, com aviso |
| Mais de uma versão do documento | Utilizada a versão mais recente |
| Amortização de custos de captação no DFC | Excluída da depreciação e amortização |
| Custos e despesas negativos na DRE | Convertidos em valores positivos |
| Empresa com plano de contas de instituição financeira | Aviso emitido; indicadores indisponíveis aparecem como `n/d` |
| Dados vazios ou denominadores iguais a zero | Execução sem erros, com `n/d` nos indicadores afetados |
| Empresa inexistente ou termo ambíguo | Mensagem de erro clara, sem interrupção abrupta |
| Falha no download | Mensagem com instrução de download manual e uso de `--zip` ou `cache_cvm/` |

Esses testes comprovam a lógica de leitura e de mapeamento. A captura a partir do servidor da CVM foi demonstrada com dados reais no estudo de caso da seção 4.3.

### 4.3 Estudo de caso: Vale S.A.

Para demonstrar a captura de dados reais, a aplicação foi executada pela interface web com a Vale S.A., companhia aberta do setor de mineração. Por não ser instituição financeira, a empresa é adequada aos indicadores implementados. O relatório gerado foi exportado em PDF a partir do navegador.

#### 4.3.1 Parâmetros da execução

| Item | Valor |
|---|---|
| Empresa | Vale S.A. |
| Exercício | Encerrado em 31/12/2025 |
| Fonte dos dados | CVM, DFP 2025 |
| Escopo | Demonstrações consolidadas |
| Unidade monetária | R$ mil |
| Preço da ação | R$ 71,96 (cotação de 30/12/2025) |
| Número de ações | 4.268.779 mil em circulação (4.539.007 mil integralizadas menos 270.228 mil em tesouraria), obtido da CVM |
| Execução | Interface web local, em 05/10/2026 |

A aplicação emitiu dois avisos: a depreciação e amortização foi estimada pela soma das linhas correspondentes do DFC, e o número de ações foi obtido da CVM.

#### 4.3.2 Indicadores calculados

**Liquidez e gestão de capital de giro**

| Indicador | Resultado |
|---|---|
| Liquidez Corrente | 1,15x |
| Liquidez Seca | 0,78x |
| Prazo Médio de Recebimento | 21,6 dias |
| Giro do Estoque | 4,25x |

**Lucratividade e rentabilidade**

| Indicador | Resultado |
|---|---|
| Margem Bruta | 34,98% |
| Margem Operacional | 14,97% |
| Margem Líquida | 5,53% |
| EBITDA | R$ 49.275.000 mil (R$ 49,28 bi) |

**Eficiência e decomposição DuPont**

| Indicador | Resultado |
|---|---|
| Giro do Ativo Total | 0,45x |
| Giro dos Ativos Fixos | 0,89x |
| ROA | 2,48% |
| ROE | 6,25% |
| DuPont: Margem Líquida × Giro do Ativo × Multiplicador de Capital | 5,53% × 0,45x × 2,52x = 6,25% |

O produto dos três fatores confere com o ROE calculado diretamente, o que a própria aplicação verifica e sinaliza no relatório.

**Estrutura de capital e alavancagem**

| Indicador | Resultado |
|---|---|
| Capital de Terceiros / Capital Próprio | 0,55x |
| Cobertura de Juros (TIE) | 3,96x |
| Dívida Líquida | R$ 61.828.000 mil (R$ 61,83 bi) |
| Dívida Líquida / EBITDA | 1,25x |
| Dívida / (Dívida + PL) | 35,38% |
| Grau de Alavancagem Operacional (GAO) | −11,50x |
| Grau de Alavancagem Financeira (GAF) | 1,44x |
| Grau de Alavancagem Combinada (GAC) | −16,61x |

Os graus de alavancagem comparam 2025 com 2024 (exercício anterior lido do mesmo DFP): vendas de R$ 213,60 bi contra R$ 206,01 bi (+3,7%), EBIT de R$ 31,97 bi contra R$ 55,46 bi (−42,4%) e lucro líquido de R$ 11,81 bi contra R$ 30,43 bi (−61,2%).

**Múltiplos e avaliação de mercado**

| Indicador | Resultado |
|---|---|
| Lucro por Ação (LPA) | R$ 2,77 |
| Valor Contábil por Ação (VPA) | R$ 44,26 |
| Preço/Lucro (P/L) | 26,01x |
| Market-to-Book | 1,63x |
| Valor de Mercado do PL | R$ 307,18 bi |
| Enterprise Value (EV) | R$ 369,01 bi |

#### 4.3.3 Estrutura patrimonial e fluxos de caixa

| Grupo do balanço | Valor (R$ bi) | Participação |
|---|---|---|
| Ativo Circulante | 100,65 | 21% do ativo |
| Ativo Não Circulante | 375,45 | 79% do ativo |
| **Ativo Total** | **476,10** | 100% |
| Passivo Circulante | 87,32 | 18% do total |
| Passivo Não Circulante | 199,85 | 42% do total |
| Patrimônio Líquido | 188,93 | 40% do total |

| Fluxo de caixa | Valor (R$ mil) |
|---|---|
| Operacional | 48.765.000 |
| Investimento | −38.463.000 |
| Financiamento | 1.239.000 |
| **Variação líquida de caixa** | **11.541.000** |

#### 4.3.4 Conferência com fontes externas

Os resultados foram comparados com valores publicados por agregadores de dados de mercado, que também se baseiam em balanços divulgados à CVM.

| Item | Aplicação | Referência externa | Fonte |
|---|---|---|---|
| Lucro líquido de 2025 | R$ 11,81 bi (ROE × Patrimônio Líquido) | R$ 11,8 bi | MEUS DIVIDENDOS |
| ROE | 6,25% | 6,3% | MEUS DIVIDENDOS |
| Margem líquida | 5,53% | 5,5% | MEUS DIVIDENDOS |
| Fluxo de caixa de investimento | −R$ 38,46 bi | −R$ 38,46 bi | HG BRASIL |

Os valores coincidem dentro do arredondamento das fontes. Também há consistência interna: a soma dos três fluxos de caixa (48.765.000 − 38.463.000 + 1.239.000) resulta na variação líquida de 11.541.000, o Passivo Circulante, o Passivo Não Circulante e o Patrimônio Líquido somam o Ativo Total, e o produto dos fatores DuPont reproduz o ROE. Por serem fontes secundárias, recomenda-se confrontar os valores finais com as demonstrações divulgadas no site de Relações com Investidores da companhia.

#### 4.3.5 Análise dos resultados

**Liquidez.** A liquidez corrente de 1,15x indica que o ativo circulante supera em 15% as obrigações de curto prazo. A liquidez seca de 0,78x, inferior a 1, mostra que, desconsiderados os estoques, os ativos circulantes não cobrem integralmente o passivo circulante. Isso sugere dependência da conversão de estoques e da geração de caixa operacional para honrar compromissos de curto prazo. O prazo médio de recebimento de 21,6 dias é curto, e o giro do estoque de 4,25x indica renovação do estoque pouco mais de quatro vezes ao ano.

**Rentabilidade.** A margem bruta de 34,98% e a margem operacional de 14,97% indicam resultado operacional expressivo. A margem líquida, de 5,53%, é bem inferior, porque entre o EBIT e o lucro líquido incidem resultado financeiro, tributos e demais itens, cuja composição não foi detalhada nesta análise. O EBITDA de R$ 49,28 bi é próximo do fluxo de caixa operacional de R$ 48,77 bi, o que sugere boa conversão do resultado operacional em caixa.

**Eficiência e decomposição DuPont.** O giro do ativo total de 0,45x e o giro dos ativos fixos de 0,89x refletem uma atividade intensiva em capital, em que o ativo não circulante representa 79% do ativo. O ROA de 2,48% decorre da combinação de margem líquida moderada e baixo giro. A decomposição DuPont mostra que o ROE de 6,25% resulta de uma margem líquida de 5,53%, de um giro de 0,45x e de uma alavancagem moderada (multiplicador de 2,52x). Assim, o retorno ao acionista é limitado principalmente pelo giro e pela margem líquida, e não pela estrutura de capital.

**Estrutura de capital.** A relação entre dívida total e patrimônio líquido de 0,55x indica que a dívida financeira equivale a pouco mais da metade do capital próprio. O passivo não circulante responde por 42% do financiamento total, o que indica predomínio de recursos de longo prazo. A cobertura de juros de 3,96x mostra que o resultado operacional cobre cerca de quatro vezes as despesas financeiras. A dívida líquida equivale a 1,25 ano de EBITDA, nível confortável para o setor. O GAO negativo (−11,50x) não indica alavancagem operacional "negativa": as vendas cresceram 3,7% enquanto o EBIT caiu 42,4%, por fatores de custo e de preço que não decorrem do volume vendido. Graus de alavancagem medidos entre dois exercícios só têm leitura direta quando a variação de resultado é explicada pela variação das vendas; aqui, o valor sinaliza que a queda de resultado teve outras causas, o que pede análise das notas explicativas.

**Fluxos de caixa.** O fluxo operacional de R$ 48,77 bi financiou integralmente os investimentos de R$ 38,46 bi, e a diferença, de cerca de R$ 10,3 bi, ficou disponível antes das atividades de financiamento. O fluxo de financiamento positivo (R$ 1,24 bi) e a variação líquida de caixa de R$ 11,54 bi indicam aumento do caixa no exercício.

**Mercado.** Com o preço de R$ 71,96, o P/L de 26,01x significa que o mercado paga cerca de 26 vezes o lucro por ação de 2025. Um múltiplo elevado pode refletir expectativas de lucros maiores no futuro ou um lucro do exercício abaixo do potencial da empresa, o que só pode ser avaliado com séries históricas. O Market-to-Book de 1,63x indica que o mercado avalia o patrimônio líquido acima de seu valor contábil. O valor da firma (EV), de R$ 369,01 bi, equivale a cerca de 7,5 vezes o EBITDA do exercício, razão calculada a partir dos resultados acima.

#### 4.3.6 Observações metodológicas

- A depreciação e amortização é uma estimativa feita a partir do DFC; o EBITDA depende dela.
- O lucro líquido e o patrimônio líquido são consolidados e incluem a participação de não controladores. O ROE divulgado pela companhia ou por terceiros pode diferir por usar o patrimônio atribuível aos controladores ou saldos médios.
- Os indicadores de balanço usam saldos de fim de período.
- Os múltiplos de mercado dependem do preço de um único dia (30/12/2025) e variam com a cotação.
- Um único exercício não permite avaliar tendências. A análise ganharia consistência com a comparação de vários anos e com empresas do mesmo setor.

## 5. Atendimento aos critérios do enunciado

| Critério de avaliação | Como foi atendido |
|---|---|
| Execução da aplicação | Execução por `python servidor_web.py` ou `python app.py`. A opção de dados fictícios funciona sem internet, e o modo offline permite usar um arquivo da CVM previamente baixado. |
| Utilização de captura de dados | Módulo `cvm_loader.py`, que obtém dados reais da CVM. Também há captura por arquivo JSON e por dicionário Python. |
| Descrição nos comentários do código | Todos os módulos possuem docstrings e comentários explicativos em português, além de type hints. |
| Geração de relatórios | Relatórios em `.txt`, `.html` e `.json`, exibidos também no console e na interface web, incluindo as seções de estrutura de capital e de avaliação de projetos. |

Temas abordados: **análise de demonstrações financeiras** (tema principal), **estrutura de capital** (completo: custo de capital, alavancagem, EBIT-LPA, estrutura ótima e Modigliani-Miller) e **gestão de investimentos** (orçamento de capital: VPL, TIR, paybacks e IL). **Operações financeiras** não fazem parte do escopo.

## 6. Limitações e trabalhos futuros

**Limitações.**

- Somente demonstrações anuais (DFP); as trimestrais (ITR) não são tratadas.
- Instituições financeiras não são suportadas, em razão do plano de contas específico.
- A depreciação e amortização é estimada a partir do DFC, e depende da forma como a empresa apresenta essa informação.
- Indicadores calculados sobre saldos de fim de período, sem médias.
- O preço da ação depende de informação manual.
- O Kd contábil (despesas financeiras / dívida média) é ruidoso em empresas reais, porque a conta de despesas financeiras inclui variação cambial, derivativos e juros de arrendamento; em testes com a DFP de 2025, ele variou de 0,9% (Petrobras) a 184% (Ambev). A aplicação avisa quando o valor sai da faixa de 2% a 40% a.a. e permite informar o Kd.
- Os parâmetros do CAPM (taxa livre de risco, beta e prêmio de mercado) não constam da DFP e precisam ser informados pelo usuário.
- A dívida contábil é usada como aproximação do valor de mercado da dívida.
- Na simulação da estrutura ótima, o valor da empresa é mantido constante, a tabela de spreads é a de Damodaran para empresas americanas não financeiras de grande porte (janeiro de 2026) e a curva não é estritamente convexa, por causa das faixas discretas de rating. O Kd simulado difere do Kd contábil.
- Os graus de alavancagem usam apenas dois exercícios e perdem interpretação quando o resultado muda de sinal.
- Empresas financeiras continuam fora do escopo.

**Trabalhos futuros.**

- Comparação de múltiplos exercícios e de empresas do mesmo setor, com gráficos de evolução.
- Suporte a demonstrações trimestrais (ITR) e a indicadores calculados sobre médias.
- Obtenção automática de cotações e do número de ações.
- Integração contínua para a suíte de testes.
- Estimativa automática do beta (regressão contra o índice de mercado) e do Kd a partir das notas explicativas.
- Implementação de outros temas da disciplina (por exemplo, operações financeiras) como novos módulos.

## 7. Conclusão

O trabalho atingiu o objetivo de construir uma aplicação que opera os conceitos de análise de demonstrações financeiras sobre dados reais. A organização em camadas separou a captura, o cálculo e a apresentação, o que tornou possível oferecer interface web, linha de comando e biblioteca sem duplicar regras de negócio. A conferência manual dos indicadores, o exemplo de livro-texto de orçamento de capital, a suíte de testes automatizados e os testes de robustez indicam que o cálculo e o tratamento de dados ausentes se comportam conforme o esperado. O estudo de caso com a Vale S.A. (exercício de 2025) demonstrou o funcionamento de ponta a ponta, da captura na CVM ao relatório, com resultados coerentes com fontes externas. A extensão para estrutura de capital mostrou que o WACC depende fortemente de parâmetros que não constam das demonstrações (beta, prêmio de risco e um custo da dívida confiável), e que a estrutura ótima resulta de um equilíbrio entre o benefício fiscal e o aumento do risco, que a simulação torna visível. As limitações identificadas, em especial a estimativa da depreciação e amortização e a ausência de dados trimestrais, apontam caminhos claros de evolução. Do ponto de vista da disciplina, a experiência mostrou que a interpretação dos indicadores depende do contexto da empresa e de suas definições contábeis, o que reforça a necessidade de analisá-los em conjunto e com senso crítico.

## Referências

BRIGHAM, Eugene F.; EHRHARDT, Michael C. **Financial management:** theory and practice. 15. ed. Boston: Cengage Learning, 2016.

BRASIL. **Lei nº 6.404, de 15 de dezembro de 1976.** Dispõe sobre as Sociedades por Ações. Brasília, DF: Presidência da República, 1976.

COMISSÃO DE VALORES MOBILIÁRIOS (Brasil). **Dados Abertos CVM:** Companhias abertas – Demonstrações Financeiras Padronizadas (DFP). Disponível em: https://dados.cvm.gov.br/. Acesso em: 5 out. 2026.

COMITÊ DE PRONUNCIAMENTOS CONTÁBEIS. **Pronunciamento Técnico CPC 26 (R1):** Apresentação das Demonstrações Contábeis. Brasília, DF: CPC, 2011.

COMITÊ DE PRONUNCIAMENTOS CONTÁBEIS. **Pronunciamento Técnico CPC 03 (R2):** Demonstração dos Fluxos de Caixa. Brasília, DF: CPC, 2010.

DAMODARAN, Aswath. **Investment valuation:** tools and techniques for determining the value of any asset. 3. ed. Hoboken: Wiley, 2012.

DAMODARAN, Aswath. **Ratings, interest coverage ratios and default spread.** Atualização de janeiro de 2026. Disponível em: https://pages.stern.nyu.edu/~adamodar/. Acesso em: 18 nov. 2026.

GITMAN, Lawrence J. **Princípios de administração financeira.** 12. ed. São Paulo: Pearson Prentice Hall, 2010.

HG BRASIL. **Vale (VALE3).** Disponível em: https://hgbrasil.com/finance/tickers/B3:VALE3. Acesso em: 5 out. 2026.

MEUS DIVIDENDOS. **VALE3: indicadores e resumo financeiro.** Disponível em: https://www.meusdividendos.com/acao/VALE3. Acesso em: 5 out. 2026.

HAMADA, Robert S. The effect of the firm's capital structure on the systematic risk of common stocks. **The Journal of Finance**, v. 27, n. 2, p. 435-452, 1972.

MODIGLIANI, Franco; MILLER, Merton H. Corporate income taxes and the cost of capital: a correction. **The American Economic Review**, v. 53, n. 3, p. 433-443, 1963.

ROSS, Stephen A.; WESTERFIELD, Randolph W.; JAFFE, Jeffrey F. **Administração financeira.** 10. ed. Porto Alegre: AMGH, 2015.

## Apêndice A – Guia de execução

**Requisitos:** Python 3.8 ou superior; nenhum pacote adicional.

```bash
git clone https://github.com/henry-gus/TP1-ADM-FIN.git
cd TP1-ADM-FIN

python servidor_web.py                     # interface web em http://127.0.0.1:8000
python app.py                              # menu no terminal
python app.py --exemplo                    # dados fictícios, sem internet
python app.py --empresa "nome" --ano 2025  # dados reais da CVM
python app.py --json dados.json            # dados de um arquivo JSON

# Estrutura de capital e projetos (taxas em %, valores em R$ mil)
python app.py --empresa "vale s.a" --preco 55 --rf 13,75 --beta 1,1 --premio 6
python app.py --exemplo --captacao 300.000 --taxa-divida 15 --preco-emissao 15
python app.py --exemplo --projeto "1.000;500;400;300;100" --taxa-projeto 10

python -m unittest discover -s tests       # testes automatizados
```

**Modo offline.** Copie o arquivo `dfp_cia_aberta_AAAA.zip`, obtido em https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/, para a pasta `cache_cvm/`, ou use a opção `--zip`.

## Apêndice B – Formato dos dados de entrada

Arquivo JSON com as seções `balanco`, `dre`, `dfc`, `mercado` e, opcionalmente, `exercicio_anterior`. Valores monetários em R$ mil; `numero_acoes` em milhares; taxas em fração. Campos omitidos resultam em `n/d`.

| Seção | Campos |
|---|---|
| `balanco` | `caixa`, `contas_receber`, `estoques`, `outros_ativos_circulantes`, `ativo_circulante`, `imobilizado`, `intangivel`, `outros_ativos_nao_circulantes`, `ativo_nao_circulante`, `ativo_total`, `fornecedores`, `emprestimos_cp`, `outros_passivos_circulantes`, `passivo_circulante`, `emprestimos_lp`, `outros_passivos_nao_circulantes`, `patrimonio_liquido` |
| `dre` | `vendas`, `cmv`, `lucro_bruto`, `despesas_operacionais`, `depreciacao_amortizacao`, `ebit`, `despesas_financeiras`, `imposto_renda`, `lucro_liquido`, `lucro_antes_impostos` |
| `dfc` | `fluxo_operacional`, `fluxo_investimento`, `fluxo_financiamento` |
| `mercado` | `preco_acao`, `numero_acoes`, `taxa_livre_risco`, `beta`, `premio_risco_mercado`, `custo_divida` |
| `exercicio_anterior` (opcional) | `vendas`, `ebit`, `lucro_liquido`, `emprestimos_cp`, `emprestimos_lp`, `caixa`, `patrimonio_liquido` |

Campos de totais (`ativo_circulante`, `ativo_nao_circulante`, `ativo_total`, `passivo_circulante`, `lucro_bruto`, `ebit`, `lucro_liquido`, `lucro_antes_impostos`) são opcionais: se omitidos, são calculados a partir das contas componentes.

Exemplo completo: veja a seção 5.2 do [README](README.md).
