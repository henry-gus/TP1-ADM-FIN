# Aplicação de Análise de Demonstrações Financeiras

**CAD 167 – Administração Financeira · Trabalho 2**
Universidade Federal de Minas Gerais · Faculdade de Ciências Econômicas · Departamento de Ciências Administrativas (CAD)
Curso de Sistemas de Informação · 2º semestre de 2026 · Professor: Bruno Pérez Ferreira

**Autores:** Henrique Gustavo Ferreira Silva e Guilherme Novais de Souza

Aplicação em Python que captura as demonstrações financeiras de companhias abertas brasileiras (Balanço Patrimonial, DRE e DFC) a partir dos Dados Abertos da CVM, calcula automaticamente os principais indicadores de análise de demonstrações financeiras, analisa a estrutura de capital da empresa (custo de capital, alavancagem, estrutura ótima e análise EBIT-LPA), avalia projetos de investimento (VPL, TIR e payback) e gera relatórios em texto, HTML e JSON. Pode ser usada por interface web, por menu em linha de comando ou como biblioteca.

> A fundamentação teórica, a arquitetura, a validação e as limitações do trabalho estão descritas em **[DOCUMENTACAO.md](DOCUMENTACAO.md)**.

## Sumário

1. [Funcionalidades](#1-funcionalidades)
2. [Estrutura do repositório](#2-estrutura-do-repositório)
3. [Requisitos e instalação](#3-requisitos-e-instalação)
4. [Como executar](#4-como-executar)
5. [Dados de entrada](#5-dados-de-entrada)
6. [Indicadores calculados](#6-indicadores-calculados)
7. [Relatórios gerados](#7-relatórios-gerados)
8. [API HTTP](#8-api-http)
9. [Uso como biblioteca](#9-uso-como-biblioteca)
10. [Limitações conhecidas](#10-limitações-conhecidas)
11. [Atendimento aos critérios de avaliação](#11-atendimento-aos-critérios-de-avaliação)
12. [Exemplo de execução: Vale S.A.](#12-exemplo-de-execução-vale-sa)
13. [Testes automatizados](#13-testes-automatizados)

## 1. Funcionalidades

- **Captura de dados reais:** baixa o arquivo anual DFP da CVM, mantém cópia local (cache) e extrai as demonstrações da empresa escolhida, com busca por nome ou CNPJ.
- **Outras fontes de dados:** arquivo JSON próprio ou conjunto de dados fictício embutido (funciona sem internet).
- **Cálculo de mais de 40 indicadores** organizados em módulos: liquidez e capital de giro, lucratividade, eficiência e DuPont, estrutura de capital e alavancagem (incluindo dívida líquida e graus de alavancagem operacional, financeira e combinada), múltiplos de mercado e custo de capital (WACC). Há ainda um resumo dos fluxos de caixa (DFC).
- **Estrutura de capital:** custo da dívida, alíquota efetiva, custo do capital próprio pelo CAPM e WACC; simulação da estrutura ótima (curva do WACC de 0% a 80% de dívida, com beta de Hamada e ratings sintéticos); benefício fiscal da dívida (Modigliani-Miller com impostos); e análise EBIT-LPA para comparar captação por dívida ou por ações.
- **Avaliação de projetos de investimento:** VPL, TIR, payback simples e descontado e índice de lucratividade, descontados pelo WACC da empresa ou por uma taxa informada.
- **Tratamento seguro de dados:** divisões por zero e contas ausentes resultam em `n/d`, sem interromper o programa. Avisos de qualidade dos dados acompanham o relatório.
- **Relatórios** em `.txt`, `.html` e `.json`, além dos dados de entrada reaproveitáveis.
- **Três formas de uso:** interface web, menu interativo no terminal e API em Python.
- **Sem dependências externas:** utiliza somente a biblioteca padrão do Python.

## 2. Estrutura do repositório

```
TP1-ADM-FIN/
├── analise_demonstracoes_financeiras.py   # Camada de cálculo: estruturas de dados e indicadores dos módulos 1 a 6
├── estrutura_capital.py                   # Camada de cálculo: WACC, alavancagem, EBIT-LPA, estrutura ótima
├── avaliacao_investimentos.py             # Camada de cálculo: VPL, TIR, paybacks e índice de lucratividade
├── cvm_loader.py                          # Camada de dados: captura e mapeamento de dados da CVM
├── app.py                                 # Camada de aplicação: serviço, relatórios e menu no terminal
├── servidor_web.py                        # Servidor HTTP (API JSON + arquivos estáticos)
├── web/                                   # Interface web (index.html é a página inicial)
├── tests/                                 # Testes automatizados (unittest)
└── .gitignore
```

Pastas criadas automaticamente durante o uso:

| Pasta | Conteúdo |
|---|---|
| `cache_cvm/` | Arquivos `dfp_cia_aberta_AAAA.zip` baixados da CVM |
| `relatorios/<empresa>/` | Relatórios e dados de entrada de cada análise |

## 3. Requisitos e instalação

- **Python 3.8 ou superior** (o código usa recursos como `Path.unlink(missing_ok=True)`, disponíveis a partir da versão 3.8).
- Conexão com a internet apenas para baixar o arquivo da CVM (veja o [modo offline](#modo-offline)).
- Nenhum pacote adicional: não há `pip install`.

```bash
git clone https://github.com/henry-gus/TP1-ADM-FIN.git
cd TP1-ADM-FIN
```

> Execute todos os comandos a partir da pasta do projeto: o cache e os relatórios são criados em relação ao diretório atual. No Windows, use `python`; em Linux/macOS, `python3`.

## 4. Como executar

### 4.1 Interface web (recomendado)

```bash
python servidor_web.py
```

O navegador abre em `http://127.0.0.1:8000`. Opções:

```bash
python servidor_web.py --porta 8080          # outra porta
python servidor_web.py --sem-navegador       # não abre o navegador automaticamente
```

Fluxo geral de uso: escolher o ano do exercício, aguardar o download do arquivo da CVM (o progresso é exibido), buscar a empresa por nome ou CNPJ, informar opcionalmente preço e número de ações e solicitar a análise. Depois, na seção **Estrutura de Capital**, informar os parâmetros de mercado (taxa livre de risco, beta, prêmio de mercado e, opcionalmente, o custo da dívida) e, se quiser, um cenário de captação; na seção **Avaliação de Projetos**, informar o investimento e os fluxos anuais (a taxa vem preenchida com o WACC). A interface também permite analisar os dados de exemplo ou dados próprios no formato JSON descrito na [seção 5](#5-dados-de-entrada).

O relatório exibido na interface reúne: cartões de destaque (Liquidez Corrente, Margem Líquida, ROE, EBITDA, Dívida/PL e P/L); a decomposição DuPont, com verificação automática de que o produto dos três fatores confere com o ROE; gráficos de estrutura do balanço, fluxos de caixa e margens; tabelas completas dos módulos; o cartão do WACC com seus componentes; a curva do WACC com o ponto ótimo e a estrutura atual; o benefício fiscal da dívida; o gráfico EBIT × LPA com o ponto de indiferença; a avaliação do projeto; e a lista de avisos sobre os dados. Os relatórios baixados (HTML, TXT e JSON) incluem tudo o que foi simulado. Indicadores que não podem ser calculados aparecem como `n/d`, acompanhados do motivo.

### 4.2 Menu no terminal

```bash
python app.py
```

Exibe um menu com quatro opções: analisar empresa real (CVM), analisar arquivo JSON, executar o exemplo fictício ou avaliar um projeto de investimento isolado (taxa obrigatória). Nas três primeiras, o menu pergunta se você quer informar os parâmetros de mercado e, depois do relatório, oferece a simulação de captação (EBIT-LPA) e a avaliação de um projeto. Atalhos sem menu:

```bash
python app.py --exemplo                                    # dados fictícios (sem internet)
python app.py --empresa "weg" --ano 2025                   # dados reais da CVM
python app.py --empresa "weg" --ano 2025 --preco 45,30 --acoes 4.197.317.998
python app.py --json meus_dados.json                       # arquivo JSON próprio
python app.py --empresa "weg" --individual                 # demonstrações individuais
python app.py --empresa "weg" --zip dfp_cia_aberta_2025.zip --nao-salvar

# Custo de capital (taxas em % ao ano)
python app.py --empresa "vale s.a" --preco 55 --rf 13,75 --beta 1,1 --premio 6
python app.py --empresa "embraer" --preco 70 --rf 13,75 --beta 1,0 --premio 6 --kd 14

# Análise EBIT-LPA e avaliação de projeto (valores em R$ mil)
python app.py --exemplo --captacao 300.000 --taxa-divida 15 --preco-emissao 15
python app.py --exemplo --projeto "1.000;500;400;300;100" --taxa-projeto 10
```

| Opção | Descrição |
|---|---|
| `--exemplo` | Usa os dados fictícios embutidos |
| `--json ARQUIVO` | Analisa um arquivo JSON de dados |
| `--empresa NOME_OU_CNPJ` | Analisa uma empresa da CVM |
| `--ano AAAA` | Ano do exercício (padrão: ano anterior ao atual) |
| `--individual` | Usa demonstrações individuais em vez de consolidadas |
| `--preco`, `--acoes` | Preço da ação (R$) e número total de ações; aceitam `45,30` e `4.197.317.998` |
| `--zip ARQUIVO` | Usa um `.zip` da DFP já baixado |
| `--pasta-saida PASTA` | Pasta dos relatórios (padrão: `relatorios`) |
| `--nao-salvar` | Apenas imprime, sem gerar arquivos |
| `--rf`, `--premio` | Taxa livre de risco e prêmio de risco de mercado, em % (ex.: `13,75`) |
| `--beta` | Beta alavancado atual (ex.: `1,2`) |
| `--kd` | Custo da dívida em %; substitui o Kd contábil no WACC |
| `--captacao` | Valor a captar em R$ mil; ativa a análise EBIT-LPA (exige `--taxa-divida` e `--preco-emissao`) |
| `--taxa-divida`, `--preco-emissao` | Taxa da nova dívida (%) e preço de emissão das novas ações (R$) |
| `--ebit-projetado` | EBIT de avaliação em R$ mil (padrão: EBIT atual) |
| `--projeto "INV;F1;F2;..."` | Investimento inicial e fluxos anuais em R$ mil, separados por `;` (a vírgula é decimal) |
| `--taxa-projeto` | Taxa de desconto do projeto em % (padrão: WACC) |

Erros de validação (por exemplo, `--captacao` sem `--preco-emissao`, ou preço de emissão zero) são exibidos com o nome do campo e encerram o programa com código de saída 1.

### 4.3 Somente captura de dados

O módulo `cvm_loader.py` pode gerar um JSON a partir da CVM, para uso posterior:

```bash
python cvm_loader.py "weg" --ano 2025 --saida dados.json
python app.py --json dados.json
```

### Modo offline

Baixe manualmente `dfp_cia_aberta_AAAA.zip` em
`https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/` e copie o arquivo para a pasta `cache_cvm/` (ela é criada na primeira execução; crie-a se necessário). A interface web e o menu o reconhecem sem novo download. No terminal também é possível usar `--zip`.

## 5. Dados de entrada

### 5.1 Fonte principal: CVM

Os dados vêm do arquivo anual **DFP** (Demonstrações Financeiras Padronizadas) do Portal de Dados Abertos da CVM. O programa utiliza o último exercício do arquivo (e o exercício anterior, que a DFP traz como comparativo, para a dívida média e os graus de alavancagem) e a versão mais recente de cada documento, converte a escala para **R$ mil** e usa valores positivos para custos e despesas. O mapeamento completo entre contas da CVM e campos do programa está na seção 3.5 da [documentação](DOCUMENTACAO.md).

O **número de ações** é obtido da CVM (ações integralizadas menos ações em tesouraria), e a aplicação informa o valor utilizado nos avisos do relatório. O **preço da ação** não consta da DFP e deve ser informado pelo usuário; sem ele, P/L, Market-to-Book, Valor de Mercado e EV aparecem como `n/d`. O número de ações também pode ser informado manualmente (opção `--acoes` ou dados JSON).

> Use empresas **não financeiras**. Bancos e seguradoras têm plano de contas distinto; o programa emite aviso nesses casos.

### 5.2 Formato JSON

Os campos omitidos viram `n/d`. Valores monetários em R$ mil; `numero_acoes` em milhares; taxas em fração (`0.11` = 11%; um valor maior que 1 é interpretado como percentual, com aviso).

```json
{
  "empresa": "Empresa Teste S.A.",
  "periodo": "Exercício de 2025",
  "balanco": {
    "caixa": 120000, "contas_receber": 280000, "estoques": 200000,
    "outros_ativos_circulantes": 20000,
    "imobilizado": 700000, "intangivel": 80000, "outros_ativos_nao_circulantes": 100000,
    "fornecedores": 150000, "emprestimos_cp": 120000, "outros_passivos_circulantes": 130000,
    "emprestimos_lp": 400000, "outros_passivos_nao_circulantes": 100000,
    "patrimonio_liquido": 600000
  },
  "dre": {
    "vendas": 2000000, "cmv": 1200000, "despesas_operacionais": 450000,
    "depreciacao_amortizacao": 90000, "despesas_financeiras": 70000,
    "imposto_renda": 95200, "lucro_antes_impostos": 280000
  },
  "dfc": {
    "fluxo_operacional": 310000, "fluxo_investimento": -180000, "fluxo_financiamento": -60000
  },
  "mercado": {
    "preco_acao": 18.00, "numero_acoes": 100000,
    "taxa_livre_risco": 0.11, "beta": 1.2, "premio_risco_mercado": 0.055, "custo_divida": null
  },
  "exercicio_anterior": {
    "vendas": 1800000, "ebit": 300000, "lucro_liquido": 150000,
    "emprestimos_cp": 100000, "emprestimos_lp": 380000, "caixa": 100000, "patrimonio_liquido": 540000
  }
}
```

Os campos novos são opcionais: arquivos sem `exercicio_anterior`, sem `lucro_antes_impostos` ou sem os parâmetros de mercado continuam válidos. Sem eles, os indicadores que dependem desses dados aparecem como `n/d` com o motivo (por exemplo, "sem exercício anterior" ou "informe Rf, beta e prêmio de mercado").

Totais como `ativo_circulante`, `ativo_total`, `passivo_circulante`, `lucro_bruto`, `ebit` e `lucro_liquido` podem ser informados diretamente. Se não forem, o programa os calcula a partir das contas.

## 6. Indicadores calculados

| Módulo | Indicador | Fórmula |
|---|---|---|
| **1. Liquidez e capital de giro** | Liquidez Corrente | Ativo Circulante / Passivo Circulante |
| | Liquidez Seca | (Ativo Circulante − Estoque) / Passivo Circulante |
| | Prazo Médio de Recebimento (dias) | Contas a Receber / (Vendas / 365) |
| | Giro do Estoque | CMV / Estoque (usa Vendas se não houver CMV) |
| **2. Lucratividade** | Margem Bruta | Lucro Bruto / Vendas |
| | Margem Operacional | EBIT / Vendas |
| | Margem Líquida | Lucro Líquido / Vendas |
| | EBITDA | EBIT + Depreciação e Amortização |
| **3. Eficiência e DuPont** | Giro do Ativo Total | Vendas / Ativo Total |
| | Giro dos Ativos Fixos | Vendas / Imobilizado |
| | ROA | Lucro Líquido / Ativo Total |
| | ROE | Lucro Líquido / Patrimônio Líquido |
| | Decomposição DuPont | Margem Líquida × Giro do Ativo × (Ativo Total / PL) |
| **4. Estrutura de capital** | Capital de Terceiros / Capital Próprio | Dívida Total / Patrimônio Líquido |
| | Cobertura de Juros (TIE) | EBIT / Despesas Financeiras |
| | Dívida Líquida | Dívida Total − Caixa |
| | Dívida Líquida / EBITDA | Dívida Líquida / EBITDA |
| | Dívida / (Dívida + PL) | Dívida Total / (Dívida Total + PL) |
| | Grau de Alavancagem Operacional (GAO) | Δ% EBIT / Δ% Vendas |
| | Grau de Alavancagem Financeira (GAF) | Δ% Lucro Líquido / Δ% EBIT |
| | Grau de Alavancagem Combinada (GAC) | GAO × GAF |
| **5. Múltiplos de mercado** | LPA | Lucro Líquido / Nº de Ações |
| | VPA | Patrimônio Líquido / Nº de Ações |
| | P/L | Preço da Ação / LPA |
| | Market-to-Book | Valor de Mercado do PL / Valor Contábil do PL |
| | Enterprise Value (EV) | Valor de Mercado do PL + Dívida Total − Caixa |
| **6. Fluxos de caixa** (complementar) | FCO, FCI, FCF e variação líquida de caixa | Resumo da DFC |
| **7. Custo de capital (WACC)** | Custo da Dívida (Kd) | Despesas Financeiras / Dívida Média (atual e anterior) |
| | Alíquota Efetiva e Alíquota Aplicada | IR e CS / Lucro antes dos Impostos (34% se a efetiva for implausível) |
| | Kd após Impostos | Kd × (1 − Alíquota) |
| | Custo do Capital Próprio (Ke) | Rf + β × Prêmio de Mercado (CAPM) |
| | Valor do Capital Próprio (E) e Dívida (D) | Preço × Nº de Ações (ou PL contábil, sem preço); Empréstimos CP + LP |
| | Pesos D/V e E/V | D / (D + E) e E / (D + E) |
| | WACC | D/V × Kd × (1 − t) + E/V × Ke |

Seções complementares do relatório:

| Seção | Conteúdo |
|---|---|
| **Simulação da estrutura de capital ótima** | Para D/V de 0% a 80% (passos de 10 p.p.): beta re-alavancado (Hamada: βL = βu × [1 + (1 − t) × D/E]), Ke, cobertura de juros, rating sintético, Kd = Rf + spread e WACC; ponto ótimo (menor WACC) e estrutura atual. Benefício fiscal de Modigliani-Miller com impostos: VL = VU + t × D |
| **Análise EBIT-LPA** (com cenário de captação) | LPA de cada alternativa no EBIT avaliado, EBIT de indiferença EBIT* = (J₁N₂ − J₂N₁) / (N₂ − N₁) e LPA de indiferença |
| **Avaliação de projeto** (com projeto informado) | VPL, TIR, payback simples e descontado, índice de lucratividade (VP dos fluxos / investimento), recomendação pelo VPL e tabela ano a ano |

**Premissas:** saldos de fim de período (sem médias, exceto a dívida média do Kd); ano de 365 dias; "Dívida Total" = empréstimos e financiamentos de curto e longo prazo; "Ativos Fixos" = imobilizado. Na estrutura de capital: alíquota nominal de 34% (IRPJ + CSLL) quando a efetiva não faz sentido; dívida contábil como aproximação do valor de mercado da dívida; tabela de spreads por rating sintético de Damodaran (empresas não financeiras de grande porte, janeiro de 2026); valor da empresa constante na simulação. Detalhes e interpretação de cada indicador estão na seção 2 da [documentação](DOCUMENTACAO.md).

## 7. Relatórios gerados

Cada análise grava uma pasta `relatorios/<empresa>/` com:

| Arquivo | Descrição |
|---|---|
| `relatorio.txt` | Mesmo relatório exibido no console |
| `relatorio.html` | Versão para abrir no navegador (autônoma, sem internet) |
| `relatorio.json` | Indicadores estruturados (valor, valor formatado, unidade, fórmula e motivo do `n/d`), além da simulação, da análise EBIT-LPA e da avaliação de projeto |
| `dados_entrada.json` | Dados capturados (inclusive exercício anterior e parâmetros de mercado), reutilizáveis com `--json` sem novo download |

## 8. API HTTP

O servidor expõe a camada de serviço de `app.py` em JSON. Erros retornam `{"erro": "mensagem"}` com status HTTP 400 (entrada inválida), 404, 413 (corpo maior que 2 MB) ou 500.

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/config` | Ano padrão do exercício |
| POST | `/api/dfp/preparar` | Inicia, em segundo plano, o download da DFP do ano. Corpo: `{"ano": 2025}` |
| GET | `/api/dfp/status?ano=2025` | Andamento do download (`ausente`, `baixando`, `pronto` ou `erro`) |
| GET | `/api/empresas?ano=2025&termo=weg` | Busca empresas no arquivo da CVM (mínimo de 2 caracteres) |
| POST | `/api/analisar/cvm` | Analisa empresa da CVM. Corpo: `{cnpj, nome, cd_cvm, ano, consolidado, preco, acoes}` |
| POST | `/api/analisar/dados` | Analisa dados no formato JSON da seção 5. Corpo: `{"dados": {...}}` |
| GET | `/api/analisar/exemplo` | Analisa os dados fictícios |
| POST | `/api/analisar/exemplo` | Idem, aceitando os blocos opcionais abaixo |

As três rotas de análise aceitam blocos opcionais no corpo. Taxas chegam em **percentual** e números aceitam o formato brasileiro; string vazia ou `null` significa "não informado":

```json
{
  "parametros": { "rf": "11", "beta": "1,2", "premio": "5,5", "kd": "" },
  "captacao":   { "valor": "300.000", "taxa": "15", "preco_emissao": "15,00", "ebit_projetado": "" },
  "projeto":    { "investimento": "1.000", "fluxos": ["500", "400", "300", "100"], "taxa": "" }
}
```

- `parametros` sobrescreve os campos correspondentes de `dados.mercado`.
- `captacao` exige valor, taxa e preço de emissão maiores que zero.
- `projeto` aceita de 1 a 20 fluxos; com `taxa` vazia, usa o WACC (se o WACC não puder ser calculado, a resposta é 400 pedindo a taxa).

A resposta passa a incluir `motivo` em cada indicador, `estrutura_capital` (`custo_capital_meta`, `simulacao` e `ebit_lpa`) e `avaliacao_projeto`. Entradas inválidas geram 400 com o campo nomeado (ex.: `Preço de emissão deve ser maior que zero.`).

O servidor escuta por padrão apenas em `127.0.0.1` e destina-se a uso local e acadêmico, não à publicação na internet.

## 9. Uso como biblioteca

```python
import app

# Dados reais (baixa a DFP se necessário)
resultado = app.analisar_cvm("weg", ano=2025, preco_acao=45.30, numero_acoes=4_197_317_998)
print(resultado.texto)                 # relatório formatado
dados = resultado.para_dict()          # estrutura JSON-serializável
app.salvar_relatorios(resultado)       # grava .txt, .html e .json

# Exemplo fictício, com cenário de captação e projeto (taxas em fração)
r = app.analisar_exemplo(
    parametros={"taxa_livre_risco": 0.11, "beta": 1.2, "premio_risco_mercado": 0.055},
    captacao={"valor": 300_000, "taxa_divida": 0.15, "preco_emissao": 15},
    projeto={"investimento_inicial": 1000, "fluxos": [500, 400, 300, 100], "taxa": 0.10},
)
r.estrutura_capital["simulacao"]["otimo"]   # {'dv': 0.7, 'wacc': 0.1409...}
r.avaliacao_projeto["vpl"]                  # 78.82...

# Funções de cálculo isoladas
import estrutura_capital as ec, avaliacao_investimentos as ai
ai.tir([-1000, 500, 400, 300, 100])          # (0.1449..., None)
```

## 10. Limitações conhecidas

- Apenas demonstrações anuais (DFP); demonstrações trimestrais (ITR) não são tratadas.
- Empresas financeiras (bancos e seguradoras) não são suportadas.
- A depreciação e amortização é estimada pela soma das linhas correspondentes do DFC (método indireto); o EBITDA fica `n/d` se ela não for localizada.
- Indicadores calculados sobre saldos de fim de período, sem médias.
- O preço da ação deve ser informado pelo usuário.
- O Kd contábil (despesas financeiras / dívida média) é ruidoso em empresas reais, porque as despesas financeiras da DFP incluem variação cambial, derivativos e juros de arrendamento. O programa avisa quando o valor sai da faixa usual de 2% a 40% a.a. e permite informar o Kd (`--kd` ou campo Kd).
- Os parâmetros do CAPM (taxa livre de risco, beta e prêmio de mercado) não constam da DFP e devem ser informados.
- Na simulação da estrutura ótima, o valor da empresa é mantido constante e o Kd de cada nível vem da tabela de ratings sintéticos, por isso difere do Kd contábil; a curva pode ter pequenos "dentes" por causa das faixas discretas de rating.

## 11. Atendimento aos critérios de avaliação

Conforme o enunciado do Trabalho 2:

| Critério | Onde está atendido |
|---|---|
| Execução da aplicação | `python servidor_web.py` ou `python app.py` (a opção de dados fictícios roda sem internet) |
| Captura de dados | `cvm_loader.py` (CVM), além de arquivo JSON e dados embutidos |
| Descrição nos comentários do código | Todos os módulos possuem docstrings e comentários em português |
| Geração de relatórios | `.txt`, `.html` e `.json` em `relatorios/`; relatório também exibido no console e na interface |

Temas abordados:

- **Análise de demonstrações financeiras** (tema principal): módulos 1 a 6.
- **Estrutura de capital** (completo): custo de capital e WACC, endividamento, graus de alavancagem, análise EBIT-LPA, estrutura ótima e Modigliani-Miller com impostos.
- **Gestão de investimentos**, por meio do orçamento de capital: VPL, TIR, paybacks e índice de lucratividade, descontados pelo WACC.
- **Operações financeiras** não fazem parte do escopo.

## 12. Exemplo de execução: Vale S.A.

Execução com dados reais da CVM (DFP 2025, demonstrações consolidadas, valores em R$ mil), com preço da ação de 30/12/2025. A análise completa e a interpretação estão na seção 4.3 da [documentação](DOCUMENTACAO.md).

| Indicador | Resultado |
|---|---|
| Liquidez Corrente | 1,15x |
| Margem Líquida | 5,53% |
| ROE | 6,25% (5,53% × 0,45x × 2,52x) |
| EBITDA | R$ 49,28 bi |
| Capital de Terceiros / Capital Próprio | 0,55x |
| Cobertura de Juros (TIE) | 3,96x |
| P/L | 26,01x |

## 13. Testes automatizados

Os testes usam apenas o `unittest` da biblioteca padrão. A partir da pasta do projeto:

```bash
python -m unittest discover -s tests -v
```

Eles conferem os valores dos dados fictícios (WACC de 15,73%, graus de alavancagem, ponto ótimo em 70% de D/V, EBIT de indiferença de R$ 340.000 mil), um exemplo de livro-texto de orçamento de capital (Projeto S de Brigham & Ehrhardt: VPL de 78,82 e TIR de 14,49% a 10%), casos-limite com dados ausentes, a leitura dos dois exercícios em um arquivo da CVM sintético, a validação das rotas do servidor e a compatibilidade dos indicadores originais com uma linha de base congelada (`tests/dados/base_modulos_exemplo.json`).
