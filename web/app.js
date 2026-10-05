/* Front-end da Análise de Demonstrações Financeiras (CAD 167 - UFMG).
   Conversa com servidor_web.py pela API JSON; não usa bibliotecas externas. */
"use strict";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const estado = {
  resultado: null,        // última resposta da API
  empresa: null,          // empresa da CVM selecionada
  fonteManual: "dados informados manualmente",
  buscaId: 0,
  baseId: 0,
  analiseId: 0,
  pollTimer: null,
};

// ---------------------------------------------------------------------------
// Utilitários
// ---------------------------------------------------------------------------
async function api(caminho, corpo) {
  const opcoes = corpo === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo),
  };
  let resposta;
  try {
    resposta = await fetch(caminho, opcoes);
  } catch {
    throw new Error("Não foi possível falar com o servidor. Ele ainda está rodando (python servidor_web.py)?");
  }
  const dados = await resposta.json().catch(() => ({}));
  if (!resposta.ok) throw new Error(dados.erro || `Erro HTTP ${resposta.status}`);
  return dados;
}

const valido = (v) => typeof v === "number" && Number.isFinite(v);

function numBR(v, casas = 2) {
  return v.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
}

/** Valor em R$ mil -> texto curto (R$ 1,23 bi / R$ 45,6 mi / R$ 789 mil). */
function moedaCurta(mil) {
  if (!valido(mil)) return "n/d";
  const abs = Math.abs(mil);
  if (abs >= 1e6) return `R$ ${numBR(mil / 1e6, 2)} bi`;
  if (abs >= 1e3) return `R$ ${numBR(mil / 1e3, 1)} mi`;
  return `R$ ${numBR(mil, 0)} mil`;
}

/** Aceita 1.234,56 · 1234.56 · 120.000 · 4.197.317.998.
    Sem vírgula, pontos separando grupos de 3 dígitos são milhares ("120.000" = 120 mil, não 120). */
function lerNumeroBR(texto) {
  let t = String(texto ?? "").replace(/R\$/g, "").replace(/\s/g, "").trim();
  if (!t) return null;
  if (t.includes(",")) t = t.replace(/\./g, "").replace(",", ".");
  else if (/^[-+]?\d{1,3}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "");
  const n = Number(t);
  if (!Number.isFinite(n)) throw new Error(`Número inválido: "${texto}"`);
  return n;
}

// ---------------------------------------------------------------------------
// Máscara de preço (R$): digita-se só números e os dois últimos são os centavos
// ---------------------------------------------------------------------------
const MAX_DIGITOS_PRECO = 11;  // até R$ 999.999.999,99

function formatarPreco(valor) {
  return valido(valor) ? valor.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "";
}

function precoDosDigitos(texto) {
  const digitos = String(texto).replace(/\D/g, "").replace(/^0+/, "").slice(0, MAX_DIGITOS_PRECO);
  return digitos ? formatarPreco(Number(digitos) / 100) : "";
}

function aplicarMascaraPreco(input) {
  input.addEventListener("input", () => {
    input.value = precoDosDigitos(input.value);
    input.setSelectionRange(input.value.length, input.value.length);
  });
  // Colar "45,3", "45.30" ou "R$ 1.234,56" mantém o valor (não interpreta como centavos)
  input.addEventListener("paste", (ev) => {
    const texto = ev.clipboardData?.getData("text") ?? "";
    let v = null;
    try { v = lerNumeroBR(texto); } catch { /* texto não numérico: ignora */ }
    ev.preventDefault();
    if (v !== null && v >= 0) input.value = precoDosDigitos(Math.round(v * 100));
  });
}

function escapar(texto) {
  return String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function slug(texto) {
  return String(texto).normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, "") || "empresa";
}

