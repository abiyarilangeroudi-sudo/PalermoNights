// Rendering only: raw events remain intact for audit and game progression.
function journalText(key) {
  const labels = {
    fa: { day: "روز", night: "شب", votes: "رأی‌گیری", detail: "جزئیات آرا", voter: "رأی‌دهنده", target: "به", count: "رأی", pending: "رأی‌گیری ادامه دارد", discussion: "گفت‌وگوها", question: "پرسش", answer: "پاسخ", waiting: "منتظر پاسخ", claim: "ادعای بازیکن", fact: "واقعیت عمومی", unknown: "علت دقیق برای عموم آشکار نیست.", unavailable: "جزئیات علت این شب در نسخهٔ قدیمی ثبت نشده است.", protected: "حفاظت موفق؛ هدف حمله نجات یافت", killed: "حمله موفق بود", blocked: "مهاجم از اقدام شبانه محروم بود", noAttacker: "مهاجم فعالی باقی نمانده بود", noAttack: "حمله‌ای ثبت نشد", attack: "هدف حمله", protection: "هدف حفاظت", replay: "بازپخش پس از پایان", none: "هیچ‌کس", rule: "در این شب طرد بود: توانایی شبانه ندارد و هدف مجاز استعلام یا حفاظت نیست.", will: "وصیت", rejected: "ادعا با نقش آشکارشده ناسازگار است", intro: "روزها و شب‌ها، نتیجهٔ رأی‌ها و گفت‌وگوهای مرتبط؛ اطلاعات خصوصی در تب جداست.", noResult: "هنوز نتیجهٔ شب ثبت نشده است." },
    en: { day: "Day", night: "Night", votes: "Voting", detail: "All votes", voter: "Voter", target: "For", count: "votes", pending: "Voting in progress", discussion: "Discussion", question: "Question", answer: "Answer", waiting: "Awaiting answer", claim: "Player claim", fact: "Public fact", unknown: "The exact cause is not public.", unavailable: "This older match did not record the cause.", protected: "Protection succeeded; the target survived", killed: "The attack succeeded", blocked: "The attacker was blocked", noAttacker: "No active attacker remained", noAttack: "No attack was recorded", attack: "Attack target", protection: "Protected target", replay: "Post-game replay", none: "Nobody", rule: "Shunned this night: cannot act or be investigated or protected.", will: "Will", rejected: "Claim conflicts with a revealed role", intro: "Days, nights, voting results and linked conversations. Private information has its own tab.", noResult: "No night result yet." },
    de: { day: "Tag", night: "Nacht", votes: "Abstimmung", detail: "Alle Stimmen", voter: "Wähler", target: "Für", count: "Stimmen", pending: "Abstimmung läuft", discussion: "Gespräche", question: "Frage", answer: "Antwort", waiting: "Antwort ausstehend", claim: "Spielerbehauptung", fact: "Öffentliche Tatsache", unknown: "Die genaue Ursache ist nicht öffentlich.", unavailable: "Die Ursache wurde in dieser älteren Partie nicht gespeichert.", protected: "Schutz erfolgreich; das Ziel überlebte", killed: "Angriff erfolgreich", blocked: "Der Angreifer war gesperrt", noAttacker: "Kein aktiver Angreifer übrig", noAttack: "Kein Angriff gespeichert", attack: "Angriffsziel", protection: "Geschütztes Ziel", replay: "Rückblick nach Spielende", none: "Niemand", rule: "Diese Nacht ausgeschlossen: keine Nachtaktion; kein zulässiges Ermittlungs- oder Schutzziel.", will: "Testament", rejected: "Behauptung widerspricht einer aufgedeckten Rolle", intro: "Tage, Nächte, Abstimmungen und verknüpfte Gespräche. Private Informationen stehen separat.", noResult: "Noch kein Nachtergebnis." },
  };
  const extras = {
    fa: { mafiaScenario: "سناریوی مافیا", scenarioPending: "هنوز انتخاب نشده است", filters: "فیلترها", nightDetails: "جزئیات شب", player: "بازیکن", round: "دور", all: "همه", kind: "نوع رویداد", filterHint: "دورهای دارای تطابق نمایش داده می‌شوند؛ جدول آرا و رشتهٔ پاسخ‌ها کامل می‌مانند.", archive: "گزارش بازی‌های تمام‌شده", local: "فقط در همین مرورگر ذخیره می‌شود؛ پاک‌کردن داده‌های مرورگر این گزارش‌ها را حذف می‌کند.", readOnly: "گزارش ذخیره‌شده — فقط برای مرور", storageError: "گزارش در مرورگر ذخیره نشد؛ فضای ذخیره‌سازی را بررسی کن." },
    en: { mafiaScenario: "Mafia scenario", scenarioPending: "Not selected yet", filters: "Filters", nightDetails: "Night details", player: "Player", round: "Round", all: "All", kind: "Event type", filterHint: "Matching rounds are shown with complete vote tables and answer threads.", archive: "Completed game reports", local: "Stored only in this browser. Clearing browser data removes these reports.", readOnly: "Saved report — read only", storageError: "Could not save the report. Check browser storage." },
    de: { mafiaScenario: "Mafia-Szenario", scenarioPending: "Noch nicht ausgewählt", filters: "Filter", nightDetails: "Nachtdetails", player: "Spieler", round: "Runde", all: "Alle", kind: "Ereignistyp", filterHint: "Passende Runden mit vollständigen Stimmtabellen und Antworten werden angezeigt.", archive: "Berichte abgeschlossener Spiele", local: "Nur in diesem Browser gespeichert. Beim Löschen der Browserdaten gehen die Berichte verloren.", readOnly: "Gespeicherter Bericht — nur lesen", storageError: "Bericht konnte nicht gespeichert werden. Browserspeicher prüfen." },
  };
  return (labels[state.lang] || labels.en)[key] || (extras[state.lang] || extras.en)[key];
}

