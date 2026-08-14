// ---------- Helpers pra montar <select> ----------

function fillSelect(selectEl, options, { blankLabel = "—", selectedValue = null } = {}) {
  selectEl.innerHTML = "";
  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = blankLabel;
  selectEl.appendChild(blank);
  options.forEach(opt => {
    const el = document.createElement("option");
    el.value = opt.value;
    el.textContent = opt.label;
    if (opt.color) el.style.color = opt.color;
    if (selectedValue !== null && String(opt.value) === String(selectedValue)) el.selected = true;
    selectEl.appendChild(el);
  });
}

const STATUS_COLOR = {
  em_andamento: "#35D9B8",
  encerrado: "#8892A0",
};
const STATUS_DOT = {
  em_andamento: "🟢",
  encerrado: "🔴",
};

// ---------- Checagem inicial: o CSV da Oracle's Elixir está presente? ----------

const setupSection = document.getElementById("setup-needed");
const appContent = document.getElementById("app-content");
const setupStatus = document.getElementById("setup-status");
const checkCsvBtn = document.getElementById("check-csv-btn");
const sourceTag = document.getElementById("source-tag");

let appInitialized = false;

async function checkCsvAndBoot() {
  setupStatus.textContent = "Verificando…";
  try {
    const res = await fetch("/api/csv-status");
    const data = await res.json();
    if (data.disponivel) {
      setupSection.classList.add("hidden");
      appContent.classList.remove("hidden");
      sourceTag.innerHTML = `fonte de dados: <strong>Oracle's Elixir</strong> — ${data.jogos} jogos, ${data.times} times, atualizado até ${data.atualizado_ate}`;
      if (!appInitialized) {
        appInitialized = true;
        initApp();
      }
    } else {
      setupSection.classList.remove("hidden");
      appContent.classList.add("hidden");
      setupStatus.textContent = "Arquivo ainda não encontrado em data/oracles_elixir.csv. Salve o CSV lá e clique em verificar de novo.";
    }
  } catch (e) {
    setupStatus.textContent = "Não foi possível falar com o servidor local — confira se o app.py está rodando no terminal.";
  }
}
checkCsvBtn.addEventListener("click", checkCsvAndBoot);
checkCsvAndBoot();

// ---------- Troca de abas ----------

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

// ---------- Cascata genérica Ano -> Campeonato ----------

async function initYearSelect(selectEl, onReady) {
  try {
    const res = await fetch("/api/years");
    const years = await res.json();
    if (!Array.isArray(years) || years.length === 0) return;
    fillSelect(selectEl, years.map(y => ({ value: y, label: String(y) })), { blankLabel: "selecione…" });
    selectEl.value = years[0];
    onReady(years[0]);
  } catch (e) { /* ignora — checkCsvAndBoot já cobre o caso de servidor fora do ar */ }
}

async function loadTournamentsInto(tournamentSelect, hintEl, year) {
  tournamentSelect.disabled = true;
  tournamentSelect.innerHTML = `<option value="">carregando…</option>`;
  try {
    const res = await fetch(`/api/tournaments?year=${encodeURIComponent(year)}`);
    const data = await res.json();
    if (!res.ok || !Array.isArray(data)) {
      hintEl.textContent = (data && data.erro) || "Erro ao carregar campeonatos.";
      fillSelect(tournamentSelect, []);
      return;
    }
    const options = data.map(t => ({
      value: t.id,
      label: `${STATUS_DOT[t.status] || "⚪"} ${t.label} (${t.jogos} jogos)`,
      color: STATUS_COLOR[t.status] || null,
    }));
    fillSelect(tournamentSelect, options, { blankLabel: "selecione…" });
    tournamentSelect.disabled = options.length === 0;
    hintEl.innerHTML = options.length
      ? `${options.length} campeonato(s) encontrados em ${year}. 🟢 dados recentes (≤21 dias) · 🔴 encerrado/mais antigo`
      : `Nenhum campeonato encontrado em ${year}.`;
  } catch (e) {
    hintEl.innerHTML = `Não foi possível falar com o servidor local. <button type="button" class="retry-link" id="retry-tournaments">tentar de novo</button>`;
    fillSelect(tournamentSelect, [], { blankLabel: "erro ao carregar" });
    document.getElementById("retry-tournaments")?.addEventListener("click", () => loadTournamentsInto(tournamentSelect, hintEl, year));
  }
}

// ---------- Aba 1: Confronto ----------

let yearSelect, tournamentSelect, tournamentHint, team1Select, team2Select, analyzeBtn, resultsEl;
let cYearSelect, cTournamentSelect, cTournamentHint, tableWrap;
let currentTournamentId = null;

function initApp() {
  yearSelect = document.getElementById("year");
  tournamentSelect = document.getElementById("tournament");
  tournamentHint = document.getElementById("tournament-hint");
  team1Select = document.getElementById("team1");
  team2Select = document.getElementById("team2");
  analyzeBtn = document.getElementById("analyze-btn");
  resultsEl = document.getElementById("results");

  cYearSelect = document.getElementById("c-year");
  cTournamentSelect = document.getElementById("c-tournament");
  cTournamentHint = document.getElementById("c-tournament-hint");
  tableWrap = document.getElementById("tournament-table-wrap");

  initYearSelect(yearSelect, (year) => { resetTeams("selecione o campeonato primeiro"); loadTournamentsInto(tournamentSelect, tournamentHint, year); });

  yearSelect.addEventListener("change", () => {
    if (!yearSelect.value) return;
    resetTeams("selecione o campeonato primeiro");
    loadTournamentsInto(tournamentSelect, tournamentHint, yearSelect.value);
  });

  tournamentSelect.addEventListener("change", () => {
    if (!tournamentSelect.value) { resetTeams("selecione o campeonato primeiro"); return; }
    loadTeams(tournamentSelect.value);
  });

  team1Select.addEventListener("change", updateAnalyzeState);
  team2Select.addEventListener("change", updateAnalyzeState);

  analyzeBtn.addEventListener("click", onCompareClick);

  let campeonatoTabInitialized = false;
  document.querySelector('.tab-btn[data-tab="campeonato"]').addEventListener("click", () => {
    if (campeonatoTabInitialized) return;
    campeonatoTabInitialized = true;
    initYearSelect(cYearSelect, (year) => {
      tableWrap.classList.add("hidden");
      loadTournamentsInto(cTournamentSelect, cTournamentHint, year);
    });
  });

  cYearSelect.addEventListener("change", () => {
    if (!cYearSelect.value) return;
    tableWrap.classList.add("hidden");
    loadTournamentsInto(cTournamentSelect, cTournamentHint, cYearSelect.value);
  });

  cTournamentSelect.addEventListener("change", () => {
    if (!cTournamentSelect.value) { tableWrap.classList.add("hidden"); return; }
    currentTournamentId = cTournamentSelect.value;
    loadTournamentTable();
  });
}

function resetTeams(placeholder) {
  team1Select.disabled = true;
  team2Select.disabled = true;
  fillSelect(team1Select, [], { blankLabel: placeholder });
  fillSelect(team2Select, [], { blankLabel: placeholder });
  updateAnalyzeState();
}

async function loadTeams(tournamentId) {
  resetTeams("carregando…");
  try {
    const res = await fetch(`/api/teams-in-tournament?tournament=${encodeURIComponent(tournamentId)}`);
    const data = await res.json();
    if (!res.ok || !Array.isArray(data)) {
      resetTeams((data && data.erro) || "Nenhum time encontrado");
      return;
    }
    const options = data.map(t => ({ value: t, label: t }));
    fillSelect(team1Select, options, { blankLabel: "selecione…" });
    fillSelect(team2Select, options, { blankLabel: "selecione…" });
    team1Select.disabled = false;
    team2Select.disabled = false;
  } catch (e) {
    resetTeams("erro ao carregar times");
  }
  updateAnalyzeState();
}

function updateAnalyzeState() {
  const ok = team1Select.value && team2Select.value && team1Select.value !== team2Select.value;
  analyzeBtn.disabled = !ok;
}

// ---------- Comparação (sem odds — tudo automático) ----------

async function onCompareClick() {
  const team1 = team1Select.value;
  const team2 = team2Select.value;
  if (!team1 || !team2 || team1 === team2) {
    showError("Escolha dois times diferentes.");
    return;
  }

  const body = {
    team1, team2,
    limit: parseInt(document.getElementById("limit").value || "20", 10),
    tournament: tournamentSelect.value || null,
  };

  analyzeBtn.disabled = true;
  const originalLabel = analyzeBtn.textContent;
  analyzeBtn.textContent = "COMPARANDO...";
  resultsEl.classList.remove("hidden");
  resultsEl.innerHTML = `<p class="hint">Comparando times…</p>`;

  try {
    const res = await fetch("/api/compare", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) {
      showError(data.erro || "Erro ao comparar.");
      return;
    }
    renderCompare(data);
  } catch (e) {
    showError("Não foi possível falar com o servidor local. Confira se o app.py está rodando.");
  } finally {
    analyzeBtn.disabled = false;
    analyzeBtn.textContent = originalLabel;
  }
}

