# Aplicação de Análise de Demonstrações Financeiras

**CAD 167 – Administração Financeira · Trabalho 1**
Universidade Federal de Minas Gerais · Faculdade de Ciências Econômicas · Departamento de Ciências Administrativas (CAD)
Curso de Sistemas de Informação · 2º semestre de 2026 · Professor: Bruno Pérez Ferreira

**Autores:** Henrique Gustavo Ferreira Silva e Guilherme Novais de Souza

Aplicação em Python que captura as demonstrações financeiras de companhias abertas brasileiras (Balanço Patrimonial, DRE e DFC) a partir dos Dados Abertos da CVM, calcula automaticamente os principais indicadores de análise de demonstrações financeiras e gera relatórios em texto, HTML e JSON. Pode ser usada por interface web, por menu em linha de comando ou como biblioteca.

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

## 1. Funcionalidades

- **Captura de dados reais:** baixa o arquivo anual DFP da CVM, mantém cópia local (cache) e extrai as demonstrações da empresa escolhida, com busca por nome ou CNPJ.
- **Outras fontes de dados:** arquivo JSON próprio ou conjunto de dados fictício embutido (funciona sem internet).
- **Cálculo de 24 indicadores** organizados em cinco módulos: liquidez e capital de giro, lucratividade, eficiência e DuPont, estrutura de capital, e múltiplos de mercado. Há ainda um resumo dos fluxos de caixa (DFC).
- **Tratamento seguro de dados:** divisões por zero e contas ausentes resultam em `n/d`, sem interromper o programa. Avisos de qualidade dos dados acompanham o relatório.
- **Relatórios** em `.txt`, `.html` e `.json`, além dos dados de entrada reaproveitáveis.
- **Três formas de uso:** interface web, menu interativo no terminal e API em Python.
- **Sem dependências externas:** utiliza somente a biblioteca padrão do Python.

## 2. Estrutura do repositório

```
TP1-ADM-FIN/
├── analise_demonstracoes_financeiras.py   # Camada de cálculo: indicadores financeiros
├── cvm_loader.py                          # Camada de dados: captura e mapeamento de dados da CVM
├── app.py                                 # Camada de aplicação: serviço, relatórios e menu no terminal
├── servidor_web.py                        # Servidor HTTP (API JSON + arquivos estáticos)
├── web/                                   # Interface web (index.html é a página inicial)
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

Fluxo geral de uso: escolher o ano do exercício, aguardar o download do arquivo da CVM (o progresso é exibido), buscar a empresa por nome ou CNPJ, informar opcionalmente preço e número de ações e solicitar a análise. A interface também permite analisar os dados de exemplo ou dados próprios no formato JSON descrito na [seção 5](#5-dados-de-entrada).

O relatório exibido na interface reúne: cartões de destaque (Liquidez Corrente, Margem Líquida, ROE, EBITDA, Dívida/PL e P/L); a decomposição DuPont, com verificação automática de que o produto dos três fatores confere com o ROE; gráficos de estrutura do balanço, fluxos de caixa e margens; tabelas completas dos módulos; e a lista de avisos sobre os dados. Indicadores que não podem ser calculados aparecem como `n/d`, acompanhados do motivo.

### 4.2 Menu no terminal

```bash
python app.py
```

Exibe um menu com três opções: analisar empresa real (CVM), analisar arquivo JSON ou executar o exemplo fictício. Atalhos sem menu:

```bash
python app.py --exemplo                                    # dados fictícios (sem internet)
python app.py --empresa "weg" --ano 2025                   # dados reais da CVM
python app.py --empresa "weg" --ano 2025 --preco 45,30 --acoes 4.197.317.998
python app.py --json meus_dados.json                       # arquivo JSON próprio
python app.py --empresa "weg" --individual                 # demonstrações individuais
python app.py --empresa "weg" --zip dfp_cia_aberta_2025.zip --nao-salvar
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

Os dados vêm do arquivo anual **DFP** (Demonstrações Financeiras Padronizadas) do Portal de Dados Abertos da CVM. O programa utiliza o último exercício do arquivo e a versão mais recente de cada documento, converte a escala para **R$ mil** e usa valores positivos para custos e despesas. O mapeamento completo entre contas da CVM e campos do programa está na seção 3.5 da [documentação](DOCUMENTACAO.md).

