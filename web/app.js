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
  requisicao: null,       // última análise-base: {mensagem, caminho, corpo, origem}
  blocos: {},             // blocos aplicados sobre ela: parametros, captacao, projeto
  mercadoExtra: {},       // parâmetros de mercado preservados ao editar dados manualmente
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
  // O pequeno ajuste arredonda meio para cima apesar do ponto flutuante (1,485 -> 1,49)
  const ajustado = v + Math.sign(v) * Math.abs(v) * 1e-12;
  return ajustado.toLocaleString("pt-BR", { minimumFractionDigits: casas, maximumFractionDigits: casas });
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
  else if (/^[-+]?[1-9]\d{0,2}(\.\d{3})+$/.test(t)) t = t.replace(/\./g, "");
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
  await executarAnalise(`Lendo as demonstrações de ${estado.empresa.nome}…`, "/api/analisar/cvm", {
    ...estado.empresa,
    ano: anoSelecionado(),
    consolidado: $("#cvm-consolidado").checked,
    preco,
    acoes,
  }, "cvm");
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
  await executarAnalise("Calculando indicadores…", "/api/analisar/dados",
    { dados, fonte: `arquivo ${arquivo.name}` }, "arquivo");
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
    ["lucro_antes_impostos", "Lucro antes dos impostos (LAIR)", true], ["lucro_liquido", "Lucro líquido", true],
  ] },
  { secao: "dfc", titulo: "Fluxos de Caixa", campos: [
    ["fluxo_operacional", "Operacional (FCO)"], ["fluxo_investimento", "Investimento (FCI)"],
    ["fluxo_financiamento", "Financiamento (FCF)"],
  ] },
  { secao: "mercado", titulo: "Mercado", campos: [
    ["preco_acao", "Preço da ação"], ["numero_acoes", "Nº de ações (milhares)"],
  ] },
  { secao: "exercicio_anterior", titulo: "Exercício anterior", recolhivel: true,
    dica: "Opcional. Usado na dívida média do Kd e nos graus de alavancagem (GAO, GAF e GAC).", campos: [
    ["vendas", "Receita líquida de vendas"], ["ebit", "EBIT"], ["lucro_liquido", "Lucro líquido"],
    ["emprestimos_cp", "Empréstimos de curto prazo"], ["emprestimos_lp", "Empréstimos de longo prazo"],
    ["caixa", "Caixa e equivalentes"], ["patrimonio_liquido", "Patrimônio líquido"],
  ] },
];
const CAMPOS_MERCADO_EXTRA = ["taxa_livre_risco", "beta", "premio_risco_mercado", "custo_divida"];

function montarFormulario() {
  const html = [`
    <div class="campo"><label for="m-empresa">Empresa</label><input id="m-empresa" type="text" placeholder="Nome da empresa"></div>
    <div class="campo"><label for="m-periodo">Período</label><input id="m-periodo" type="text" placeholder="Exercício de 2025"></div>`];
  for (const g of CAMPOS) {
    html.push(g.recolhivel
      ? `<details class="grupo recolhivel"><summary>${g.titulo} <span class="opcional">(opcional)</span></summary><p class="dica">${g.dica}</p>`
      : `<fieldset class="grupo"><legend>${g.titulo}</legend>`);
    for (const [nome, rotulo, total] of g.campos) {
      const id = `m-${g.secao}-${nome}`;
      const preco = nome === "preco_acao";
      const campo = `<input id="${id}" data-secao="${g.secao}" data-conta="${nome}"${preco
        ? ' inputmode="numeric" placeholder="0,00" data-mascara="preco"' : ' inputmode="decimal"'}${total ? ' placeholder="auto"' : ""}>`;
      html.push(`<div class="linha${total ? " total" : ""}"><label for="${id}">${rotulo}</label>
        ${preco ? `<div class="campo-moeda"><span aria-hidden="true">R$</span>${campo}</div>` : campo}</div>`);
    }
    html.push(g.recolhivel ? "</details>" : "</fieldset>");
  }
  $("#form-manual").innerHTML = html.join("");
  $$('#form-manual [data-mascara="preco"]').forEach(aplicarMascaraPreco);
}