function showError(msg) {
  resultsEl.classList.remove("hidden");
  resultsEl.innerHTML = `<div class="error-box">${msg}</div>`;
}

function headToHeadBlock(h2h, nome1, nome2) {
  if (!h2h) return `<p class="hint">Nenhum confronto direto entre esses dois times nos jogos analisados.</p>`;
  const marks = h2h.ultimos_resultados.map(r => {
    const won1 = r.vencedor === "time1";
    return `<span class="h2h-mark ${won1 ? 'w1' : 'w2'}" title="${r.data}">${won1 ? '●' : '○'}</span>`;
  }).join("");
  return `
    <div class="h2h-row">
      <div class="h2h-score">${h2h.vitorias_time1} <small>${nome1}</small></div>
      <div class="h2h-mid">${h2h.jogos} jogo(s) direto(s)</div>
      <div class="h2h-score">${h2h.vitorias_time2} <small>${nome2}</small></div>
    </div>
    <div class="h2h-marks">${marks}</div>
    <p class="hint">● = vitória de ${nome1} · ○ = vitória de ${nome2} (mais recente → mais antigo)</p>
  `;
}

// ---------- Comparativo por mercado (abas estilo gol.gg) ----------

let lastCompareData = null;

function fmtSigned(n) {
  return n > 0 ? `+${n}` : `${n}`;
}

function fmtMetricValue(block, type, signed) {
  if (!block) return "—";
  if (type === "rate") return `${block.pct}%`;
  return signed ? fmtSigned(block.media) : `${block.media}`;
}

function barColor(v, isRate, signed) {
  if (v === null || v === undefined) return "var(--muted)";
  if (isRate) return v >= 50 ? "var(--accent)" : "var(--danger)";
  if (signed) return v > 0 ? "var(--accent)" : v < 0 ? "var(--danger)" : "var(--text)";
  return "var(--text)";
}

function metricBar(label, block, type, signed = false) {
  const isRate = type === "rate";
  if (!block) return `<div class="mf-row"><span class="mf-label">${label}</span><span class="na">—</span></div>`;
  const val = fmtMetricValue(block, type, signed);
  const pct = isRate ? block.pct : null;
  const color = isRate ? barColor(pct, true) : barColor(block.media, false, signed);
  return `
    <div class="mf-row">
      ${isRate ? `<div class="mf-bar-track"><div class="mf-bar-fill" style="width:${pct}%; background:${color}"></div></div>` : ""}
      <span class="mf-value" style="color:${color}">${val}</span>
      <span class="mf-label">${label}</span>
    </div>
  `;
}

function seqMarks(seqArr, type, signed = false) {
  if (!seqArr || !seqArr.length) return `<p class="hint">Sem jogos suficientes.</p>`;
  const isRate = type === "rate";
  return `<div class="seq-marks">${seqArr.map(s => {
    if (isRate) {
      const hit = s.valor === 1;
      return `<span class="seq-mark ${hit ? 'hit' : 'miss'}"><span class="seq-opp">vs ${s.adversario} · ${s.data}</span><span class="seq-icon">${hit ? '✓' : '✗'}</span></span>`;
    }
    const cls = signed ? (s.valor > 0 ? "hit" : s.valor < 0 ? "miss" : "num") : "num";
    const label = signed ? fmtSigned(s.valor) : s.valor;
    return `<span class="seq-mark ${cls}"><span class="seq-opp">vs ${s.adversario} · ${s.data}</span><span class="seq-icon">${label}</span></span>`;
  }).join("")}</div>`;
}

function marketPanelHtml(data, key) {
  const meta = data.mercados_disponiveis.find(m => m.key === key);
  if (!meta) return "";
  const type = meta.type;
  const t1 = data.time1, t2 = data.time2;
  const m1 = t1.metricas[key], m2 = t2.metricas[key];

  return `
    <div class="panel">
      <div class="panel-head"><h2>${meta.label}</h2></div>
      <div class="mf-cols">
        <div class="mf-col-head">${t1.nome}</div>
        <div class="mf-col-head mid">OVERALL</div>
        <div class="mf-col-head">${t2.nome}</div>
      </div>
      <div class="mf-triple">
        <div>${metricBar("Nos jogos analisados", m1.overall, type, meta.signed)}</div>
        <div class="mf-mid-label">${m1.overall?.jogos ?? "—"} / ${m2.overall?.jogos ?? "—"} jogos</div>
        <div>${metricBar("Nos jogos analisados", m2.overall, type, meta.signed)}</div>

        <div>${metricBar("Lado azul", m1.overall_azul, type, meta.signed)}</div>
        <div class="mf-mid-label">Lado azul</div>
        <div>${metricBar("Lado azul", m2.overall_azul, type, meta.signed)}</div>

        <div>${metricBar("Lado vermelho", m1.overall_vermelho, type, meta.signed)}</div>
        <div class="mf-mid-label">Lado vermelho</div>
        <div>${metricBar("Lado vermelho", m2.overall_vermelho, type, meta.signed)}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>${meta.label} — Recent Form</h2></div>
      <div class="mf-cols">
        <div class="mf-col-head">${t1.nome}</div>
        <div class="mf-col-head mid"></div>
        <div class="mf-col-head">${t2.nome}</div>
      </div>
      <div class="mf-triple">
        <div>${metricBar("", m1.recent_5, type, meta.signed)}</div>
        <div class="mf-mid-label">Últimos 5</div>
        <div>${metricBar("", m2.recent_5, type, meta.signed)}</div>

        <div>${metricBar("", m1.recent_10, type, meta.signed)}</div>
        <div class="mf-mid-label">Últimos 10</div>
        <div>${metricBar("", m2.recent_10, type, meta.signed)}</div>
      </div>
      <div class="mf-seq-row">
        <div>${seqMarks(m1.recent_10_seq, type, meta.signed)}</div>
        <div>${seqMarks(m2.recent_10_seq, type, meta.signed)}</div>
      </div>
    </div>

    <div class="panel">
      <div class="panel-head"><h2>${meta.label} — Past Faceoffs</h2></div>
      ${m1.confronto_direto?.summary ? `
        <div class="mf-cols">
          <div class="mf-col-head">${t1.nome}</div>
          <div class="mf-col-head mid">confronto direto</div>
          <div class="mf-col-head">${t2.nome}</div>
        </div>
        <div class="mf-triple">
          <div>${metricBar("", m1.confronto_direto.summary, type, meta.signed)}</div>
          <div class="mf-mid-label">${m1.confronto_direto.summary.jogos} jogo(s)</div>
          <div>${metricBar("", m2.confronto_direto.summary, type, meta.signed)}</div>
        </div>
        <div class="mf-seq-row">
          <div>${seqMarks(m1.confronto_direto.seq, type, meta.signed)}</div>
          <div>${seqMarks(m2.confronto_direto.seq, type, meta.signed)}</div>
        </div>
      ` : `<p class="hint">Sem confronto direto registrado nos jogos analisados.</p>`}
    </div>

    ${data.mercados_disponiveis.filter(m => m.parent === key).map(sub => `
      <p class="tt-section-label">${sub.label}</p>
      ${marketPanelHtml(data, sub.key)}
    `).join("")}

    ${key === "gamelength_avg" ? gameTimeLiveHtml(t1.nome, t2.nome) : ""}
    ${key === "kills_avg" ? liveKillLineHtml(t1.nome, t2.nome) : ""}
  `;
}

function switchMarketTab(key) {
  document.querySelectorAll(".market-tab-btn").forEach(b => b.classList.toggle("active", b.dataset.key === key));
  document.getElementById("market-panel-wrap").innerHTML = marketPanelHtml(lastCompareData, key);
  if (key === "gamelength_avg") initGameTimeLiveWidget(lastCompareData.time1.nome, lastCompareData.time2.nome);
  if (key === "kills_avg") initLiveKillLineWidget(lastCompareData.time1.nome, lastCompareData.time2.nome);
}

function renderCompare(data) {
  resultsEl.classList.remove("hidden");
  lastCompareData = data;
  const t1 = data.time1, t2 = data.time2;

  const tabsHtml = data.mercados_disponiveis.filter(m => !m.parent).map(m => `
    <button type="button" class="market-tab-btn ${m.key === 'win' ? 'active' : ''}" data-key="${m.key}">${m.label}</button>
  `).join("");

  resultsEl.innerHTML = `
    <div class="vs-title">${t1.nome} <span>vs</span> ${t2.nome}</div>

    <div class="panel">
      <div class="panel-head"><h2>Confronto direto (vitórias)</h2></div>
      ${headToHeadBlock(data.confronto_direto, t1.nome, t2.nome)}
    </div>

    <div class="market-tabs-bar">${tabsHtml}</div>
    <div id="market-panel-wrap">${marketPanelHtml(data, "win")}</div>
  `;

  document.querySelectorAll(".market-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => switchMarketTab(btn.dataset.key));
  });

  resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- Aba 2: Análise de Campeonato ----------