function journalDisclosure(key, label, body, open = false) {
  return `<details class="journal-group" data-journal-key="${escapeHTML(key)}"${open ? " open" : ""}><summary>${escapeHTML(label)}</summary><div class="journal-body">${body}</div></details>`;
}

function journalParagraph(value, kind = "") {
  return `<p${kind ? ` class="${kind}"` : ""}>${escapeHTML(value)}</p>`;
}

function journalOutcome(event, events) {
  const will = events.find((item) => item.type === "WILL_REVEALED" && item.player === event.player && (item.text?.trim() || Object.keys(item.trust || {}).length));
  const trust = Object.entries(will?.trust || {}).sort((a,b) => b[1]-a[1]).map(([id, score]) => `<li>${profileImageMarkup(id)}<span>${escapeHTML(playerName(id))}</span><b>${score}</b></li>`).join("");
  const note = state.lang === "fa" ? "آخرین برداشت بازیکن؛ نشان‌دهندهٔ نقش واقعی افراد نیست." : state.lang === "de" ? "Letzte Einschätzung des Spielers, keine bestätigten Rollen." : "The player's last assessment, not confirmed roles.";
  return `<article class="journal-card">${journalParagraph(factEventText(event))}${will ? `<h5>${journalText("will")} — ${escapeHTML(playerName(event.player))}</h5>${will.text ? journalParagraph(will.text) : ""}${trust ? journalParagraph(note, "journal-muted") + `<ul class="will-trust">${trust}</ul>` : ""}` : ""}</article>`;
}

function journalVotes(events, round) {
  const votes = events.filter((e) => e.type === "VOTE_CAST");
  if (!votes.length) return "";
  const tally = new Map();
  votes.forEach((e) => tally.set(e.target, (tally.get(e.target) || 0) + 1));
  const complete = events.some((e) => ["NIGHT_STARTED", "GAME_OVER", "PLAYER_SHUNNED", "PLAYER_ELIMINATED", "VOTE_TIED"].includes(e.type));
  const counts = [...tally].sort((a, b) => b[1] - a[1]).map(([id, count]) => journalParagraph(`${playerName(id)}: ${count} ${journalText("count")}`)).join("");
  const rows = votes.map((e) => `<tr><th scope="row">${escapeHTML(playerName(e.actor))}</th><td>${escapeHTML(playerName(e.target))}${e.position?.reason ? `<small class="journal-muted">${escapeHTML(replacePlayerReferences(e.position.reason))}</small>` : ""}</td></tr>`).join("");
  const table = `<table class="journal-votes"><caption>${journalText("votes")} — ${journalText("day")} ${round}</caption><thead><tr><th scope="col">${journalText("voter")}</th><th scope="col">${journalText("target")}</th></tr></thead><tbody>${rows}</tbody></table>`;
  const results = events.filter((e) => ["PLAYER_SHUNNED", "PLAYER_ELIMINATED"].includes(e.type) && e.phase !== "NIGHT_ACTION");
  return `<section class="journal-card"><h4>${journalText("votes")}</h4>${complete ? "" : journalParagraph(journalText("pending"), "journal-muted")}${results.map((e) => journalOutcome(e, events)).join("")}${complete && !results.length ? journalParagraph(text("tied")) : ""}${journalDisclosure(`votes-${round}`, journalText("detail"), counts + table)}</section>`;
}