function preencherFormulario(dados) {
  estado.mercadoExtra = {};
  for (const c of CAMPOS_MERCADO_EXTRA) if (valido(dados?.mercado?.[c])) estado.mercadoExtra[c] = dados.mercado[c];
  const ant = dados?.exercicio_anterior;
  $("details.recolhivel").open = Boolean(ant && Object.values(ant).some(valido));
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
    balanco: {}, dre: {}, dfc: {}, mercado: {}, exercicio_anterior: {},
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
  if (!Object.keys(dados.exercicio_anterior).length) dados.exercicio_anterior = null;
  dados.mercado = { ...estado.mercadoExtra, ...dados.mercado };  // mantém Rf, beta, prêmio e Kd
  return dados;
}

async function analisarManual() {
  mostrarErro("");
  let dados;
  try { dados = lerFormulario(); } catch (e) { mostrarErro(e.message); return; }
  await executarAnalise("Calculando indicadores…", "/api/analisar/dados", { dados, fonte: estado.fonteManual }, "manual");
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

/** Nova análise-base (CVM, arquivo, manual ou exemplo): descarta parâmetros, cenário e projeto anteriores. */
async function executarAnalise(mensagem, caminho, corpo, origem) {
  mostrarErro("");
  const id = ++estado.analiseId;  // se o usuário disparar outra análise, só a última vale
  const telaAnterior = estado.resultado ? "relatorio" : "vazio";
  $("#carregando-texto").textContent = mensagem;
  mostrarTela("carregando");
  try {
    const r = await api(caminho, corpo);
    if (id !== estado.analiseId) return;
    estado.requisicao = { mensagem, caminho, corpo, origem };
    estado.blocos = {};
    $("#j-taxa").dataset.editado = "";
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

/** Reenvia a última análise com blocos novos (parâmetros, captação ou projeto), sem sair da tela. */
async function reanalisar(blocosExtras, form) {
  const req = estado.requisicao;
  if (!req) return;
  const erro = form.querySelector(".alerta-erro"), status = form.querySelector(".form-status");
  const botao = form.querySelector("button[type=submit]");
  erro.classList.add("oculto");
  const blocos = { ...estado.blocos, ...blocosExtras };
  const id = ++estado.analiseId;
  botao.disabled = true;
  status.textContent = "Recalculando…";
  try {
    const r = await api(req.caminho, { ...req.corpo, ...blocos });
    if (id !== estado.analiseId) return;
    estado.blocos = blocos;
    estado.resultado = r;
    renderizar(r);
    status.textContent = "✓ Aplicado";
    setTimeout(() => { if (status.textContent === "✓ Aplicado") status.textContent = ""; }, 2500);
  } catch (e) {
    if (id !== estado.analiseId) return;
    status.textContent = "";
    erro.textContent = e.message;
    erro.classList.remove("oculto");
  } finally {
    botao.disabled = false;
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
  7: "Custo de Capital (WACC)",
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
  renderizarEstrutura(r);
  renderizarSimulacao(r);
  renderizarEbitLpa(r);
  renderizarProjeto(r);
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
      ${valido(i.valor) ? "" : `<div class="motivo">${escapar(i.motivo || motivoND(nome, base))}</div>`}
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
          valido(i.valor) ? "" : `<span class="motivo">${escapar(i.motivo || motivoND(i.nome, base))}</span>`}</td>
        <td class="f">${escapar(i.formula)}</td></tr>`).join("")}</tbody></table></section>`;
  }).join("");
}

// ---------------------------------------------------------------------------
// Estrutura de capital: parâmetros, WACC, curva, MM e EBIT-LPA
// ---------------------------------------------------------------------------
const MODULO_WACC = "7. CUSTO DE CAPITAL (WACC)";
const pct = (v, casas = 2) => (valido(v) ? `${numBR(v * 100, casas)}%` : "n/d");
/** Fração -> texto em % para um campo editável (0,1375 -> "13,75"). */
const pctCampo = (v) => (valido(v) ? (v * 100).toLocaleString("pt-BR", { useGrouping: false, maximumFractionDigits: 4 }) : "");
const numCampo = (v) => (valido(v) ? v.toLocaleString("pt-BR", { useGrouping: false, maximumFractionDigits: 4 }) : "");

function indicadoresWacc(r) {
  const mapa = {};
  for (const i of r.modulos[MODULO_WACC] || []) mapa[i.nome] = i;
  return mapa;
}

function aplicarParametros(ev) {
  ev.preventDefault();
  reanalisar({ parametros: {
    rf: $("#p-rf").value.trim(), beta: $("#p-beta").value.trim(),
    premio: $("#p-premio").value.trim(), kd: $("#p-kd").value.trim(),
  } }, ev.currentTarget);
}

function aplicarCaptacao(ev) {
  ev.preventDefault();
  reanalisar({ captacao: {
    valor: $("#c-valor").value.trim(), taxa: $("#c-taxa").value.trim(),
    preco_emissao: $("#c-preco").value.trim(), ebit_projetado: $("#c-ebit").value.trim(),
  } }, ev.currentTarget);
}

function avaliarProjeto(ev) {
  ev.preventDefault();
  const taxa = $("#j-taxa");
  const fluxos = $("#j-fluxos").value.split(/[\/;\n]+/).map((f) => f.trim()).filter(Boolean);
  reanalisar({ projeto: {
    investimento: $("#j-investimento").value.trim(), fluxos,
    // Taxa igual à sugerida = usar o WACC exato (não o valor arredondado mostrado no campo)
    taxa: taxa.dataset.editado === "1" ? taxa.value.trim() : "",
  } }, ev.currentTarget);
}

function irParaParametros() {
  $("#form-parametros").scrollIntoView({ behavior: "smooth", block: "center" });
  const vazio = ["#p-rf", "#p-beta", "#p-premio"].map((s) => $(s)).find((c) => !c.value.trim());
  (vazio || $("#p-rf")).focus({ preventScroll: true });
}

function renderizarEstrutura(r) {
  const m = r.dados_entrada?.mercado || {};
  $("#p-rf").value = pctCampo(m.taxa_livre_risco);
  $("#p-beta").value = numCampo(m.beta);
  $("#p-premio").value = pctCampo(m.premio_risco_mercado);
  $("#p-kd").value = pctCampo(m.custo_divida);

  const w = indicadoresWacc(r);
  const meta = r.estrutura_capital?.custo_capital_meta || {};
  const wacc = w["WACC"];
  if (!wacc) { $("#r-wacc").innerHTML = ""; return; }
  const informado = meta.kd_utilizado === "informado";
  const linha = (rotulo, i, extra = "") => `<div class="wacc-linha"><span>${rotulo}</span><strong class="${valido(i?.valor) ? "" : "nd"}">${
    escapar(i?.valor_formatado ?? "n/d")}</strong>${extra}</div>`;
  const kd = informado
    ? `<div class="wacc-linha"><span>Kd informado</span><strong>${pct(m.custo_divida)}</strong></div>`
    : linha("Kd contábil", w["Custo da Dívida (Kd)"]);
  $("#r-wacc").innerHTML = `
    <h3>Custo médio ponderado de capital</h3>
    <div class="wacc-destaque">
      <div class="wacc-valor${valido(wacc.valor) ? "" : " nd"}">${escapar(wacc.valor_formatado)}</div>
      ${valido(wacc.valor) ? `<div class="kpi-formula">${escapar(wacc.formula)}</div>`
        : `<div class="motivo">${escapar(wacc.motivo || "")}</div>
           <button type="button" class="btn btn-fantasma btn-pequeno" data-acao="parametros">Informar parâmetros</button>`}
    </div>
    <div class="wacc-componentes">
      ${kd}
      ${linha("Alíquota aplicada", w["Alíquota Aplicada"], `<small>${escapar(meta.origem_aliquota || "")}</small>`)}
      ${linha("Kd após impostos", w["Kd após Impostos"])}
      ${linha("Ke (CAPM)", w["Custo do Capital Próprio (Ke)"])}
      ${linha("Peso da dívida (D/V)", w["Peso da Dívida (D/V)"])}
      ${linha("Peso do capital próprio (E/V)", w["Peso do Capital Próprio (E/V)"])}
    </div>
    <p class="dupont-nota">Pesos a valor ${meta.base_pesos === "mercado" ? "de mercado" : "contábil (sem preço da ação)"} ·
      Kd ${escapar(meta.kd_utilizado || "")} · alíquota ${escapar(meta.origem_aliquota || "")}</p>`;
  $("#r-wacc [data-acao=parametros]")?.addEventListener("click", irParaParametros);
}

/** Escala linear [d0, d1] -> [r0, r1]. */
const escala = (d0, d1, r0, r1) => (v) => r0 + ((v - d0) / (d1 - d0 || 1)) * (r1 - r0);

/** Valores "redondos" para as marcas de um eixo, cobrindo todo o intervalo [min, max]. */
function marcas(min, max, quantas = 5) {
  const bruto = (max - min) / quantas || Math.abs(max) || 1;
  const pot = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 2.5, 5, 10].map((f) => f * pot).find((p) => p >= bruto);
  const inicio = Math.floor(min / passo + 1e-9), fim = Math.ceil(max / passo - 1e-9);
  const lista = [];
  for (let k = inicio; k <= Math.max(fim, inicio + 1); k++) lista.push(k * passo || 0);  // "|| 0" evita -0
  return lista;
}