async function loadTournamentTable() {
  tableWrap.classList.remove("hidden");
  tableWrap.innerHTML = `<p class="hint">Carregando estatísticas do campeonato…</p>`;

  try {
    const res = await fetch(`/api/tournament-table?tournament=${encodeURIComponent(currentTournamentId)}`);
    const data = await res.json();
    if (!res.ok) {
      tableWrap.innerHTML = `<div class="error-box">${data.erro || "Erro ao carregar."}</div>`;
      return;
    }
    renderTournamentTable(data);
  } catch (e) {
    tableWrap.innerHTML = `<div class="error-box">Não foi possível falar com o servidor local.</div>`;
  }
}

function pctCell(v) {
  if (v === null || v === undefined) return `<td class="na">—</td>`;
  const cls = v >= 60 ? "win" : "";
  return `<td class="${cls}">${v}%</td>`;
}

let lastTournamentData = null;
let tableSortKey = "vitoria";
let tableSortDir = "desc";

function buildTableColumns(th) {
  const cols = [
    { key: "time", label: "Time", get: t => t.time, render: t => `<td>${t.time}</td>`, numeric: false },
    { key: "jogos", label: "Jogos", get: t => t.resumo.jogos_analisados, render: t => `<td>${t.resumo.jogos_analisados}</td>` },
    { key: "vitoria", label: "Vitória %", get: t => t.resumo.taxa_vitoria_pct, render: t => `<td class="${t.resumo.taxa_vitoria_pct >= 50 ? 'win' : ''}">${t.resumo.taxa_vitoria_pct}%</td>` },
    { key: "duracao", label: "Duração", get: t => t.resumo.media_duracao_min, render: t => `<td>${t.resumo.media_duracao_min} min</td>` },
    { key: "fb", label: "FB%", get: t => t.primeiras_jogadas?.first_blood_pct, render: t => pctCell(t.primeiras_jogadas?.first_blood_pct) },
    { key: "ft", label: "FT%", get: t => t.primeiras_jogadas?.first_tower_pct, render: t => pctCell(t.primeiras_jogadas?.first_tower_pct) },
    { key: "fd", label: "FD%", get: t => t.primeiras_jogadas?.first_dragon_pct, render: t => pctCell(t.primeiras_jogadas?.first_dragon_pct) },
    { key: "fh", label: "FH%", get: t => t.primeiras_jogadas?.first_herald_pct, render: t => pctCell(t.primeiras_jogadas?.first_herald_pct) },
    { key: "fnash", label: "FNash%", get: t => t.primeiras_jogadas?.first_baron_pct, render: t => pctCell(t.primeiras_jogadas?.first_baron_pct) },
    { key: "ouro", label: "Ouro médio", get: t => t.resumo.ouro.media_a_favor, render: t => `<td>${Math.round(t.resumo.ouro.media_a_favor)}</td>` },
    { key: "kills", label: "Kills média", get: t => t.resumo.kills.media_a_favor, render: t => `<td>${t.resumo.kills.media_a_favor}</td>` },
    { key: "mortes", label: "Mortes média", get: t => t.resumo.kills.media_contra, render: t => `<td>${t.resumo.kills.media_contra}</td>` },
    { key: "torres", label: "Torres média", get: t => t.resumo.torres.media_a_favor, render: t => `<td>${t.resumo.torres.media_a_favor}</td>` },
    { key: "dragoes", label: "Dragões média", get: t => t.resumo.dragoes.media_a_favor, render: t => `<td>${t.resumo.dragoes.media_a_favor}</td>` },
    { key: "baroes", label: "Barões média", get: t => t.resumo.baroes.media_a_favor, render: t => `<td>${t.resumo.baroes.media_a_favor}</td>` },
  ];
  th.kills.forEach(l => cols.push({ key: `k_${l}`, label: `Kills>${l}%`, get: t => t.limiares.kills[l], render: t => pctCell(t.limiares.kills[l]) }));
  th.towers.forEach(l => cols.push({ key: `t_${l}`, label: `Torres>${l}%`, get: t => t.limiares.towers[l], render: t => pctCell(t.limiares.towers[l]) }));
  th.dragons.forEach(l => cols.push({ key: `d_${l}`, label: `Dragões>${l}%`, get: t => t.limiares.dragons[l], render: t => pctCell(t.limiares.dragons[l]) }));
  th.barons.forEach(l => cols.push({ key: `b_${l}`, label: `Barões>${l}%`, get: t => t.limiares.barons[l], render: t => pctCell(t.limiares.barons[l]) }));
  th.inhibitors.forEach(l => cols.push({ key: `i_${l}`, label: `Inib>${l}%`, get: t => t.limiares.inhibitors[l], render: t => pctCell(t.limiares.inhibitors[l]) }));
  return cols;
}

function renderTournamentTable(data) {
  lastTournamentData = data;
  tableSortKey = "vitoria";
  tableSortDir = "desc";
  renderTournamentTableBody();
}

function renderTournamentTableBody() {
  const data = lastTournamentData;
  const th = data.limiares_disponiveis;
  const cols = buildTableColumns(th);

  const sortCol = cols.find(c => c.key === tableSortKey) || cols[2];
  const sorted = [...data.times].sort((a, b) => {
    let va = sortCol.get(a), vb = sortCol.get(b);
    if (va === null || va === undefined) va = sortCol.numeric === false ? "" : -Infinity;
    if (vb === null || vb === undefined) vb = sortCol.numeric === false ? "" : -Infinity;
    if (typeof va === "string") return tableSortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    return tableSortDir === "asc" ? va - vb : vb - va;
  });

  const headHtml = `
    <tr>
      ${cols.map(c => `
        <th data-key="${c.key}" class="${c.key === tableSortKey ? 'sorted' : ''}">
          ${c.label}${c.key === tableSortKey ? `<span class="sort-arrow">${tableSortDir === 'desc' ? '▼' : '▲'}</span>` : ''}
        </th>
      `).join("")}
    </tr>
  `;

  const rowsHtml = sorted.map(t => `<tr>${cols.map(c => c.render(t)).join("")}</tr>`).join("");

  tableWrap.innerHTML = `
    <p class="tt-section-label">Clique numa coluna pra ordenar. % = porcentagem dos jogos do campeonato em que a estatística ficou ACIMA da linha indicada.</p>
    <div class="tt-table-scroll">
      <table class="tt-table">
        <thead>${headHtml}</thead>
        <tbody>${rowsHtml}</tbody>
      </table>
    </div>
  `;

  tableWrap.querySelectorAll("th[data-key]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (tableSortKey === key) {
        tableSortDir = tableSortDir === "desc" ? "asc" : "desc";
      } else {
        tableSortKey = key;
        tableSortDir = key === "time" ? "asc" : "desc";
      }
      renderTournamentTableBody();
    });
  });
}

// ---------------------------------------------------------------------------
// Aba Valorant
// ---------------------------------------------------------------------------

const vSetupSection = document.getElementById("v-setup-needed");
const vAppContent = document.getElementById("v-app-content");
const vSetupStatus = document.getElementById("v-setup-status");
const vCheckBtn = document.getElementById("v-check-btn");

let vYearSelect, vTournamentSelect, vTournamentHint, vTeam1Select, vTeam2Select, vAnalyzeBtn, vResults;
let vInitialized = false;
let vCurrentTournamentId = null;
let vLastCompareData = null;

document.querySelector('.tab-btn[data-tab="valorant"]').addEventListener("click", () => {
  if (vInitialized) return;
  vInitialized = true;
  vCheckAndBoot();
  vlInit();
});

vCheckBtn.addEventListener("click", vCheckAndBoot);

async function vCheckAndBoot() {
  vSetupStatus.textContent = "Verificando…";
  try {
    const res = await fetch("/api/valorant/csv-status");
    const data = await res.json();
    if (data.disponivel) {
      vSetupSection.classList.add("hidden");
      vAppContent.classList.remove("hidden");
      vInitTeamsUI();
    } else {
      vSetupSection.classList.remove("hidden");
      vAppContent.classList.add("hidden");
      vSetupStatus.textContent = "Arquivos ainda não encontrados em data/valorant/vct_<ano>/. Salve lá e clique em verificar de novo.";
    }
  } catch (e) {
    vSetupSection.classList.remove("hidden");
    vSetupStatus.textContent = "Não foi possível falar com o servidor local — confira se o app.py está rodando.";
  }
}