function journalDiscussion(events, round) {
  const answers = events.filter((e) => e.type === "PLAYER_ANSWERED");
  const idsFor = (e) => e.question_ids || (e.question_id ? [e.question_id] : []);
  const renderedAnswers = new Set();
  const items = [];
  for (const e of events) {
    if (e.type === "PLAYER_ASKED") {
      const answer = answers.find((a) => idsFor(a).includes(e.question_id));
      if (answer && renderedAnswers.has(answer.event_id)) continue;
      if (answer) renderedAnswers.add(answer.event_id);
      const questions = answer ? events.filter((q) => q.type === "PLAYER_ASKED" && idsFor(answer).includes(q.question_id)) : [e];
      items.push(`<article class="journal-card journal-thread">${questions.map((q) => journalParagraph(`${journalText("question")} — ${eventSummary(q)}`)).join("")}${journalParagraph(answer ? `${journalText("answer")} — ${eventSummary(answer)}` : journalText("waiting"), answer ? "journal-answer" : "journal-muted")}</article>`);
    } else if (e.type === "PLAYER_SPOKE") {
      // Fold exact repetition into its answer thread; never merge merely similar claims.
      if (answers.some((a) => a.actor === e.actor && a.text?.trim() === e.text?.trim())) continue;
      items.push(`<article class="journal-card">${profileImageMarkup(e.actor)}${journalParagraph(eventSummary(e))}</article>`);
    }
  }
  // Keep an answer visible even if an older server omitted its question.
  answers.filter((a) => !renderedAnswers.has(a.event_id)).forEach((a) => items.push(journalParagraph(eventSummary(a))));
  return items.length ? journalDisclosure(`discussion-${round}`, journalText("discussion"), items.join("")) : "";
}

function journalNight(events, round) {
  const result = events.find((e) => e.type === "NIGHT_RESULT");
  if (!result && !events.some((e) => e.type === "NIGHT_STARTED")) return "";
  const blocks = events.filter((e) => e.type === "PLAYER_SHUNNED").map((e) => journalParagraph(`${playerName(e.player)} — ${journalText("rule")}`, "journal-rule")).join("");
  const outcome = result ? (result.player ? journalOutcome(result, events) : journalParagraph(factEventText(result))) : journalParagraph(journalText("noResult"));
  let body = blocks;
  if (state.public.phase === "GAME_OVER") {
    const replay = (state.nightReplay || []).find((n) => n.round === round);
    if (replay) {
      const reasons = { PROTECTED: "protected", KILLED: "killed", ATTACKER_BLOCKED: "blocked", NO_ACTIVE_ATTACKER: "noAttacker", NO_ATTACK: "noAttack" };
      body += `<div class="journal-replay"><small>${journalText("replay")}</small>${journalParagraph(journalText(reasons[replay.reason] || "unavailable"))}${journalParagraph(`${journalText("attack")}: ${replay.attack_target ? playerName(replay.attack_target) : journalText("none")}`)}${journalParagraph(`${journalText("protection")}: ${replay.protected_target ? playerName(replay.protected_target) : journalText("none")}`)}</div>`;
    } else if (result) body += journalParagraph(journalText("unavailable"), "journal-muted");
  } else if (result?.result === "NO_DEATH") body += journalParagraph(journalText("unknown"), "journal-muted");
  return `<section class="journal-night"><h4>${journalText("night")} ${round}</h4>${outcome}${body ? journalDisclosure(`night-${round}`, journalText("nightDetails"), body) : ""}</section>`;
}

function renderJournal(includeDiscussion = true) {
  const events = state.events.filter((e) => e.visibility === "PUBLIC");
  const filters = { kind: "" };
  const matches = events;
  const rounds = [...new Set(matches.map((e) => e.round).filter(Boolean))].sort((a, b) => b - a);
  return rounds.map((round, index) => {
    const items = events.filter((e) => e.round === round);
    const finished = items.find((e) => e.type === "GAME_OVER");
    const conclusion = finished ? journalParagraph(`${text("gameOver")} — ${text("winner")}: ${text("roles")[finished.winner] || finished.winner}`) : "";
    const body = (includeDiscussion && (!filters.kind || filters.kind === "discussion") ? journalDiscussion(items, round) : "") +
      (!filters.kind || filters.kind === "votes" ? journalVotes(items, round) : "") +
      (!filters.kind || filters.kind === "night" ? journalNight(items, round) : "") + conclusion;
    return journalDisclosure(`round-${round}`, `${journalText("day")} ${round}`, body || journalParagraph(text("factsEmpty")), index === 0);
  }).join("") || journalParagraph(text("factsEmpty"));
}