const GRAF = { w: 640, h: 300, m: { t: 18, r: 20, b: 44, l: 64 } };

function eixos(x, y, ticksX, ticksY, fmtX, fmtY, rotX, rotY) {
  const { w, h, m } = GRAF;
  const gx = ticksX.map((v) => `<g><line class="grade" x1="${x(v)}" x2="${x(v)}" y1="${m.t}" y2="${h - m.b}"/>
    <text x="${x(v)}" y="${h - m.b + 16}" text-anchor="middle">${fmtX(v)}</text></g>`).join("");
  const gy = ticksY.map((v) => `<g><line class="grade" x1="${m.l}" x2="${w - m.r}" y1="${y(v)}" y2="${y(v)}"/>
    <text x="${m.l - 8}" y="${y(v) + 4}" text-anchor="end">${fmtY(v)}</text></g>`).join("");
  return `<g class="eixo">${gx}${gy}
    <line class="base" x1="${m.l}" x2="${w - m.r}" y1="${h - m.b}" y2="${h - m.b}"/>
    <text class="rotulo" x="${(m.l + w - m.r) / 2}" y="${h - 6}" text-anchor="middle">${rotX}</text>
    <text class="rotulo" transform="translate(14 ${(m.t + h - m.b) / 2}) rotate(-90)" text-anchor="middle">${rotY}</text></g>`;
}