function vInitTeamsUI() {
  vYearSelect = document.getElementById("v-year");
  vTournamentSelect = document.getElementById("v-tournament");
  vTournamentHint = document.getElementById("v-tournament-hint");
  vTeam1Select = document.getElementById("v-team1");
  vTeam2Select = document.getElementById("v-team2");
  vAnalyzeBtn = document.getElementById("v-analyze-btn");
  vResults = document.getElementById("v-results");

  vInitYearSelect();

  vYearSelect.addEventListener("change", () => {
    if (!vYearSelect.value) return;
    vResetTeams("selecione o campeonato primeiro");
    vLoadTournaments(vYearSelect.value);
  });

  vTournamentSelect.addEventListener("change", () => {
    if (!vTournamentSelect.value) { vResetTeams("selecione o campeonato primeiro"); return; }
    vCurrentTournamentId = vTournamentSelect.value;
    vLoadTeams(vTournamentSelect.value);
  });

  vTeam1Select.addEventListener("change", vUpdateAnalyzeState);
  vTeam2Select.addEventListener("change", vUpdateAnalyzeState);
  vAnalyzeBtn.addEventListener("click", vOnCompareClick);

  document.querySelectorAll('#v-results .market-tab-btn').forEach(btn => {
    btn.addEventListener("click", () => vSwitchSubTab(btn.dataset.vtab));
  });
}

async function vInitYearSelect() {
  try {
    const res = await fetch("/api/valorant/years");
    const years = await res.json();
    if (!Array.isArray(years) || years.length === 0) return;
    fillSelect(vYearSelect, years.map(y => ({ value: y, label: y })), { blankLabel: "selecione…" });
    vYearSelect.value = years[0];
    vResetTeams("selecione o campeonato primeiro");
    vLoadTournaments(years[0]);
  } catch (e) { /* ignora */ }
}

async function vLoadTournaments(year) {
  vTournamentSelect.disabled = true;
  vTournamentSelect.innerHTML = `<option value="">carregando…</option>`;
  try {
    const res = await fetch(`/api/valorant/tournaments?year=${encodeURIComponent(year)}`);
    const data = await res.json();
    if (!res.ok || !Array.isArray(data)) {
      vTournamentHint.textContent = (data && data.erro) || "Erro ao carregar campeonatos.";
      fillSelect(vTournamentSelect, []);
      return;
    }
    const options = data.map(t => ({ value: t.id, label: `${t.label} (${t.mapas} mapas, ${t.times} times)` }));
    fillSelect(vTournamentSelect, options, { blankLabel: "selecione…" });
    vTournamentSelect.disabled = options.length === 0;
    vTournamentHint.textContent = options.length ? `${options.length} campeonato(s) encontrados em ${year}.` : `Nenhum campeonato encontrado em ${year}.`;
  } catch (e) {
    vTournamentHint.innerHTML = `Não foi possível falar com o servidor local. <button type="button" class="retry-link" id="v-retry-tournaments">tentar de novo</button>`;
    document.getElementById("v-retry-tournaments")?.addEventListener("click", () => vLoadTournaments(year));
  }
}

function vResetTeams(placeholder) {
  vTeam1Select.disabled = true;
  vTeam2Select.disabled = true;
  fillSelect(vTeam1Select, [], { blankLabel: placeholder });
  fillSelect(vTeam2Select, [], { blankLabel: placeholder });
  vUpdateAnalyzeState();
}

async function vLoadTeams(tournamentId) {
  vResetTeams("carregando…");
  try {
    const res = await fetch(`/api/valorant/teams-in-tournament?tournament=${encodeURIComponent(tournamentId)}`);
    const data = await res.json();
    if (!res.ok || !Array.isArray(data)) { vResetTeams((data && data.erro) || "Nenhum time encontrado"); return; }
    const options = data.map(t => ({ value: t, label: t }));
    fillSelect(vTeam1Select, options, { blankLabel: "selecione…" });
    fillSelect(vTeam2Select, options, { blankLabel: "selecione…" });
    vTeam1Select.disabled = false;
    vTeam2Select.disabled = false;
  } catch (e) {
    vResetTeams("erro ao carregar times");
  }
  vUpdateAnalyzeState();
}

function vUpdateAnalyzeState() {
  const ok = vTeam1Select.value && vTeam2Select.value && vTeam1Select.value !== vTeam2Select.value;
  vAnalyzeBtn.disabled = !ok;
}

function vSwitchSubTab(tab) {
  document.querySelectorAll('#v-results .market-tab-btn').forEach(b => b.classList.toggle("active", b.dataset.vtab === tab));
  document.getElementById("v-winrate-wrap").classList.toggle("hidden", tab !== "winrate");
  document.getElementById("v-mapas-wrap").classList.toggle("hidden", tab !== "mapas");
  if (tab === "mapas") vLoadMapsPicker();
}

async function vOnCompareClick() {
  const team1 = vTeam1Select.value, team2 = vTeam2Select.value;
  if (!team1 || !team2 || team1 === team2) return;

  vAnalyzeBtn.disabled = true;
  const original = vAnalyzeBtn.textContent;
  vAnalyzeBtn.textContent = "COMPARANDO...";
  vResults.classList.remove("hidden");
  document.getElementById("v-winrate-wrap").innerHTML = `<p class="hint">Comparando times…</p>`;
  vSwitchSubTab("winrate");

  try {
    const res = await fetch("/api/valorant/compare", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ team1, team2, limit: parseInt(document.getElementById("v-limit").value, 10), tournament: vCurrentTournamentId }),
    });
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("v-winrate-wrap").innerHTML = `<div class="error-box">${data.erro || "Erro ao comparar."}</div>`;
      return;
    }
    vLastCompareData = data;
    renderVWinRate(data);
  } catch (e) {
    document.getElementById("v-winrate-wrap").innerHTML = `<div class="error-box">Não foi possível falar com o servidor local.</div>`;
  } finally {
    vAnalyzeBtn.disabled = false;
    vAnalyzeBtn.textContent = original;
  }
}

function vH2hBlock(h2h, nome1, nome2) {
  if (!h2h) return `<p class="hint">Nenhum confronto direto entre esses dois times no histórico.</p>`;
  const marks = h2h.ultimos_resultados.map(r => {
    const w1 = r.vencedor === "time1";
    return `<span class="h2h-mark ${w1 ? 'w1' : 'w2'}" title="${r.mapa} · ${r.placar}">${w1 ? '●' : '○'}</span>`;
  }).join("");
  return `
    <div class="h2h-row">
      <div class="h2h-score">${h2h.vitorias_time1} <small>${nome1}</small></div>
      <div class="h2h-mid">${h2h.mapas} mapa(s) direto(s)</div>
      <div class="h2h-score">${h2h.vitorias_time2} <small>${nome2}</small></div>
    </div>
    <div class="h2h-marks">${marks}</div>
    <p class="hint">● = vitória de ${nome1} · ○ = vitória de ${nome2} no mapa (passe o mouse pra ver qual mapa e o placar)</p>
  `;
}

function vWinRateRow(label, b1, b2) {
  const fmt = b => b ? `${b.taxa_vitoria_pct}% <span class="na">(${b.vitorias}/${b.jogos})</span>` : "—";
  let cls1 = "", cls2 = "";
  if (b1 && b2 && b1.taxa_vitoria_pct !== b2.taxa_vitoria_pct) {
    cls1 = b1.taxa_vitoria_pct > b2.taxa_vitoria_pct ? "win" : "";
    cls2 = b2.taxa_vitoria_pct > b1.taxa_vitoria_pct ? "win" : "";
  }
  return `<tr><td class="${cls1}">${fmt(b1)}</td><td class="cr-label">${label}</td><td class="${cls2}">${fmt(b2)}</td></tr>`;
}

function renderVWinRate(data) {
  const t1 = data.time1, t2 = data.time2;
  document.getElementById("v-winrate-wrap").innerHTML = `
    <div class="vs-title">${t1.nome} <span>vs</span> ${t2.nome}</div>
    <div class="panel">
      <div class="panel-head"><h2>Confronto direto (histórico completo)</h2></div>
      ${vH2hBlock(t1.confronto_direto, t1.nome, t2.nome)}
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Win Rate (por mapa)</h2></div>
      <table class="cr-table">
        <tbody>
          ${vWinRateRow("Nos jogos analisados", t1.overall, t2.overall)}
          ${vWinRateRow("Últimos 5 mapas", t1.recent_5, t2.recent_5)}
          ${vWinRateRow("Últimos 10 mapas", t1.recent_10, t2.recent_10)}
        </tbody>
      </table>
    </div>
  `;
}

async function vLoadMapsPicker() {
  const wrap = document.getElementById("v-mapas-wrap");
  if (!vLastCompareData) return;
  const t1 = vLastCompareData.time1.nome, t2 = vLastCompareData.time2.nome;
  wrap.innerHTML = `<p class="hint">Carregando lista de mapas…</p>`;
  try {
    const res = await fetch(`/api/valorant/maps?team1=${encodeURIComponent(t1)}&team2=${encodeURIComponent(t2)}&tournament=${encodeURIComponent(vCurrentTournamentId || "")}`);
    const maps = await res.json();
    if (!Array.isArray(maps) || maps.length === 0) {
      wrap.innerHTML = `<p class="hint">Nenhum mapa em comum encontrado pra esses times nesse recorte.</p>`;
      return;
    }
    wrap.innerHTML = `
      <div class="market-tabs-bar" id="v-map-picker">
        ${maps.map((m, i) => `<button type="button" class="market-tab-btn map-btn ${i === 0 ? 'active' : ''}" data-map="${m}">${m}</button>`).join("")}
      </div>
      <div id="v-map-detail-wrap"></div>
    `;
    document.querySelectorAll("#v-map-picker .map-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#v-map-picker .map-btn").forEach(b => b.classList.toggle("active", b === btn));
        vLoadMapDetail(btn.dataset.map);
      });
    });
    vLoadMapDetail(maps[0]);
  } catch (e) {
    wrap.innerHTML = `<div class="error-box">Não foi possível carregar os mapas.</div>`;
  }
}