function baixarArquivo(nome, conteudo, tipo) {
  const url = URL.createObjectURL(new Blob([conteudo], { type: tipo }));
  const a = Object.assign(document.createElement("a"), { href: url, download: nome });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function mostrarErro(msg) {
  const el = $("#erro");
  el.textContent = msg || "";
  el.classList.toggle("oculto", !msg);
}

// ---------------------------------------------------------------------------
// Tema e abas
// ---------------------------------------------------------------------------
function iniciarTema() {
  try {
    const salvo = localStorage.getItem("tema");
    if (salvo) document.documentElement.dataset.theme = salvo;
  } catch { /* armazenamento indisponível */ }
  $("#btn-tema").addEventListener("click", () => {
    const escuroAtual = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === "dark"
      : matchMedia("(prefers-color-scheme: dark)").matches;
    const novo = escuroAtual ? "light" : "dark";
    document.documentElement.dataset.theme = novo;
    try { localStorage.setItem("tema", novo); } catch { /* ignora */ }
  });
}

function trocarAba(nome) {
  $$(".aba").forEach((b) => b.classList.toggle("ativa", b.dataset.aba === nome));
  $$(".aba-conteudo").forEach((s) => s.classList.toggle("oculto", s.id !== `aba-${nome}`));
  mostrarErro("");
}

// ---------------------------------------------------------------------------
// CVM: base anual, busca e análise
// ---------------------------------------------------------------------------
const anoSelecionado = () => Number($("#cvm-ano").value);
const ANO_MINIMO = 2010;

function anoValido() {
  const ano = anoSelecionado();
  return $("#cvm-ano").value !== "" && Number.isInteger(ano) && ano >= ANO_MINIMO && ano <= Number($("#cvm-ano").max || 9999);
}

async function verificarBase() {
  clearTimeout(estado.pollTimer);
  const id = ++estado.baseId;  // descarta respostas de um ano que já não está selecionado
  if (!anoValido()) {
    renderizarBase({ estado: "invalido" });
    return;
  }
  let s;
  try {
    s = await api(`/api/dfp/status?ano=${anoSelecionado()}`);
  } catch (e) {
    s = { estado: "erro", erro: e.message };
  }
  if (id === estado.baseId) renderizarBase(s);
}

function renderizarBase(s) {
  const ano = anoSelecionado();
  const caixa = $("#cvm-base"), texto = $("#cvm-base-texto"), prog = $("#cvm-progresso"), btn = $("#btn-baixar");
  caixa.classList.toggle("pronto", s.estado === "pronto");
  prog.classList.toggle("oculto", s.estado !== "baixando");
  btn.classList.toggle("oculto", !["ausente", "erro"].includes(s.estado));
  $("#cvm-busca-area").classList.toggle("oculto", s.estado !== "pronto");

  if (s.estado === "pronto") {
    const n = s.empresas;
    texto.textContent = `✓ Base da CVM (DFP ${ano}) disponível` + (n ? ` · ${n.toLocaleString("pt-BR")} empresas` : "");
    if (n && n < 100) {
      texto.textContent += ". Poucas empresas: o arquivo deste ano ainda está incompleto (só exercícios já encerrados).";
    }
  } else if (s.estado === "verificando") {
    texto.textContent = `Verificando a base da CVM de ${ano}…`;
  } else if (s.estado === "invalido") {
    texto.textContent = `Informe um ano entre ${ANO_MINIMO} e ${$("#cvm-ano").max}.`;
  } else if (s.estado === "ausente") {
    texto.textContent = `A base da CVM de ${ano} ainda não está no computador. O download (dezenas de MB) é feito só uma vez.`;
    btn.textContent = "Baixar base da CVM";
  } else if (s.estado === "erro") {
    texto.textContent = s.erro || "Falha ao baixar a base da CVM.";
    btn.textContent = "Tentar novamente";
  } else if (s.estado === "baixando") {
    const barra = prog.querySelector(".progresso-barra");
    const mb = (s.baixado / 1e6).toFixed(1);
    const terminado = s.total && s.baixado >= s.total;
    prog.classList.toggle("indeterminado", !s.total || terminado);
    barra.style.width = s.total && !terminado ? `${(100 * s.baixado / s.total).toFixed(1)}%` : "";
    texto.textContent = terminado ? "Indexando empresas…"
      : s.total ? `Baixando da CVM… ${mb} de ${(s.total / 1e6).toFixed(1)} MB`
      : s.baixado ? `Baixando da CVM… ${mb} MB` : "Conectando à CVM…";
    estado.pollTimer = setTimeout(verificarBase, 600);
  }
}

async function baixarBase() {
  mostrarErro("");
  if (!anoValido()) return;
  const id = ++estado.baseId;
  let s;
  try {
    s = await api("/api/dfp/preparar", { ano: anoSelecionado() });
  } catch (e) {
    s = { estado: "erro", erro: e.message };
  }
  if (id === estado.baseId) renderizarBase(s);
}

function limparSelecao() {
  estado.empresa = null;
  $("#cvm-selecionada").classList.add("oculto");
  $("#cvm-busca").closest(".campo").classList.remove("oculto");
  $("#btn-analisar-cvm").disabled = true;
}

let buscaTimer;
function aoDigitarBusca() {
  clearTimeout(buscaTimer);
  const termo = $("#cvm-busca").value.trim();
  const lista = $("#cvm-resultados");
  const id = ++estado.buscaId;  // invalida buscas em andamento e resultados antigos
  lista._empresas = null;
  if (termo.length < 2) { lista.innerHTML = ""; return; }
  buscaTimer = setTimeout(async () => {
    lista.innerHTML = `<li class="info">Buscando…</li>`;
    try {
      const { empresas } = await api(`/api/empresas?ano=${anoSelecionado()}&termo=${encodeURIComponent(termo)}`);
      if (id !== estado.buscaId) return;
      lista.innerHTML = empresas.length
        ? empresas.map((e, i) => `<li role="option" data-i="${i}"><span>${escapar(e.nome)}</span><small>CNPJ ${escapar(e.cnpj)}</small></li>`).join("")
        : `<li class="info">Nenhuma empresa encontrada. Tente outra parte do nome.</li>`;
      lista._empresas = empresas;
    } catch (e) {
      if (id === estado.buscaId) lista.innerHTML = `<li class="info">${escapar(e.message)}</li>`;
    }
  }, 280);
}

function selecionarEmpresa(empresa) {
  estado.empresa = empresa;
  estado.buscaId++;
  clearTimeout(buscaTimer);
  $("#cvm-resultados").innerHTML = "";
  $("#cvm-busca").closest(".campo").classList.add("oculto");
  const chip = $("#cvm-selecionada");
  chip.innerHTML = `<div><strong>${escapar(empresa.nome)}</strong><small>CNPJ ${escapar(empresa.cnpj)}</small></div>
    <button type="button" title="Trocar empresa" aria-label="Trocar empresa">×</button>`;
  chip.classList.remove("oculto");
  chip.querySelector("button").addEventListener("click", () => {
    limparSelecao();
    $("#cvm-busca").focus();
  });
  $("#btn-analisar-cvm").disabled = false;
}

async function analisarCVM() {
  if (!estado.empresa) return;
  mostrarErro("");
  let preco, acoes;
  try {
    preco = lerCampoMercado("#cvm-preco", "Preço da ação");
    acoes = lerCampoMercado("#cvm-acoes", "Número de ações");
  } catch (e) {
    mostrarErro(e.message);
    return;
  }
  await executarAnalise(`Lendo as demonstrações de ${estado.empresa.nome}…`, () => api("/api/analisar/cvm", {
    ...estado.empresa,
    ano: anoSelecionado(),
    consolidado: $("#cvm-consolidado").checked,
    preco,
    acoes,
  }), "cvm");
}

function lerCampoMercado(seletor, nome) {
  const campo = $(seletor);
  let v;
  try {
    v = lerNumeroBR(campo.value);
  } catch {
    campo.focus();
    throw new Error(`${nome} inválido: "${campo.value}". Exemplos: 45,30 ou 4.197.317.998`);
  }
  if (v !== null && v <= 0) {
    campo.focus();
    throw new Error(`${nome} deve ser maior que zero.`);
  }
  return v;
}

// ---------------------------------------------------------------------------
// Arquivo JSON e exemplo
// ---------------------------------------------------------------------------
async function analisarArquivo(arquivo) {
  if (!arquivo) return;
  mostrarErro("");
  let dados;
  try {
    dados = JSON.parse(await arquivo.text());
  } catch {
    mostrarErro(`"${arquivo.name}" não é um JSON válido.`);
    return;
  }
  if (dados && dados.dados_entrada) dados = dados.dados_entrada;  // aceita também relatorio.json
  await executarAnalise("Calculando indicadores…",
    () => api("/api/analisar/dados", { dados, fonte: `arquivo ${arquivo.name}` }), "arquivo");
}

// ---------------------------------------------------------------------------
// Entrada manual
// ---------------------------------------------------------------------------
const CAMPOS = [
  { secao: "balanco", titulo: "Balanço Patrimonial", campos: [
    ["caixa", "Caixa e equivalentes"], ["contas_receber", "Contas a receber"], ["estoques", "Estoques"],
    ["outros_ativos_circulantes", "Outros ativos circulantes"], ["ativo_circulante", "Ativo circulante (total)", true],
    ["imobilizado", "Imobilizado (ativos fixos)"], ["intangivel", "Intangível"],
    ["outros_ativos_nao_circulantes", "Outros ativos não circulantes"],
    ["ativo_nao_circulante", "Ativo não circulante (total)", true], ["ativo_total", "Ativo total", true],
    ["fornecedores", "Fornecedores"], ["emprestimos_cp", "Empréstimos de curto prazo"],
    ["outros_passivos_circulantes", "Outros passivos circulantes"], ["passivo_circulante", "Passivo circulante (total)", true],
    ["emprestimos_lp", "Empréstimos de longo prazo"], ["outros_passivos_nao_circulantes", "Outros passivos não circulantes"],
    ["patrimonio_liquido", "Patrimônio líquido"],
  ] },
  { secao: "dre", titulo: "DRE", campos: [
    ["vendas", "Receita líquida de vendas"], ["cmv", "CMV"], ["lucro_bruto", "Lucro bruto", true],
    ["despesas_operacionais", "Despesas operacionais"], ["depreciacao_amortizacao", "Depreciação e amortização"],
    ["ebit", "EBIT", true], ["despesas_financeiras", "Despesas financeiras"], ["imposto_renda", "IR e CSLL"],
    ["lucro_liquido", "Lucro líquido", true],
  ] },
  { secao: "dfc", titulo: "Fluxos de Caixa", campos: [
    ["fluxo_operacional", "Operacional (FCO)"], ["fluxo_investimento", "Investimento (FCI)"],
    ["fluxo_financiamento", "Financiamento (FCF)"],
  ] },
  { secao: "mercado", titulo: "Mercado", campos: [
    ["preco_acao", "Preço da ação"], ["numero_acoes", "Nº de ações (milhares)"],
  ] },
];

function montarFormulario() {
  const html = [`
    <div class="campo"><label for="m-empresa">Empresa</label><input id="m-empresa" type="text" placeholder="Nome da empresa"></div>
    <div class="campo"><label for="m-periodo">Período</label><input id="m-periodo" type="text" placeholder="Exercício de 2025"></div>`];
  for (const g of CAMPOS) {
    html.push(`<fieldset class="grupo"><legend>${g.titulo}</legend>`);
    for (const [nome, rotulo, total] of g.campos) {
      const id = `m-${g.secao}-${nome}`;
      const preco = nome === "preco_acao";
      const campo = `<input id="${id}" data-secao="${g.secao}" data-conta="${nome}"${preco
        ? ' inputmode="numeric" placeholder="0,00" data-mascara="preco"' : ' inputmode="decimal"'}${total ? ' placeholder="auto"' : ""}>`;
      html.push(`<div class="linha${total ? " total" : ""}"><label for="${id}">${rotulo}</label>
        ${preco ? `<div class="campo-moeda"><span aria-hidden="true">R$</span>${campo}</div>` : campo}</div>`);
    }
    html.push("</fieldset>");
  }
  $("#form-manual").innerHTML = html.join("");
  $$('#form-manual [data-mascara="preco"]').forEach(aplicarMascaraPreco);
}

function preencherFormulario(dados) {
  $("#m-empresa").value = dados?.empresa ?? "";
  $("#m-periodo").value = dados?.periodo ?? "";
  $$("#form-manual input[data-secao]").forEach((input) => {
    const v = dados?.[input.dataset.secao]?.[input.dataset.conta];
    if (input.dataset.mascara === "preco") input.value = formatarPreco(v);
    // Sem separador de milhar: "100.000" seria lido como 100 (ponto único = decimal)
    else input.value = valido(v) ? v.toLocaleString("pt-BR", { useGrouping: false, maximumFractionDigits: 4 }) : "";
  });
}

function lerFormulario() {
  const dados = {
    empresa: $("#m-empresa").value.trim() || "Empresa",
    periodo: $("#m-periodo").value.trim(),
    balanco: {}, dre: {}, dfc: {}, mercado: {},
  };
  for (const input of $$("#form-manual input[data-secao]")) {
    try {
      const v = lerNumeroBR(input.value);
      if (v !== null) dados[input.dataset.secao][input.dataset.conta] = v;
    } catch (e) {
      input.focus();
      throw new Error(`${$(`label[for="${input.id}"]`).textContent}: ${e.message}`);
    }
  }
  return dados;
}

async function analisarManual() {
  mostrarErro("");
  let dados;
  try { dados = lerFormulario(); } catch (e) { mostrarErro(e.message); return; }
  await executarAnalise("Calculando indicadores…",
    () => api("/api/analisar/dados", { dados, fonte: estado.fonteManual }), "manual");
}

function editarDados() {
  const r = estado.resultado;
  if (!r) return;
  preencherFormulario(r.dados_entrada);
  estado.fonteManual = r.fonte && !r.fonte.includes("editad") && !r.fonte.includes("manual")
    ? `${r.fonte} (editado manualmente)` : (r.fonte || "dados informados manualmente");
  trocarAba("manual");
  $(".painel").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------------------
// Execução e renderização dos resultados
// ---------------------------------------------------------------------------
function mostrarTela(qual) {
  for (const id of ["vazio", "carregando", "relatorio"]) $(`#${id}`).classList.toggle("oculto", id !== qual);
}

async function executarAnalise(mensagem, chamada, origem) {
  mostrarErro("");
  const id = ++estado.analiseId;  // se o usuário disparar outra análise, só a última vale
  const telaAnterior = estado.resultado ? "relatorio" : "vazio";
  $("#carregando-texto").textContent = mensagem;
  mostrarTela("carregando");
  try {
    const r = await chamada();
    if (id !== estado.analiseId) return;
    estado.resultado = r;
    estado.origem = origem;
    renderizar(r);
    mostrarTela("relatorio");
    if (matchMedia("(max-width: 960px)").matches) $(".resultados").scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    if (id !== estado.analiseId) return;
    mostrarErro(e.message);
    mostrarTela(telaAnterior);
  }
}

function indicadores(r) {
  const mapa = {};
  for (const lista of Object.values(r.modulos)) for (const i of lista) mapa[i.nome] = i;
  return mapa;
}

/** Valores-base de cada indicador, com os mesmos totais derivados usados no cálculo. */
function valoresBase(d) {
  const b = d?.balanco || {}, r = d?.dre || {}, f = d?.dfc || {}, m = d?.mercado || {};
  const sub = (x, y) => (valido(x) && valido(y) ? x - y : null);
  const vendas = r.vendas, lb = ou(r.lucro_bruto, sub(vendas, r.cmv));
  const ebit = ou(r.ebit, sub(lb, r.despesas_operacionais));
  const lair = sub(ebit, r.despesas_financeiras);
  return {
    ac: ou(b.ativo_circulante, b.caixa, b.contas_receber, b.estoques, b.outros_ativos_circulantes),
    pc: ou(b.passivo_circulante, b.fornecedores, b.emprestimos_cp, b.outros_passivos_circulantes),
    at: ou(b.ativo_total, ou(b.ativo_circulante, b.caixa, b.contas_receber, b.estoques, b.outros_ativos_circulantes),
      ou(b.ativo_nao_circulante, b.imobilizado, b.intangivel, b.outros_ativos_nao_circulantes)),
    pl: b.patrimonio_liquido, estoques: b.estoques, receber: b.contas_receber, imob: b.imobilizado,
    divida: soma(b.emprestimos_cp, b.emprestimos_lp),
    vendas, cmvOuVendas: valido(r.cmv) ? r.cmv : vendas, lb, ebit, da: r.depreciacao_amortizacao,
    despfin: r.despesas_financeiras,
    ll: valido(r.lucro_liquido) ? r.lucro_liquido : (valido(lair) ? lair - (valido(r.imposto_renda) ? r.imposto_renda : 0) : null),
    preco: m.preco_acao, acoes: m.numero_acoes,
    fco: f.fluxo_operacional, fci: f.fluxo_investimento, fcf: f.fluxo_financiamento,
  };
}

// Para cada indicador: [chave em valoresBase, nome do dado, é denominador?]
const DEPENDENCIAS = {
  "Liquidez Corrente": [["ac", "ativo circulante"], ["pc", "passivo circulante", 1]],
  "Liquidez Seca": [["ac", "ativo circulante"], ["estoques", "estoques"], ["pc", "passivo circulante", 1]],
  "Prazo Médio de Recebimento": [["receber", "contas a receber"], ["vendas", "receita", 1]],
  "Giro do Estoque": [["cmvOuVendas", "CMV"], ["estoques", "estoques", 1]],
  "Margem Bruta": [["lb", "lucro bruto"], ["vendas", "receita", 1]],
  "Margem Operacional": [["ebit", "EBIT"], ["vendas", "receita", 1]],
  "Margem Líquida": [["ll", "lucro líquido"], ["vendas", "receita", 1]],
  "EBITDA": [["ebit", "EBIT"], ["da", "depreciação e amortização"]],
  "Giro do Ativo Total": [["vendas", "receita"], ["at", "ativo total", 1]],
  "Giro dos Ativos Fixos": [["vendas", "receita"], ["imob", "imobilizado", 1]],
  "ROA": [["ll", "lucro líquido"], ["at", "ativo total", 1]],
  "ROE": [["ll", "lucro líquido"], ["pl", "patrimônio líquido", 1]],
  "DuPont - Margem Líquida": [["ll", "lucro líquido"], ["vendas", "receita", 1]],
  "DuPont - Giro do Ativo Total": [["vendas", "receita"], ["at", "ativo total", 1]],
  "DuPont - Multiplicador de Capital": [["at", "ativo total"], ["pl", "patrimônio líquido", 1]],
  "DuPont - ROE (produto dos 3 fatores)": [["ll", "lucro líquido"], ["vendas", "receita", 1], ["at", "ativo total", 1], ["pl", "patrimônio líquido", 1]],
  "Capital de Terceiros / Capital Próprio": [["divida", "empréstimos"], ["pl", "patrimônio líquido", 1]],
  "Cobertura de Juros (TIE)": [["ebit", "EBIT"], ["despfin", "despesas financeiras", 1]],
  "Lucro por Ação (LPA)": [["ll", "lucro líquido"], ["acoes", "número de ações", 1]],
  "Valor Contábil por Ação (VPA)": [["pl", "patrimônio líquido"], ["acoes", "número de ações", 1]],
  "Preço/Lucro (P/L)": [["preco", "preço da ação"], ["acoes", "número de ações", 1], ["ll", "lucro líquido", 1]],
  "Market-to-Book": [["preco", "preço da ação"], ["acoes", "número de ações"], ["pl", "patrimônio líquido", 1]],
  "Valor de Mercado do PL": [["preco", "preço da ação"], ["acoes", "número de ações"]],
  "Enterprise Value (EV)": [["preco", "preço da ação"], ["acoes", "número de ações"], ["divida", "empréstimos"]],
  "Fluxo de Caixa Operacional": [["fco", "fluxo operacional"]],
  "Fluxo de Caixa de Investimento": [["fci", "fluxo de investimento"]],
  "Fluxo de Caixa de Financiamento": [["fcf", "fluxo de financiamento"]],
  "Variação Líquida de Caixa": [["fco", "fluxos de caixa"]],
};

/** Explica em poucas palavras por que um indicador ficou n/d. */
function motivoND(nome, base) {
  for (const [chave, rotulo, denominador] of DEPENDENCIAS[nome] || []) {
    const v = base[chave];
    if (!valido(v)) {
      if (chave === "preco") return "informe o preço da ação";
      if (chave === "acoes") return "informe o número de ações";
      return `falta: ${rotulo}`;
    }
    if (denominador && v === 0) {
      if (chave === "estoques") return "empresa sem estoques";
      if (chave === "vendas") return "receita igual a zero";
      return `${rotulo} igual a zero`;
    }
  }
  return "dado ausente ou divisão por zero";
}

const TITULOS_MODULOS = {
  1: "Liquidez e Gestão de Capital de Giro",
  2: "Lucratividade e Rentabilidade",
  3: "Eficiência e Decomposição DuPont",
  4: "Estrutura de Capital e Alavancagem",
  5: "Múltiplos e Avaliação de Mercado",
  6: "Fluxos de Caixa (complementar)",
};

/** Avisos que invalidam a análise inteira (ex.: banco) vêm primeiro. */
function avisosOrdenados(avisos) {
  const grave = (a) => /instituição financeira/i.test(a);
  return [...avisos.filter(grave), ...avisos.filter((a) => !grave(a))];
}

function renderizar(r) {
  const ind = indicadores(r);
  $("#r-empresa").textContent = r.empresa;
  $("#r-periodo").textContent = r.periodo;
  $("#r-fonte").textContent = r.fonte ? `Fonte: ${r.fonte}` : "";

  $("#r-avisos").innerHTML = r.avisos?.length ? `
    <details class="avisos" open>
      <summary>${r.avisos.length} aviso${r.avisos.length > 1 ? "s" : ""} sobre os dados</summary>
      <ul>${avisosOrdenados(r.avisos).map((a) => `<li>${escapar(a)}</li>`).join("")}</ul>
    </details>` : "";

  const base = valoresBase(r.dados_entrada);
  renderizarKpis(ind, base);
  renderizarDupont(ind);
  renderizarBalanco(r.dados_entrada);
  $("#r-dfc").innerHTML = barrasDivergentes([
    ["Operacional", ind["Fluxo de Caixa Operacional"]?.valor],
    ["Investimento", ind["Fluxo de Caixa de Investimento"]?.valor],
    ["Financiamento", ind["Fluxo de Caixa de Financiamento"]?.valor],
    ["Variação líquida", ind["Variação Líquida de Caixa"]?.valor],
  ], moedaCurta, "var(--s5)");
  $("#r-margens").innerHTML = barrasDivergentes([
    ["Margem bruta", ind["Margem Bruta"]?.valor],
    ["Margem operacional", ind["Margem Operacional"]?.valor],
    ["Margem líquida", ind["Margem Líquida"]?.valor],
    ["ROA", ind["ROA"]?.valor],
    ["ROE", ind["ROE"]?.valor],
  ], (v) => `${numBR(v * 100, 1)}%`, "var(--s1)");
  renderizarModulos(r.modulos, base);
}

function renderizarKpis(ind, base) {
  const kpis = [
    ["Liquidez Corrente", "Liquidez corrente"],
    ["Margem Líquida", "Margem líquida"],
    ["ROE", "ROE"],
    ["EBITDA", "EBITDA", (i) => moedaCurta(i.valor)],
    ["Capital de Terceiros / Capital Próprio", "Dívida / PL"],
    ["Preço/Lucro (P/L)", "P/L"],
  ];
  $("#r-kpis").innerHTML = kpis.map(([nome, rotulo, fmt]) => {
    const i = ind[nome];
    if (!i) return "";
    const texto = fmt && valido(i.valor) ? fmt(i) : i.valor_formatado;
    return `<div class="kpi" title="${escapar(i.formula)}">
      <div class="kpi-rotulo">${escapar(rotulo)}</div>
      <div class="kpi-valor${valido(i.valor) ? "" : " nd"}">${escapar(texto)}</div>
      ${valido(i.valor) ? "" : `<div class="motivo">${escapar(motivoND(nome, base))}</div>`}
      <div class="kpi-formula">${escapar(i.formula)}</div></div>`;
  }).join("");
}

function renderizarDupont(ind) {
  const f = (nome, rotulo, extra = "") => {
    const i = ind[nome];
    return `<div class="dupont-fator ${extra}"><div class="v">${escapar(i?.valor_formatado ?? "n/d")}</div><div class="r">${rotulo}</div></div>`;
  };
  const roe = ind["ROE"], dupont = ind["DuPont - ROE (produto dos 3 fatores)"];
  const confere = valido(roe?.valor) && valido(dupont?.valor) && Math.abs(roe.valor - dupont.valor) < 1e-9;
  $("#r-dupont").innerHTML = `<div class="dupont">
      ${f("DuPont - Margem Líquida", "Margem líquida")}<span class="dupont-op">×</span>
      ${f("DuPont - Giro do Ativo Total", "Giro do ativo")}<span class="dupont-op">×</span>
      ${f("DuPont - Multiplicador de Capital", "Multiplicador<br>(Ativo / PL)")}<span class="dupont-op igual">=</span>
      ${f("DuPont - ROE (produto dos 3 fatores)", "ROE", "resultado")}
    </div>
    <p class="dupont-nota">${confere ? "✓ O produto dos três fatores confere com o ROE calculado diretamente (LL / PL)."
      : "Lucro Líquido / Vendas × Vendas / Ativo × Ativo / PL"}</p>`;
}

const soma = (...vs) => { const ok = vs.filter(valido); return ok.length ? ok.reduce((a, b) => a + b, 0) : null; };
const ou = (total, ...partes) => (valido(total) ? total : soma(...partes));

function renderizarBalanco(d) {
  const b = d?.balanco || {};
  const ac = ou(b.ativo_circulante, b.caixa, b.contas_receber, b.estoques, b.outros_ativos_circulantes);
  const anc = ou(b.ativo_nao_circulante, b.imobilizado, b.intangivel, b.outros_ativos_nao_circulantes);
  const pc = ou(b.passivo_circulante, b.fornecedores, b.emprestimos_cp, b.outros_passivos_circulantes);
  const pl = b.patrimonio_liquido;
  const at = ou(b.ativo_total, ac, anc);
  // A CVM não fornece o total do passivo não circulante: usa a identidade Ativo = PC + PNC + PL
  const pnc = valido(at) && valido(pc) && valido(pl) ? at - pc - pl
    : soma(b.emprestimos_lp, b.outros_passivos_nao_circulantes);
  const plNegativo = valido(pl) && pl < 0;
  // Em alguns planos de contas (ex.: bancos) AC + ANC não somam o Ativo Total: mostra a diferença
  const outrosAtivos = valido(at) ? at - (soma(ac, anc) ?? 0) : null;
  const segAtivo = [["Ativo circulante", ac, "var(--s1)"], ["Ativo não circulante", anc, "var(--s2)"]];
  if (valido(outrosAtivos) && Math.abs(outrosAtivos) > Math.abs(at) * 0.001) segAtivo.push(["Outros ativos", outrosAtivos, "var(--texto-3)"]);
  const linhas = [
    ["Ativo", segAtivo],
    [plNegativo ? "Passivo" : "Passivo + PL",
      [["Passivo circulante", pc, "var(--s3)"], ["Passivo não circulante", pnc, "var(--s4)"], ["Patrimônio líquido", pl, "var(--s5)"]]],
  ];
  const positivo = (v) => (valido(v) && v > 0 ? v : 0);
  const totais = linhas.map(([, segs]) => segs.reduce((t, [, v]) => t + positivo(v), 0));
  const maximo = Math.max(...totais);
  if (!maximo) { $("#r-balanco").innerHTML = `<p class="sem-dados">Sem dados de balanço.</p>`; return; }

  const barras = linhas.map(([nome, segs], li) => {
    const pedacos = segs.filter(([, v]) => positivo(v) > 0).map(([seg, v, cor]) => {
      const pct = (100 * v) / totais[li], largura = (100 * v) / maximo;
      return `<div class="seg" style="width:${largura}%;background:${cor}"
        title="${escapar(seg)}: ${moedaCurta(v)} (${numBR(pct, 1)}%)">${largura >= 9 ? `${numBR(pct, 0)}%` : ""}</div>`;
    }).join("");
    return `<div class="balanco-linha"><span class="balanco-rotulo">${nome}</span>
      <div class="balanco-trilho">${pedacos}</div><span class="balanco-total">${moedaCurta(totais[li])}</span></div>`;
  }).join("");
  const nota = plNegativo
    ? `<p class="dupont-nota">Patrimônio líquido negativo (${moedaCurta(pl)}): o passivo supera o ativo.</p>` : "";
  $("#r-balanco").innerHTML = `<div class="balanco" role="img" aria-label="Estrutura do balanço">${barras}</div>
    <div class="legenda">${linhas.flatMap(([, s]) => s).map(([n, v, c]) => `<span><i style="background:${c}"></i>${n}: ${moedaCurta(v)}</span>`).join("")}</div>${nota}`;
}

/** Barras horizontais com eixo no zero (aceitam valores negativos). */
function barrasDivergentes(itens, fmt, cor) {
  const vals = itens.map(([, v]) => v).filter(valido);
  if (!vals.length) return `<p class="sem-dados">Sem dados disponíveis.</p>`;
  const min = Math.min(0, ...vals), max = Math.max(0, ...vals);
  const faixa = max - min || 1;
  const zero = (-min / faixa) * 100;
  return `<div class="barras-h">${itens.map(([rotulo, v]) => {
    if (!valido(v)) {
      return `<div class="barra-h-linha"><span>${rotulo}</span><div class="barra-h-trilho"></div><span class="barra-h-valor" style="color:var(--texto-3)">n/d</span></div>`;
    }
    const w = (Math.abs(v) / faixa) * 100;
    const esq = v >= 0 ? zero : zero - w;
    return `<div class="barra-h-linha"><span>${rotulo}</span>
      <div class="barra-h-trilho">${min < 0 ? `<div class="zero" style="left:${zero}%"></div>` : ""}
        <div class="fill${v < 0 ? " neg" : ""}" style="left:${esq}%;width:${w}%;${v >= 0 ? `background:${cor}` : ""}"></div></div>
      <span class="barra-h-valor"${v < 0 ? ' style="color:var(--negativo)"' : ""}>${fmt(v)}</span></div>`;
  }).join("")}</div>`;
}

function renderizarModulos(modulos, base) {
  $("#r-modulos").innerHTML = Object.entries(modulos).map(([titulo, lista]) => {
    const m = titulo.match(/^(\d+)\.\s*(.*)$/);
    const num = m ? m[1] : "";
    const nome = TITULOS_MODULOS[num] || (m ? m[2] : titulo);
    const faltaPreco = num === "5" && !valido(base.preco);
    const chamada = faltaPreco ? `<div class="chamada">
        <p><strong>Falta o preço da ação.</strong> P/L, Market-to-Book, Valor de Mercado e EV dependem da cotação,
        que não faz parte das demonstrações financeiras entregues à CVM.</p>
        <button type="button" class="btn btn-secundario" data-acao="informar-preco">Informar preço</button></div>` : "";
    return `<section class="modulo"><h3>${num ? `<span class="num">${num}</span>` : ""}${escapar(nome)}</h3>${chamada}
      <table class="tabela"><tbody>${lista.map((i) => `<tr>
        <td class="nome">${escapar(i.nome)}</td>
        <td class="v${valido(i.valor) ? (i.valor < 0 ? " neg" : "") : " nd"}">${escapar(i.valor_formatado)}${
          valido(i.valor) ? "" : `<span class="motivo">${escapar(motivoND(i.nome, base))}</span>`}</td>
        <td class="f">${escapar(i.formula)}</td></tr>`).join("")}</tbody></table></section>`;
  }).join("");
}

/** Leva o usuário ao campo de preço adequado à origem da análise. */
function informarPreco() {
  if (estado.origem === "cvm") {
    trocarAba("cvm");
    $(".painel").scrollIntoView({ behavior: "smooth", block: "start" });
    $("#cvm-preco").focus({ preventScroll: true });
  } else {
    editarDados();
    $("#m-mercado-preco_acao").focus({ preventScroll: true });
    $("#m-mercado-preco_acao").scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function baixar(tipo) {
  const r = estado.resultado;
  if (!r) return;
  const base = slug(r.empresa);
  const { texto, relatorio_html: html, ...semTexto } = r;
  if (tipo === "html") baixarArquivo(`${base}_relatorio.html`, html, "text/html;charset=utf-8");
  if (tipo === "txt") baixarArquivo(`${base}_relatorio.txt`, texto, "text/plain;charset=utf-8");
  if (tipo === "json") baixarArquivo(`${base}_relatorio.json`, JSON.stringify(semTexto, null, 2), "application/json");
  if (tipo === "dados") baixarArquivo(`${base}_dados_entrada.json`, JSON.stringify(r.dados_entrada, null, 2), "application/json");
}

// ---------------------------------------------------------------------------
// Inicialização
// ---------------------------------------------------------------------------
async function iniciar() {
  iniciarTema();
  montarFormulario();
  aplicarMascaraPreco($("#cvm-preco"));

  $$(".aba").forEach((b) => b.addEventListener("click", () => trocarAba(b.dataset.aba)));

  // CVM
  $("#cvm-ano").addEventListener("change", () => {
    limparSelecao();
    $("#cvm-busca").value = "";
    $("#cvm-resultados").innerHTML = "";
    renderizarBase({ estado: "verificando" });  // não deixa buscar na base do ano anterior enquanto verifica
    verificarBase();
  });
  $("#btn-baixar").addEventListener("click", baixarBase);
  $("#cvm-busca").addEventListener("input", aoDigitarBusca);
  $("#cvm-busca").addEventListener("keydown", (ev) => {
    const empresas = $("#cvm-resultados")._empresas;
    if (ev.key !== "Enter") return;
    ev.preventDefault();
    if (empresas?.length) selecionarEmpresa(empresas[0]);
  });
  $("#cvm-resultados").addEventListener("click", (ev) => {
    const li = ev.target.closest("li[data-i]");
    if (li) selecionarEmpresa($("#cvm-resultados")._empresas[Number(li.dataset.i)]);
  });
  $("#btn-analisar-cvm").addEventListener("click", analisarCVM);

  // Arquivo / exemplo
  $("#arquivo-json").addEventListener("change", (ev) => { analisarArquivo(ev.target.files[0]); ev.target.value = ""; });
  const zona = $("#zona-arquivo");
  ["dragenter", "dragover"].forEach((t) => zona.addEventListener(t, (ev) => { ev.preventDefault(); zona.classList.add("arrastando"); }));
  ["dragleave", "drop"].forEach((t) => zona.addEventListener(t, () => zona.classList.remove("arrastando")));
  zona.addEventListener("drop", (ev) => { ev.preventDefault(); analisarArquivo(ev.dataTransfer.files[0]); });
  $("#btn-exemplo").addEventListener("click", () => executarAnalise("Calculando indicadores…", () => api("/api/analisar/exemplo"), "exemplo"));

  // Manual
  $("#btn-analisar-manual").addEventListener("click", analisarManual);
  $("#btn-limpar-manual").addEventListener("click", () => { preencherFormulario(null); estado.fonteManual = "dados informados manualmente"; });

  // Relatório
  $("#btn-editar").addEventListener("click", editarDados);
  $("#r-modulos").addEventListener("click", (ev) => {
    if (ev.target.closest('[data-acao="informar-preco"]')) informarPreco();
  });
  $("#btn-imprimir").addEventListener("click", () => window.print());
  $("#btn-download").addEventListener("click", (ev) => { ev.stopPropagation(); $("#menu-download").classList.toggle("oculto"); });
  $("#menu-download").addEventListener("click", (ev) => {
    const b = ev.target.closest("[data-download]");
    if (b) baixar(b.dataset.download);
    $("#menu-download").classList.add("oculto");
  });
  document.addEventListener("click", () => $("#menu-download").classList.add("oculto"));

  try {
    const { ano_padrao } = await api("/api/config");
    $("#cvm-ano").value = ano_padrao;
    $("#cvm-ano").max = ano_padrao + 1;
  } catch (e) {
    $("#cvm-ano").value = new Date().getFullYear() - 1;
    mostrarErro(e.message);
  }
  verificarBase();
}

iniciar();