function renderizarSimulacao(r) {
  const sim = r.estrutura_capital?.simulacao;
  const alvo = $("#r-curva-wacc");
  if (!sim) { alvo.innerHTML = ""; $("#r-mm").innerHTML = ""; return; }
  if (sim.faltando) {
    alvo.innerHTML = `<div class="chamada chamada-cartao"><p><strong>Para simular, informe:</strong> ${escapar(sim.faltando.join(", "))}.</p>
      <button type="button" class="btn btn-secundario" data-acao="parametros">Informar parâmetros</button></div>`;
    $("#r-mm").innerHTML = `<p class="sem-dados">Depende dos mesmos dados da simulação.</p>`;
    return;
  }
  const { w, h, m } = GRAF;
  const pts = sim.pontos;
  const waccs = pts.map((p) => p.wacc).concat(valido(sim.atual.wacc_calculado) ? [sim.atual.wacc_calculado] : []);
  const ticksY = marcas(Math.min(...waccs) * 100, Math.max(...waccs) * 100, 5).map((v) => v / 100);
  const y = escala(ticksY[0], ticksY[ticksY.length - 1], h - m.b, m.t);
  const x = escala(0, 0.8, m.l, w - m.r);
  const caminho = pts.map((p, i) => `${i ? "L" : "M"}${x(p.dv).toFixed(1)},${y(p.wacc).toFixed(1)}`).join("");
  const otimo = pts.find((p) => p.dv === sim.otimo.dv);
  const atual = sim.atual;
  const marcaAtual = valido(atual.dv) && atual.dv <= 0.8 ? `<g class="marca-atual">
      <line x1="${x(atual.dv)}" x2="${x(atual.dv)}" y1="${m.t}" y2="${h - m.b}"/>
      <text x="${x(atual.dv) + 5}" y="${m.t + 10}">atual ${pct(atual.dv, 1)}</text>
      ${valido(atual.wacc_calculado) ? `<rect x="${x(atual.dv) - 5}" y="${y(atual.wacc_calculado) - 5}" width="10" height="10"
        transform="rotate(45 ${x(atual.dv)} ${y(atual.wacc_calculado)})"><title>WACC calculado (Kd contábil): ${pct(atual.wacc_calculado)}</title></rect>` : ""}</g>` : "";
  const circulos = pts.map((p) => `<circle class="${p === otimo ? "ponto otimo" : "ponto"}" cx="${x(p.dv)}" cy="${y(p.wacc)}" r="${p === otimo ? 6.5 : 4}">
      <title>D/V ${pct(p.dv, 0)} · WACC ${pct(p.wacc)} · rating ${p.rating}${valido(p.kd) ? ` · Kd ${pct(p.kd)}` : ""}</title></circle>`).join("");
  const rotuloOtimo = `<text class="rotulo-otimo" x="${x(otimo.dv)}" y="${y(otimo.wacc) - 12}" text-anchor="middle">ótimo ${pct(otimo.wacc)}</text>`;
  const linhas = pts.map((p) => `<tr class="${p === otimo ? "destaque" : ""}"><td>${pct(p.dv, 0)}</td><td>${numBR(p.beta)}</td><td>${pct(p.ke)}</td>
      <td>${valido(p.cobertura) ? `${numBR(p.cobertura)}x` : "—"}</td><td>${p.rating}</td><td>${valido(p.kd) ? pct(p.kd) : "—"}</td>
      <td>${pct(p.aliquota)}</td><td><strong>${pct(p.wacc)}</strong></td></tr>`).join("");
  alvo.innerHTML = `
    <p class="resumo-grafico">Ótimo em <strong>D/V = ${pct(otimo.dv, 0)}</strong> com WACC de <strong>${pct(otimo.wacc)}</strong>
      (rating ${escapar(otimo.rating)}). Hoje: D/V de ${pct(atual.dv)} e WACC calculado de ${pct(atual.wacc_calculado)}.
      Beta desalavancado: ${numBR(sim.beta_desalavancado, 4)}.</p>
    <svg class="grafico" viewBox="0 0 ${w} ${h}" role="img" aria-label="Curva do WACC por nível de endividamento">
      ${eixos(x, y, [0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8], ticksY, (v) => `${Math.round(v * 100)}%`, (v) => `${numBR(v * 100, 1)}%`, "Dívida / Valor (D/V)", "WACC")}
      ${marcaAtual}<path class="curva" d="${caminho}"/>${circulos}${rotuloOtimo}
    </svg>
    <div class="legenda"><span><i class="leg-curva"></i>WACC simulado</span><span><i class="leg-otimo"></i>Ponto ótimo</span>
      <span><i class="leg-atual"></i>Estrutura atual (WACC calculado)</span></div>
    <details class="detalhes"><summary>Tabela da simulação (${pts.length} pontos)</summary>
      <div class="tabela-rolagem"><table class="tabela tabela-grade"><thead><tr><th>D/V</th><th>Beta</th><th>Ke</th><th>Cobertura</th>
        <th>Rating</th><th>Kd</th><th>Alíquota</th><th>WACC</th></tr></thead><tbody>${linhas}</tbody></table></div></details>
    <details class="detalhes"><summary>Premissas da simulação</summary>
      <ul>${sim.premissas.map((p) => `<li>${escapar(p)}</li>`).join("")}</ul></details>`;

  const mm = sim.modigliani_miller;
  $("#r-mm").innerHTML = `<div class="mm">
      <div class="dupont-fator"><div class="v">${moedaCurta(mm.valor_desalavancado)}</div><div class="r">Empresa sem dívida (VU)</div></div>
      <span class="dupont-op">+</span>
      <div class="dupont-fator"><div class="v">${moedaCurta(mm.beneficio_fiscal)}</div><div class="r">Benefício fiscal (t × D)</div></div>
      <span class="dupont-op igual">=</span>
      <div class="dupont-fator resultado"><div class="v">${moedaCurta(mm.valor_alavancado)}</div><div class="r">Empresa alavancada (VL = D + E)</div></div>
    </div>
    <p class="dupont-nota">Proposição I de Modigliani-Miller com impostos (dívida perpétua): VL = VU + t × D, com t = ${pct(sim.aliquota)}.</p>`;
}