function vPlayersTable(block) {
  if (!block || !block.jogadores.length) return `<p class="hint">Sem dados de jogadores nesse mapa.</p>`;
  const rows = block.jogadores.map(j => `
    <tr>
      <td class="cr-label" style="text-align:left">${j.jogador}</td>
      <td>${j.agente_mais_jogado || "—"}</td>
      <td>${j.media_rating}</td>
      <td>${j.media_acs}</td>
      <td>${j.media_kills}</td>
      <td>${j.media_deaths}</td>
      <td>${j.media_assists}</td>
      <td>${j.media_adr}</td>
      <td>${j.media_hs_pct}%</td>
    </tr>
  `).join("");
  return `
    <p class="stat-line" style="justify-content:flex-start; gap:1.5rem;">
      <span><b>${block.vitorias}</b> vitórias</span>
      <span><b>${block.derrotas}</b> derrotas</span>
      <span><b>${block.taxa_vitoria_pct}%</b> aproveitamento</span>
      <span><b>${block.jogos}</b> mapas jogados</span>
    </p>
    <div class="tt-table-scroll">
      <table class="tt-table">
        <thead><tr>
          <th style="text-align:left">Jogador</th><th>Agente+</th><th>Rating</th><th>ACS</th>
          <th>Kills</th><th>Mortes</th><th>Assist.</th><th>ADR</th><th>HS%</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function vLoadMapDetail(mapName) {
  const wrap = document.getElementById("v-map-detail-wrap");
  wrap.innerHTML = `<p class="hint">Carregando ${mapName}…</p>`;
  const t1 = vLastCompareData.time1.nome, t2 = vLastCompareData.time2.nome;
  try {
    const res = await fetch(`/api/valorant/map-detail?team1=${encodeURIComponent(t1)}&team2=${encodeURIComponent(t2)}&map=${encodeURIComponent(mapName)}&tournament=${encodeURIComponent(vCurrentTournamentId || "")}`);
    const data = await res.json();
    wrap.innerHTML = `
      <div class="panel">
        <div class="panel-head"><h2>${mapName} — ${t1}</h2></div>
        ${data.time1 ? vPlayersTable(data.time1) : `<p class="hint">${t1} não jogou esse mapa nesse recorte.</p>`}
      </div>
      <div class="panel">
        <div class="panel-head"><h2>${mapName} — ${t2}</h2></div>
        ${data.time2 ? vPlayersTable(data.time2) : `<p class="hint">${t2} não jogou esse mapa nesse recorte.</p>`}
      </div>
    `;
  } catch (e) {
    wrap.innerHTML = `<div class="error-box">Não foi possível carregar o detalhe do mapa.</div>`;
  }
}

// ---------------------------------------------------------------------------
// Stats ao vivo (importado de CSV manual)
// ---------------------------------------------------------------------------

const vlCampeonatoSelect = document.getElementById("vl-campeonato");
const vlMapaSelect = document.getElementById("vl-mapa");
const vlWrap = document.getElementById("vl-wrap");
const vlCampeonatoCmpSelect = document.getElementById("vl-campeonato-cmp");
const vlTeam1Select = document.getElementById("vl-team1");
const vlTeam2Select = document.getElementById("vl-team2");
const vlCompareBtn = document.getElementById("vl-compare-btn");
const vlCompareWrap = document.getElementById("vl-compare-wrap");
let vlSortKey = "rating";
let vlSortDir = "desc";
let vlRowsCache = [];

async function vlInit() {
  try {
    const res = await fetch("/api/valorant-live/status");
    const status = await res.json();
    if (!status.disponivel) {
      vlWrap.innerHTML = `<p class="hint">Nenhum arquivo encontrado em data/valorant_live/ ainda.</p>`;
      return;
    }
    fillSelect(vlCampeonatoSelect, status.campeonatos.map(c => ({ value: c, label: c })), { blankLabel: "todos" });
    fillSelect(vlMapaSelect, status.mapas.map(m => ({ value: m, label: m })), { blankLabel: "todos" });
    fillSelect(vlCampeonatoCmpSelect, status.campeonatos.map(c => ({ value: c, label: c })), { blankLabel: "selecione…" });
    vlWrap.innerHTML = `<p class="hint">${status.linhas} linhas carregadas de ${status.arquivos.join(", ")}.</p>`;
    vlLoadRows();
  } catch (e) {
    vlWrap.innerHTML = `<div class="error-box">Não foi possível carregar o status.</div>`;
  }
}
// (vlInit é chamado quando a aba Valorant é aberta, junto com vCheckAndBoot)

vlCampeonatoSelect.addEventListener("change", vlLoadRows);
vlMapaSelect.addEventListener("change", vlLoadRows);

async function vlLoadRows() {
  vlWrap.innerHTML = `<p class="hint">Carregando…</p>`;
  const params = new URLSearchParams();
  if (vlCampeonatoSelect.value) params.set("campeonato", vlCampeonatoSelect.value);
  if (vlMapaSelect.value) params.set("mapa", vlMapaSelect.value);
  try {
    const res = await fetch(`/api/valorant-live/rows?${params.toString()}`);
    const rows = await res.json();
    vlRowsCache = rows;
    vlRenderTable();
  } catch (e) {
    vlWrap.innerHTML = `<div class="error-box">Não foi possível carregar os dados.</div>`;
  }
}

const VL_COLUMNS = [
  { key: "jogador", label: "Jogador", numeric: false },
  { key: "time", label: "Time", numeric: false },
  { key: "campeonato", label: "Campeonato", numeric: false },
  { key: "mapa", label: "Mapa", numeric: false },
  { key: "agentes_pick_raw", label: "Agentes (pick %)", numeric: false },
  { key: "mapas_jogados", label: "Mapas" },
  { key: "rounds_jogados", label: "Rounds" },
  { key: "rating", label: "Rating" },
  { key: "acs", label: "ACS" },
  { key: "kd", label: "K/D" },
  { key: "kast_pct", label: "KAST%" },
  { key: "adr", label: "ADR" },
];

function vlRenderTable() {
  if (!vlRowsCache.length) {
    vlWrap.innerHTML = `<p class="hint">Nenhuma linha encontrada com esse filtro.</p>`;
    return;
  }
  const sorted = [...vlRowsCache].sort((a, b) => {
    let va = a[vlSortKey], vb = b[vlSortKey];
    if (va === null || va === undefined) va = typeof vb === "string" ? "" : -Infinity;
    if (vb === null || vb === undefined) vb = typeof va === "string" ? "" : -Infinity;
    if (typeof va === "string") return vlSortDir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
    return vlSortDir === "asc" ? va - vb : vb - va;
  }).slice(0, 300);

  const head = `<tr>${VL_COLUMNS.map(c => `
    <th data-key="${c.key}" class="${c.key === vlSortKey ? 'sorted' : ''}">
      ${c.label}${c.key === vlSortKey ? `<span class="sort-arrow">${vlSortDir === 'desc' ? '▼' : '▲'}</span>` : ''}
    </th>
  `).join("")}</tr>`;

  const rows = sorted.map(r => `<tr>${VL_COLUMNS.map(c => `<td${c.numeric === false ? ' style="text-align:left"' : ''}>${r[c.key] ?? "—"}</td>`).join("")}</tr>`).join("");

  vlWrap.innerHTML = `
    <p class="hint">Mostrando ${sorted.length} de ${vlRowsCache.length} linha(s) (clique numa coluna pra ordenar).</p>
    <div class="tt-table-scroll">
      <table class="tt-table"><thead>${head}</thead><tbody>${rows}</tbody></table>
    </div>
  `;
  vlWrap.querySelectorAll("th[data-key]").forEach(th => {
    th.addEventListener("click", () => {
      const key = th.dataset.key;
      if (vlSortKey === key) vlSortDir = vlSortDir === "desc" ? "asc" : "desc";
      else { vlSortKey = key; vlSortDir = "desc"; }
      vlRenderTable();
    });
  });
}

// ---------------------------------------------------------------------------
// Mini-confronto dentro do "Stats ao vivo" (times/tags do próprio arquivo)
// ---------------------------------------------------------------------------

function vlResetTeamsCmp(placeholder) {
  vlTeam1Select.disabled = true;
  vlTeam2Select.disabled = true;
  fillSelect(vlTeam1Select, [], { blankLabel: placeholder });
  fillSelect(vlTeam2Select, [], { blankLabel: placeholder });
  vlCompareWrap.classList.add("hidden");
  vlUpdateCompareState();
}

function vlUpdateCompareState() {
  const ok = vlTeam1Select.value && vlTeam2Select.value && vlTeam1Select.value !== vlTeam2Select.value;
  vlCompareBtn.disabled = !ok;
}

vlCampeonatoCmpSelect.addEventListener("change", async () => {
  if (!vlCampeonatoCmpSelect.value) { vlResetTeamsCmp("selecione o campeonato primeiro"); return; }
  vlResetTeamsCmp("carregando…");
  try {
    const res = await fetch(`/api/valorant-live/teams?campeonato=${encodeURIComponent(vlCampeonatoCmpSelect.value)}`);
    const teams = await res.json();
    if (!Array.isArray(teams) || !teams.length) { vlResetTeamsCmp("nenhum time encontrado"); return; }
    const options = teams.map(t => ({ value: t, label: t }));
    fillSelect(vlTeam1Select, options, { blankLabel: "selecione…" });
    fillSelect(vlTeam2Select, options, { blankLabel: "selecione…" });
    vlTeam1Select.disabled = false;
    vlTeam2Select.disabled = false;
  } catch (e) {
    vlResetTeamsCmp("erro ao carregar times");
  }
  vlUpdateCompareState();
});

vlTeam1Select.addEventListener("change", vlUpdateCompareState);
vlTeam2Select.addEventListener("change", vlUpdateCompareState);

vlCompareBtn.addEventListener("click", async () => {
  const campeonato = vlCampeonatoCmpSelect.value, t1 = vlTeam1Select.value, t2 = vlTeam2Select.value;
  vlCompareWrap.classList.remove("hidden");
  vlCompareWrap.innerHTML = `<p class="hint">Carregando mapas em comum…</p>`;
  try {
    const res = await fetch(`/api/valorant-live/maps?campeonato=${encodeURIComponent(campeonato)}&team1=${encodeURIComponent(t1)}&team2=${encodeURIComponent(t2)}`);
    const maps = await res.json();
    if (!Array.isArray(maps) || !maps.length) {
      vlCompareWrap.innerHTML = `<p class="hint">Nenhum mapa em comum encontrado pra esses times nesse campeonato.</p>`;
      return;
    }
    vlCompareWrap.innerHTML = `
      <div class="market-tabs-bar" id="vl-map-picker">
        ${maps.map((m, i) => `<button type="button" class="market-tab-btn map-btn ${i === 0 ? 'active' : ''}" data-map="${m}">${m}</button>`).join("")}
      </div>
      <div id="vl-map-detail-wrap"></div>
    `;
    document.querySelectorAll("#vl-map-picker .map-btn").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#vl-map-picker .map-btn").forEach(b => b.classList.toggle("active", b === btn));
        vlLoadMapDetail(campeonato, t1, t2, btn.dataset.map);
      });
    });
    vlLoadMapDetail(campeonato, t1, t2, maps[0]);
  } catch (e) {
    vlCompareWrap.innerHTML = `<div class="error-box">Não foi possível carregar os mapas.</div>`;
  }
});

function vlPlayersTable(block) {
  if (!block || !block.jogadores.length) return `<p class="hint">Sem dados de jogadores nesse mapa.</p>`;
  const rows = block.jogadores.map(j => `
    <tr>
      <td class="cr-label" style="text-align:left">${j.jogador}</td>
      <td>${j.agentes_pick_raw || "—"}</td>
      <td>${j.mapas_jogados ?? "—"}</td>
      <td>${j.rounds_jogados ?? "—"}</td>
      <td>${j.rating ?? "—"}</td>
      <td>${j.acs ?? "—"}</td>
      <td>${j.kd ?? "—"}</td>
      <td>${j.kast_pct !== null && j.kast_pct !== undefined ? j.kast_pct + "%" : "—"}</td>
      <td>${j.adr ?? "—"}</td>
    </tr>
  `).join("");
  return `
    <div class="tt-table-scroll">
      <table class="tt-table">
        <thead><tr>
          <th style="text-align:left">Jogador</th><th>Agentes (pick%)</th><th>Mapas</th><th>Rounds</th>
          <th>Rating</th><th>ACS</th><th>K/D</th><th>KAST%</th><th>ADR</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

async function vlLoadMapDetail(campeonato, t1, t2, mapName) {
  const wrap = document.getElementById("vl-map-detail-wrap");
  wrap.innerHTML = `<p class="hint">Carregando ${mapName}…</p>`;
  try {
    const res = await fetch(`/api/valorant-live/map-detail?campeonato=${encodeURIComponent(campeonato)}&team1=${encodeURIComponent(t1)}&team2=${encodeURIComponent(t2)}&map=${encodeURIComponent(mapName)}`);
    const data = await res.json();
    wrap.innerHTML = `
      <div class="panel">
        <div class="panel-head"><h2>${mapName} — ${t1}</h2></div>
        ${vlPlayersTable(data.time1)}
      </div>
      <div class="panel">
        <div class="panel-head"><h2>${mapName} — ${t2}</h2></div>
        ${vlPlayersTable(data.time2)}
      </div>
    `;
  } catch (e) {
    wrap.innerHTML = `<div class="error-box">Não foi possível carregar o detalhe do mapa.</div>`;
  }
}

// ---------------------------------------------------------------------------
// "Game Time LIVE" — duração estimada a partir de um draft (10 campeões)
// ---------------------------------------------------------------------------

let gtlChampionListCache = null;

function gameTimeLiveHtml(nome1, nome2) {
  const rowSelect = (prefix, i) => `<select id="${prefix}-${i}" class="gtl-champ-select"><option value="">campeão ${i}</option></select>`;
  return `
    <div class="panel">
      <div class="panel-head"><h2>Game Time LIVE — duração estimada pelo draft</h2></div>
      <p class="hint">
        Escolha os 5 campeões de cada time assim que o draft fechar. O app calcula a média de duração
        histórica de cada campeão (priorizando o histórico daquele time específico com o campeão, quando
        existir) e estima a duração da partida com base nesse draft.
      </p>
      <div class="teams-grid">
        <div class="team-input">
          <label>${nome1}</label>
          <div class="gtl-champ-col" id="gtl-col-1">
            ${[1, 2, 3, 4, 5].map(i => rowSelect("gtl-t1", i)).join("")}
          </div>
        </div>
        <div class="vs">VS</div>
        <div class="team-input">
          <label>${nome2}</label>
          <div class="gtl-champ-col" id="gtl-col-2">
            ${[1, 2, 3, 4, 5].map(i => rowSelect("gtl-t2", i)).join("")}
          </div>
        </div>
      </div>
      <button id="gtl-calc-btn" class="cta" disabled>CALCULAR DURAÇÃO ESTIMADA</button>
      <div id="gtl-results"></div>
    </div>
  `;
}

async function ensureChampions() {
  if (gtlChampionListCache) return gtlChampionListCache;
  try {
    const res = await fetch("/api/champions");
    gtlChampionListCache = await res.json();
  } catch (e) {
    gtlChampionListCache = [];
  }
  return gtlChampionListCache;
}

async function initGameTimeLiveWidget(nome1, nome2) {
  const selects = document.querySelectorAll(".gtl-champ-select");
  const calcBtn = document.getElementById("gtl-calc-btn");
  const resultsEl2 = document.getElementById("gtl-results");
  if (!selects.length || !calcBtn) return;

  const champions = await ensureChampions();
  const options = champions.map(c => ({ value: c, label: c }));
  selects.forEach(sel => {
    const placeholder = sel.id.startsWith("gtl-t1") ? `${sel.options[0]?.textContent || "campeão"}` : sel.options[0]?.textContent || "campeão";
    fillSelect(sel, options, { blankLabel: placeholder });
    sel.addEventListener("change", updateGtlCalcState);
  });

  function updateGtlCalcState() {
    const t1vals = [1, 2, 3, 4, 5].map(i => document.getElementById(`gtl-t1-${i}`).value);
    const t2vals = [1, 2, 3, 4, 5].map(i => document.getElementById(`gtl-t2-${i}`).value);
    calcBtn.disabled = t1vals.some(v => !v) || t2vals.some(v => !v);
  }

  calcBtn.addEventListener("click", async () => {
    const t1vals = [1, 2, 3, 4, 5].map(i => document.getElementById(`gtl-t1-${i}`).value);
    const t2vals = [1, 2, 3, 4, 5].map(i => document.getElementById(`gtl-t2-${i}`).value);
    calcBtn.disabled = true;
    const original = calcBtn.textContent;
    calcBtn.textContent = "CALCULANDO...";
    resultsEl2.innerHTML = `<p class="hint">Calculando…</p>`;
    try {
      const res = await fetch("/api/draft-time", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ team1: nome1, team2: nome2, champions_team1: t1vals, champions_team2: t2vals }),
      });
      const data = await res.json();
      if (!res.ok) { resultsEl2.innerHTML = `<div class="error-box">${data.erro || "Erro ao calcular."}</div>`; return; }
      renderGtlResults(data);
    } catch (e) {
      resultsEl2.innerHTML = `<div class="error-box">Não foi possível calcular.</div>`;
    } finally {
      calcBtn.disabled = false;
      calcBtn.textContent = original;
    }
  });
}