O **número de ações** é obtido da CVM (ações integralizadas menos ações em tesouraria), e a aplicação informa o valor utilizado nos avisos do relatório. O **preço da ação** não consta da DFP e deve ser informado pelo usuário; sem ele, P/L, Market-to-Book, Valor de Mercado e EV aparecem como `n/d`. O número de ações também pode ser informado manualmente (opção `--acoes` ou dados JSON).

> Use empresas **não financeiras**. Bancos e seguradoras têm plano de contas distinto; o programa emite aviso nesses casos.

### 5.2 Formato JSON

Os campos omitidos viram `n/d`. Valores monetários em R$ mil; `numero_acoes` em milhares.

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
    "imposto_renda": 95200
  },
  "dfc": {
    "fluxo_operacional": 310000, "fluxo_investimento": -180000, "fluxo_financiamento": -60000
  },
  "mercado": { "preco_acao": 18.00, "numero_acoes": 100000 }
}
```

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
| **5. Múltiplos de mercado** | LPA | Lucro Líquido / Nº de Ações |
| | VPA | Patrimônio Líquido / Nº de Ações |
| | P/L | Preço da Ação / LPA |
| | Market-to-Book | Valor de Mercado do PL / Valor Contábil do PL |
| | Enterprise Value (EV) | Valor de Mercado do PL + Dívida Total − Caixa |
| **6. Fluxos de caixa** (complementar) | FCO, FCI, FCF e variação líquida de caixa | Resumo da DFC |

**Premissas:** saldos de fim de período (sem médias); ano de 365 dias; "Dívida Total" = empréstimos e financiamentos de curto e longo prazo; "Ativos Fixos" = imobilizado. Detalhes e interpretação de cada indicador estão na seção 2 da [documentação](DOCUMENTACAO.md).

## 7. Relatórios gerados

Cada análise grava uma pasta `relatorios/<empresa>/` com:

| Arquivo | Descrição |
|---|---|
| `relatorio.txt` | Mesmo relatório exibido no console |
| `relatorio.html` | Versão para abrir no navegador (autônoma, sem internet) |
| `relatorio.json` | Indicadores estruturados (valor, valor formatado, unidade e fórmula) |
| `dados_entrada.json` | Dados capturados, reutilizáveis com `--json` sem novo download |

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

O servidor escuta por padrão apenas em `127.0.0.1` e destina-se a uso local e acadêmico, não à publicação na internet.

## 9. Uso como biblioteca

```python
import app

# Dados reais (baixa a DFP se necessário)
resultado = app.analisar_cvm("weg", ano=2025, preco_acao=45.30, numero_acoes=4_197_317_998)
print(resultado.texto)                 # relatório formatado
dados = resultado.para_dict()          # estrutura JSON-serializável
app.salvar_relatorios(resultado)       # grava .txt, .html e .json

# Exemplo fictício
app.analisar_exemplo()
```

## 10. Limitações conhecidas

- Apenas demonstrações anuais (DFP); demonstrações trimestrais (ITR) não são tratadas.
- Empresas financeiras (bancos e seguradoras) não são suportadas.
- A depreciação e amortização é estimada pela soma das linhas correspondentes do DFC (método indireto); o EBITDA fica `n/d` se ela não for localizada.
- Indicadores calculados sobre saldos de fim de período, sem médias.
- O preço da ação deve ser informado pelo usuário.

## 11. Atendimento aos critérios de avaliação

Conforme o enunciado do Trabalho 1:

| Critério | Onde está atendido |
|---|---|
| Execução da aplicação | `python servidor_web.py` ou `python app.py` (a opção de dados fictícios roda sem internet) |
| Captura de dados | `cvm_loader.py` (CVM), além de arquivo JSON e dados embutidos |
| Descrição nos comentários do código | Todos os módulos possuem docstrings e comentários em português |
| Geração de relatórios | `.txt`, `.html` e `.json` em `relatorios/`; relatório também exibido no console e na interface |

Tema escolhido: **Análise de demonstrações financeiras**.

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