function renderizarEbitLpa(r) {
  const e = r.estrutura_capital?.ebit_lpa;
  const alvo = $("#r-ebit-lpa-resultado");
  if (!e) {
    alvo.innerHTML = `<p class="dica">Informe o valor a captar, a taxa da nova dívida e o preço de emissão para comparar o LPA das duas formas de financiamento.</p>`;
    return;
  }
  if (e.motivo) { alvo.innerHTML = `<p class="sem-dados">Análise indisponível: ${escapar(e.motivo)}.</p>`; return; }
  const { w, h, m } = GRAF;
  const [p0, p1] = e.pontos_grafico;
  const lpas = [p0.lpa_divida, p0.lpa_acoes, p1.lpa_divida, p1.lpa_acoes];
  const ticksY = marcas(Math.min(...lpas), Math.max(...lpas), 5);
  const ticksX = marcas(0, p1.ebit, 5);
  const x = escala(0, ticksX[ticksX.length - 1], m.l, w - m.r);
  const y = escala(ticksY[0], ticksY[ticksY.length - 1], h - m.b, m.t);
  const reta = (a, b, cls) => `<line class="${cls}" x1="${x(p0.ebit)}" y1="${y(a)}" x2="${x(p1.ebit)}" y2="${y(b)}"/>`;
  const ind = valido(e.ebit_indiferenca) && e.ebit_indiferenca >= 0 && e.ebit_indiferenca <= p1.ebit
    ? `<g class="marca-indiferenca"><circle cx="${x(e.ebit_indiferenca)}" cy="${y(e.lpa_indiferenca)}" r="6"><title>Indiferença: EBIT ${moedaCurta(e.ebit_indiferenca)}, LPA R$ ${numBR(e.lpa_indiferenca)}</title></circle>
        <text x="${x(e.ebit_indiferenca) + 9}" y="${y(e.lpa_indiferenca) + 16}">EBIT* ${moedaCurta(e.ebit_indiferenca)}</text></g>` : "";
  const avaliado = `<g class="marca-atual"><line x1="${x(e.ebit_avaliado)}" x2="${x(e.ebit_avaliado)}" y1="${m.t}" y2="${h - m.b}"/>
      <text x="${x(e.ebit_avaliado) + 5}" y="${m.t + 10}">EBIT ${e.origem_ebit === "projetado" ? "projetado" : "atual"}</text></g>`;
  const linhas = e.alternativas.map((a) => `<tr class="${a.nome === e.melhor_no_ebit ? "destaque" : ""}"><td>${a.nome === "Dívida" ? "Emitir dívida" : "Emitir ações"}</td>
      <td>${numBR(a.juros, 0)}</td><td>${numBR(a.acoes, 0)}</td><td><strong>R$ ${numBR(a.lpa_no_ebit)}</strong></td></tr>`).join("");
  const conclusao = valido(e.ebit_indiferenca)
    ? `EBIT de indiferença: <strong>${moedaCurta(e.ebit_indiferenca)}</strong> (LPA de R$ ${numBR(e.lpa_indiferenca)}). Acima dele, a dívida dá maior LPA; abaixo, as ações.`
    : `As retas são paralelas: não há ponto de indiferença e a alternativa <strong>${escapar(e.dominante)}</strong> domina em qualquer EBIT.`;
  alvo.innerHTML = `
    <div class="tabela-rolagem"><table class="tabela tabela-grade"><thead><tr><th>Alternativa</th><th>Juros (R$ mil)</th><th>Ações (mil)</th>
      <th>LPA no EBIT avaliado</th></tr></thead><tbody>${linhas}</tbody></table></div>
    <p class="resumo-grafico">${conclusao} No EBIT ${e.origem_ebit} (${moedaCurta(e.ebit_avaliado)}), ${
      e.melhor_no_ebit === "Empate" ? "as alternativas empatam" : `a melhor alternativa é <strong>${e.melhor_no_ebit === "Dívida" ? "a dívida" : "a emissão de ações"}</strong>`}.
      Alíquota: ${pct(e.aliquota)}.</p>
    <svg class="grafico" viewBox="0 0 ${w} ${h}" role="img" aria-label="Retas de LPA em função do EBIT para dívida e ações">
      ${eixos(x, y, ticksX, ticksY, (v) => numBR(v / 1000, 0), (v) => numBR(v, 2), "EBIT (R$ milhões)", "LPA (R$)")}
      ${avaliado}${reta(p0.lpa_divida, p1.lpa_divida, "reta-divida")}${reta(p0.lpa_acoes, p1.lpa_acoes, "reta-acoes")}${ind}
    </svg>
    <div class="legenda"><span><i class="leg-divida"></i>Dívida</span><span><i class="leg-acoes"></i>Ações</span>
      <span><i class="leg-atual"></i>EBIT avaliado</span></div>
    ${(e.avisos || []).map((a) => `<p class="dica">${escapar(a)}</p>`).join("")}`;
}