function renderGtlResults(data) {
  const resultsEl2 = document.getElementById("gtl-results");
  const rows = data.picks.map(p => `
    <tr>
      <td class="cr-label" style="text-align:left">${p.campeao} <span class="na">(${p.time})</span></td>
      <td>${p.geral ? `${p.geral.media_duracao_min} min (${p.geral.jogos}j)` : "—"}</td>
      <td>${p.do_time ? `${p.do_time.media_duracao_min} min (${p.do_time.jogos}j)` : "—"}</td>
      <td class="${p.fonte_usada === 'time' ? 'win' : ''}">${p.media_usada !== null ? `${p.media_usada} min` : "sem dado"}</td>
    </tr>
  `).join("");

  resultsEl2.innerHTML = `
    <div class="vs-title" style="margin-top:1.4rem;">
      Duração estimada: <span>${data.duracao_prevista_min !== null ? data.duracao_prevista_min + " min" : "sem dados suficientes"}</span>
    </div>
    <p class="hint" style="text-align:center;">baseado em ${data.baseado_em} de ${data.de_total} campeões escolhidos${data.campeoes_sem_dado.length ? ` — sem dado pra: ${data.campeoes_sem_dado.join(", ")}` : ""}</p>
    <div class="tt-table-scroll">
      <table class="tt-table">
        <thead><tr><th style="text-align:left">Campeão (time)</th><th>Média geral</th><th>Média com esse time</th><th>Usada no cálculo</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `;
}

