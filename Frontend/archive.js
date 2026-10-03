const COMPLETED_REPORTS_KEY = "palermo-completed-reports-v1";

function completedReports() {
  const rows = readStored(COMPLETED_REPORTS_KEY, []);
  if (!Array.isArray(rows)) return [];
  return rows.filter((r) => r?.version === 1 && typeof r.gameId === "string" &&
    r.public?.phase === "GAME_OVER" && Array.isArray(r.events) &&
    characters.some((c) => c.id === r.characterId));
}

function saveCompletedReport() {
  if (state.archiveMode || !state.gameId || state.public?.phase !== "GAME_OVER") return;
  const report = {
    version: 1, gameId: state.gameId, characterId: state.characterId, lang: state.lang,
    public: state.public, private: state.private, events: state.events,
    nightReplay: state.nightReplay, playerNames: state.playerNames, notes: state.notes,
    // Deliberate allowlist: credentials and transient runner data are never archived.
    run: { status: "COMPLETED", summary: state.run?.summary, ai_model: state.run?.ai_model },
    savedAt: new Date().toISOString(),
  };
  const reports = completedReports();
  const previous = reports.find((r) => r.gameId === state.gameId);
  if (previous) report.savedAt = previous.savedAt;
  try {
    localStorage.setItem(COMPLETED_REPORTS_KEY, JSON.stringify([report, ...reports.filter((r) => r.gameId !== state.gameId)]));
  } catch {
    if (!state.archiveSaveFailed) toast(journalText("storageError"));
    state.archiveSaveFailed = true;
  }
}

function renderArchives() {
  const container = $("#completed-reports");
  if (!container) return;
  const reports = completedReports();
  if (!reports.length) { container.innerHTML = ""; return; }
  container.innerHTML = `<details><summary>${journalText("archive")} (${reports.length})</summary><p>${journalText("local")}</p><ul>${reports.map((r, index) => {
    const date = new Date(r.savedAt);
    const formatted = Number.isNaN(date.valueOf()) ? "" : date.toLocaleString(state.lang);
    const winner = text("roles")[r.public.winner] || r.public.winner || "—";
    return `<li><button type="button" data-open-report="${index}"><b>${escapeHTML(formatted)}</b><span>${escapeHTML(`${text("winner")}: ${winner} · ${journalText("round")} ${r.public.round}`)}</span><small>${escapeHTML(r.gameId)}</small></button></li>`;
  }).join("")}</ul></details>`;
  $$('[data-open-report]', container).forEach((button) => button.addEventListener("click", () => openCompletedReport(reports[Number(button.dataset.openReport)])));
}

function openCompletedReport(report) {
  if (!report || report.public?.phase !== "GAME_OVER") return;
  if (state.eventSource) state.eventSource.close();
  window.clearTimeout(syncTimer);
  syncAgain = false;
  syncNeedsRoute = false;
  state.archiveMode = true;
  state.gameId = report.gameId;
  state.characterId = report.characterId;
  state.characterMap = buildCharacterMap(report.characterId);
  state.token = null;
  state.observationUrl = null;
  state.availableActions = [];
  state.public = report.public;
  state.private = report.private;
  state.events = report.events;
  state.nightReplay = report.nightReplay || [];
  state.playerNames = report.playerNames || {};
  state.notes = report.notes || { text: "", suspicion: {} };
  state.run = { ...report.run, status: "COMPLETED" };
  state.consoleTab = "timeline";
  state.journalFilters = { round: "", player: "", kind: "" };
  showScreen("story-screen");
  showGameOver();
  $("#round-label").textContent = journalText("readOnly");
  $("#agent-status").textContent = "";
  setFactsOpen(true);
}