// ---------------------------------------------------------------------------
// Avaliação de projetos
// ---------------------------------------------------------------------------
const anos = (v) => (valido(v) ? `${numBR(v)} anos` : "não recuperado no horizonte");
const RECOMENDACOES = { aceitar: "Aceitar", rejeitar: "Rejeitar", indiferente: "Indiferente" };

function renderizarProjeto(r) {
  const wacc = indicadoresWacc(r)["WACC"];
  const taxa = $("#j-taxa"), nota = $("#j-taxa-nota");
  taxa.dataset.wacc = valido(wacc?.valor) ? numBR(wacc.valor * 100) : "";
  if (taxa.dataset.editado !== "1") taxa.value = taxa.dataset.wacc;
  nota.textContent = valido(wacc?.valor) ? `Sugerida: WACC de ${wacc.valor_formatado}. Altere se quiser.`
    : `WACC indisponível (${wacc?.motivo || "dados insuficientes"}): informe a taxa.`;
  nota.classList.toggle("aviso-campo", !valido(wacc?.valor));

  const p = r.avaliacao_projeto, alvo = $("#r-projeto-resultado");
  if (!p) { alvo.innerHTML = ""; return; }
  const cartao = (rotulo, valor, extra = "") => `<div class="kpi"><div class="kpi-rotulo">${rotulo}</div>
    <div class="kpi-valor${valor === "n/d" ? " nd" : ""}">${escapar(valor)}</div>${extra}</div>`;
  const linhas = p.tabela.map((t) => `<tr><td>${t.ano}</td><td class="${t.fluxo < 0 ? "neg" : ""}">${numBR(t.fluxo)}</td>
      <td>${numBR(t.fluxo_descontado)}</td><td class="${t.acumulado < 0 ? "neg" : ""}">${numBR(t.acumulado)}</td>
      <td class="${t.acumulado_descontado < 0 ? "neg" : ""}">${numBR(t.acumulado_descontado)}</td></tr>`).join("");
  alvo.innerHTML = `
    <div class="recomendacao rec-${p.recomendacao}">
      <span>Recomendação pelo VPL</span><strong>${RECOMENDACOES[p.recomendacao]}</strong>
      <small>Taxa de ${pct(p.taxa)} (${p.origem_taxa === "WACC" ? "WACC da empresa" : "informada"})</small>
    </div>
    <div class="kpis kpis-projeto">
      ${cartao("VPL", `R$ ${numBR(p.vpl)} mil`)}
      ${cartao("TIR", valido(p.tir) ? pct(p.tir) : "n/d", valido(p.tir) ? "" : `<div class="motivo">${escapar(p.motivo_tir || "")}</div>`)}
      ${cartao("Payback simples", anos(p.payback_simples))}
      ${cartao("Payback descontado", anos(p.payback_descontado))}
      ${cartao("Índice de lucratividade", valido(p.indice_lucratividade) ? `${numBR(p.indice_lucratividade)}x` : "n/d")}
    </div>
    ${p.avisos.length ? `<div class="avisos"><ul>${p.avisos.map((a) => `<li>${escapar(a)}</li>`).join("")}</ul></div>` : ""}
    <details class="detalhes" open><summary>Fluxos ano a ano (R$ mil)</summary>
      <div class="tabela-rolagem"><table class="tabela tabela-grade"><thead><tr><th>Ano</th><th>Fluxo</th><th>Descontado</th>
        <th>Acumulado</th><th>Acumulado descontado</th></tr></thead><tbody>${linhas}</tbody></table></div></details>`;
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
  $("#btn-exemplo").addEventListener("click", () => executarAnalise("Calculando indicadores…", "/api/analisar/exemplo", {}, "exemplo"));

  // Manual
  $("#btn-analisar-manual").addEventListener("click", analisarManual);
  $("#btn-limpar-manual").addEventListener("click", () => { preencherFormulario(null); estado.fonteManual = "dados informados manualmente"; });

  // Relatório
  $("#btn-editar").addEventListener("click", editarDados);
  $("#r-modulos").addEventListener("click", (ev) => {
    if (ev.target.closest('[data-acao="informar-preco"]')) informarPreco();
  });
  $("#btn-imprimir").addEventListener("click", () => window.print());

  // Estrutura de capital e projetos
  aplicarMascaraPreco($("#c-preco"));
  $("#form-parametros").addEventListener("submit", aplicarParametros);
  $("#form-captacao").addEventListener("submit", aplicarCaptacao);
  $("#form-projeto").addEventListener("submit", avaliarProjeto);
  $("#j-taxa").addEventListener("input", (ev) => {
    ev.target.dataset.editado = ev.target.value.trim() && ev.target.value.trim() !== ev.target.dataset.wacc ? "1" : "";
  });
  $("#r-curva-wacc").addEventListener("click", (ev) => {
    if (ev.target.closest('[data-acao="parametros"]')) irParaParametros();
  });
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