// ---------------------------------------------------------------------------
// "Linha ao vivo" de Total Kills — minuto atual + placar + ouro
// ---------------------------------------------------------------------------

function liveKillLineHtml(nome1, nome2) {
  const rowSelect = (prefix, i) => `<select id="${prefix}-${i}" class="lkl-champ-select"><option value="">campeão ${i} (opcional)</option></select>`;
  return `
    <div class="panel">
      <div class="panel-head"><h2>Linha ao vivo de Kills</h2></div>
      <p class="hint">
        Durante o jogo, digite o minuto atual (e, se quiser, o placar de kills, a diferença de ouro e a
        composição de cada time) pra ver qual seria a linha "justa" de Total de Kills até esse momento,
        baseada no histórico entre esses times, e uma projeção do total final da partida no ritmo atual.
      </p>
      <div class="row-config">
        <label>Minuto atual de jogo
          <input type="number" id="lkl-minuto" min="0" step="1" placeholder="ex: 12">
        </label>
      </div>
      <div class="row-config">
        <label>Kills — ${nome1}
          <input type="number" id="lkl-kills1" min="0" step="1" placeholder="opcional">
        </label>
        <label>Kills — ${nome2}
          <input type="number" id="lkl-kills2" min="0" step="1" placeholder="opcional">
        </label>
      </div>
      <div class="row-config">
        <label>Diferença de ouro atual (em favor de qualquer um dos times, sempre positivo)
          <input type="number" id="lkl-ouro" min="0" step="50" placeholder="opcional">
        </label>
      </div>
      <p class="hint">Composição (opcional) — os 5 campeões de cada time também ajustam a linha, pelo ritmo histórico de kills de cada campeão:</p>
      <div class="teams-grid">
        <div class="team-input">
          <label>${nome1}</label>
          <div class="gtl-champ-col">${[1, 2, 3, 4, 5].map(i => rowSelect("lkl-t1", i)).join("")}</div>
        </div>
        <div class="vs">VS</div>
        <div class="team-input">
          <label>${nome2}</label>
          <div class="gtl-champ-col">${[1, 2, 3, 4, 5].map(i => rowSelect("lkl-t2", i)).join("")}</div>
        </div>
      </div>
      <button id="lkl-calc-btn" class="cta">CALCULAR LINHA AO VIVO</button>
      <div id="lkl-results"></div>
    </div>
  `;
}

function initLiveKillLineWidget(nome1, nome2) {
  const btn = document.getElementById("lkl-calc-btn");
  if (!btn) return;

  ensureChampions().then(champions => {
    const options = champions.map(c => ({ value: c, label: c }));
    document.querySelectorAll(".lkl-champ-select").forEach(sel => {
      const placeholder = sel.options[0]?.textContent || "campeão (opcional)";
      fillSelect(sel, options, { blankLabel: placeholder });
    });
  });

  btn.addEventListener("click", async () => {
    const minuto = parseFloat(document.getElementById("lkl-minuto").value);
    if (isNaN(minuto)) {
      document.getElementById("lkl-results").innerHTML = `<div class="error-box">Informe o minuto atual de jogo.</div>`;
      return;
    }
    const k1 = document.getElementById("lkl-kills1").value;
    const k2 = document.getElementById("lkl-kills2").value;
    const ouro = document.getElementById("lkl-ouro").value;
    const champs1 = [1, 2, 3, 4, 5].map(i => document.getElementById(`lkl-t1-${i}`)?.value).filter(Boolean);
    const champs2 = [1, 2, 3, 4, 5].map(i => document.getElementById(`lkl-t2-${i}`)?.value).filter(Boolean);

    const body = { team1: nome1, team2: nome2, minuto };
    if (k1 !== "") body.kills_time1 = parseFloat(k1);
    if (k2 !== "") body.kills_time2 = parseFloat(k2);
    if (ouro !== "") body.diferenca_ouro = parseFloat(ouro);
    if (champs1.length) body.champions_team1 = champs1;
    if (champs2.length) body.champions_team2 = champs2;

    const resultsEl3 = document.getElementById("lkl-results");
    btn.disabled = true;
    const original = btn.textContent;
    btn.textContent = "CALCULANDO...";
    resultsEl3.innerHTML = `<p class="hint">Calculando…</p>`;
    try {
      const res = await fetch("/api/live-kill-line", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { resultsEl3.innerHTML = `<div class="error-box">${data.erro || "Erro ao calcular."}</div>`; return; }
      renderLklResults(data);
    } catch (e) {
      resultsEl3.innerHTML = `<div class="error-box">Não foi possível calcular.</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = original;
    }
  });
}

function renderLklResults(data) {
  const el = document.getElementById("lkl-results");
  let html = `
    <div class="vs-title" style="margin-top:1.4rem;">
      Linha esperada até o minuto ${data.minuto}: <span>${data.linha_esperada_ate_o_minuto ?? "—"} kills</span>
    </div>
    <p class="hint" style="text-align:center;">baseado em ${data.jogos_na_amostra} jogo(s) — ${data.amostra}</p>
  `;

  if (data.ajuste_por_composicao_pct !== undefined) {
    const compColor = data.ajuste_por_composicao_pct > 0 ? "var(--accent)" : data.ajuste_por_composicao_pct < 0 ? "var(--danger)" : "var(--text)";
    html += `
      <table class="cr-table">
        <tbody>
          ${compareRowSimple("Ajuste pela composição (10 campeões)", `<span style="color:${compColor}">${data.ajuste_por_composicao_pct > 0 ? "+" : ""}${data.ajuste_por_composicao_pct}%</span>`)}
        </tbody>
      </table>
    `;
  }

  if (data.total_atual_informado !== undefined) {
    const ritmoColor = data.ritmo_vs_esperado_pct > 15 ? "var(--accent)" : data.ritmo_vs_esperado_pct < -15 ? "var(--danger)" : "var(--text)";
    html += `
      <table class="cr-table">
        <tbody>
          ${compareRowSimple("Total de kills informado agora", data.total_atual_informado)}
          ${compareRowSimple("Ritmo vs. esperado", `<span style="color:${ritmoColor}">${data.ritmo_vs_esperado_pct > 0 ? "+" : ""}${data.ritmo_vs_esperado_pct}%</span>`)}
          ${data.ajuste_por_ouro_pct !== undefined ? compareRowSimple("Ajuste aplicado pela diferença de ouro", `${data.ajuste_por_ouro_pct > 0 ? "+" : ""}${data.ajuste_por_ouro_pct}%`) : ""}
          ${data.projecao_total_final_min !== undefined ? compareRowSimple("Projeção de total final da partida", `<b>${data.projecao_total_final_min} kills</b>`) : ""}
          ${data.duracao_media_historica_min !== undefined ? compareRowSimple("Duração média histórica desses times", `${data.duracao_media_historica_min} min`) : ""}
        </tbody>
      </table>
      <p class="hint">Isso é uma estimativa simples baseada no ritmo histórico — não considera coisas como troca de meta, patch, ou uma virada repentina no jogo. Use como referência, não como certeza.</p>
    `;
  }

  el.innerHTML = html;
}

function compareRowSimple(label, value) {
  return `<tr><td class="cr-label" colspan="1" style="text-align:left; width:60%;">${label}</td><td style="text-align:right;">${value}</td></tr>`;
}

// ---------------------------------------------------------------------------
// Aba "LoL — Ao Vivo"
// ---------------------------------------------------------------------------

const alMatchSelect = document.getElementById("al-match-select");
const alRefreshBtn = document.getElementById("al-refresh-btn");
const alStatus = document.getElementById("al-status");
const alResults = document.getElementById("al-results");
let alMatchesCache = [];
let alInitialized = false;
let alAutoTimer = null;

document.querySelector('.tab-btn[data-tab="aovivo"]').addEventListener("click", () => {
  if (alInitialized) return;
  alInitialized = true;
  alLoadMatches();
});

alRefreshBtn.addEventListener("click", alLoadMatches);
alMatchSelect.addEventListener("change", () => {
  if (alAutoTimer) { clearInterval(alAutoTimer); alAutoTimer = null; }
  if (alMatchSelect.value) {
    alLoadState();
    alAutoTimer = setInterval(alLoadState, 30000); // atualiza sozinho a cada 30s
  } else {
    alResults.classList.add("hidden");
  }
});

async function alLoadMatches() {
  alMatchSelect.disabled = true;
  alStatus.textContent = "Buscando partidas ao vivo…";
  try {
    const res = await fetch("/api/lol-live/matches");
    const data = await res.json();
    if (!res.ok) { alStatus.textContent = data.erro || "Erro ao buscar partidas."; fillSelect(alMatchSelect, []); return; }
    alMatchesCache = data;
    if (!data.length) {
      alStatus.textContent = "Nenhuma partida oficial rolando ou prestes a começar agora.";
      fillSelect(alMatchSelect, [], { blankLabel: "nenhuma partida ao vivo" });
      return;
    }
    const ESTADO_LABEL = { inprogress: "🔴 AO VIVO", unstarted: "⏳ a começar" };
    const options = data.map((m, i) => ({
      value: i,
      label: `${ESTADO_LABEL[m.estado_mapa] || m.estado_mapa} — ${m.liga || "?"} — ${m.time1} vs ${m.time2} (mapa ${m.numero_mapa})${(!m.time1_no_dataset || !m.time2_no_dataset) ? " ⚠ time não achado no CSV" : ""}`,
    }));
    fillSelect(alMatchSelect, options, { blankLabel: "selecione…" });
    alMatchSelect.disabled = false;
    alStatus.textContent = `${data.length} jogo(s) encontrados.`;
  } catch (e) {
    alStatus.textContent = "Não foi possível falar com o servidor local.";
  }
}

async function alLoadState() {
  const idx = parseInt(alMatchSelect.value, 10);
  const match = alMatchesCache[idx];
  if (!match) return;
  alResults.classList.remove("hidden");

  if (!match.ao_vivo) {
    alResults.innerHTML = `<div class="panel"><p class="hint">Esse mapa ainda não começou (${match.estado_mapa}) — assim que o "AO VIVO" aparecer na lista, escolha de novo.</p></div>`;
    return;
  }
  if (!match.time1_no_dataset || !match.time2_no_dataset) {
    alResults.innerHTML = `<div class="error-box">Não achei "${match.time1}" e/ou "${match.time2}" no seu CSV local — não dá pra calcular a linha sem o histórico desses times no seu dataset (o scoreboard ao vivo abaixo funciona mesmo assim).</div>`;
  }

  try {
    const res = await fetch(`/api/lol-live/state?gameId=${encodeURIComponent(match.game_id)}`);
    const estado = await res.json();
    if (!res.ok) { alResults.innerHTML = `<div class="error-box">${estado.erro || "Erro ao buscar o estado do jogo."}</div>`; return; }

    let calc = null;
    if (match.time1_no_dataset && match.time2_no_dataset) {
      const body = { team1: match.time1_no_dataset, team2: match.time2_no_dataset, minuto: estado.minuto };
      if (estado.kills_time1 !== null && estado.kills_time1 !== undefined) body.kills_time1 = estado.kills_time1;
      if (estado.kills_time2 !== null && estado.kills_time2 !== undefined) body.kills_time2 = estado.kills_time2;
      if (estado.diferenca_ouro !== null && estado.diferenca_ouro !== undefined) body.diferenca_ouro = estado.diferenca_ouro;
      if (estado.champions_team1?.length) body.champions_team1 = estado.champions_team1;
      if (estado.champions_team2?.length) body.champions_team2 = estado.champions_team2;

      const res2 = await fetch("/api/live-kill-line", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      calc = await res2.json();
      if (!res2.ok) calc = null;
    }

    renderAlResults(match, estado, calc);
  } catch (e) {
    alResults.innerHTML = `<div class="error-box">Não foi possível atualizar o estado ao vivo.</div>`;
  }
}

function alObjectivesRow(obj) {
  if (!obj) return "";
  return `
    <span class="al-obj">🗼 ${obj.torres ?? 0}</span>
    <span class="al-obj">🐉 ${obj.dragoes ?? 0}</span>
    <span class="al-obj">👹 ${obj.baroes ?? 0}</span>
    <span class="al-obj">💠 ${obj.arautos ?? 0}</span>
    <span class="al-obj">🏰 ${obj.inibidores ?? 0}</span>
  `;
}

function alScoreboardSide(jogadores) {
  if (!jogadores || !jogadores.length) return `<p class="hint">Sem dados de jogadores ainda.</p>`;
  return jogadores.map(j => `
    <div class="al-player-row">
      <div class="al-player-champ">${j.campeao || "?"}</div>
      <div class="al-player-info">
        <div class="al-player-name">${j.jogador}</div>
        <div class="al-hp-track"><div class="al-hp-fill" style="width:${j.vida_pct ?? 100}%"></div></div>
      </div>
      <div class="al-player-stat">${j.kills}/${j.deaths}/${j.assists}</div>
      <div class="al-player-stat">${j.cs} cs</div>
      <div class="al-player-stat">${Math.round((j.ouro || 0) / 100) / 10}k</div>
    </div>
  `).join("");
}

function renderAlResults(match, estado, calc) {
  const nome1 = match.time1_no_dataset || match.time1;
  const nome2 = match.time2_no_dataset || match.time2;
  let html = `
    <div class="vs-title">${nome1} <span>vs</span> ${nome2}</div>
    <p class="hint" style="text-align:center;">
      ${match.liga} — mapa ${match.numero_mapa} — minuto ${estado.minuto ?? "?"} · atualiza sozinho a cada 30s
    </p>

    <div class="panel">
      <div class="panel-head"><h2>Scoreboard ao vivo</h2></div>
      <div class="al-obj-row">
        <div>${alObjectivesRow(estado.objetivos_time1)}</div>
        <div class="al-gold-diff">${estado.diferenca_ouro !== null && estado.diferenca_ouro !== undefined ? `💰 dif. de ouro: ${estado.diferenca_ouro}` : ""}</div>
        <div>${alObjectivesRow(estado.objetivos_time2)}</div>
      </div>
      <div class="al-scoreboard">
        <div>${alScoreboardSide(estado.jogadores_time1)}</div>
        <div>${alScoreboardSide(estado.jogadores_time2)}</div>
      </div>
    </div>
  `;

  if (calc) {
    html += `
      <div class="panel">
        <div class="panel-head"><h2>Total esperado de kills</h2></div>
        <div class="al-big-numbers">
          <div class="al-big-num-box">
            <div class="al-big-num">${calc.linha_base_pre_jogo ?? "—"}</div>
            <div class="al-big-num-label">pós-draft</div>
          </div>
          <div class="al-big-num-box accent">
            <div class="al-big-num">${calc.linha_justa_agora ?? "—"}</div>
            <div class="al-big-num-label">ao vivo</div>
          </div>
        </div>
        <table class="cr-table">
          <tbody>
            ${calc.ajuste_por_composicao_pct !== undefined ? compareRowSimple("Ajuste pela composição", `${calc.ajuste_por_composicao_pct > 0 ? "+" : ""}${calc.ajuste_por_composicao_pct}%`) : ""}
            ${calc.total_atual_informado !== undefined ? compareRowSimple("Kills no placar agora", calc.total_atual_informado) : ""}
            ${calc.ritmo_vs_esperado_pct !== undefined ? compareRowSimple("Ritmo vs. esperado", `${calc.ritmo_vs_esperado_pct > 0 ? "+" : ""}${calc.ritmo_vs_esperado_pct}%`) : ""}
            ${calc.ajuste_por_ouro_pct !== undefined ? compareRowSimple("Ajuste pela diferença de ouro", `${calc.ajuste_por_ouro_pct > 0 ? "+" : ""}${calc.ajuste_por_ouro_pct}%`) : ""}
          </tbody>
        </table>
        <p class="hint" style="text-align:center;">baseado em ${calc.jogos_na_amostra} jogo(s) — ${calc.amostra}</p>
        <p class="hint">Estimativa baseada no histórico — não considera troca de meta, patch, ou virada repentina no jogo. Use como referência, não como certeza.</p>
      </div>
    `;
  }

  alResults.innerHTML = html;
}
