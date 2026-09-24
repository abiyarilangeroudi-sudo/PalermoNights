const $ = (selector) => document.querySelector(selector);

const playerImages = Object.fromEntries(
  Array.from({ length: 7 }, (_, index) => [`P${index + 1}`, `/ui/Images/Character_${index + 1}.jpeg`]),
);

const phaseCopy = {
  NIGHT_1_MAFIA: ["شب اول", "شهر هنوز از رازها خبر ندارد.", "مافیا استراتژی خود را انتخاب می‌کند.", "Silhouettes_having_secret_conver.jpeg"],
  ROLE_CLAIM: ["ادعاها", "هر حقیقت می‌تواند یک دروغ باشد.", "بازیکنان نقش عمومی خود را اعلام می‌کنند.", "Person_reading_newspaper_in_city.jpeg"],
  DAY_DISCUSSION: ["بحث روز", "شهر به صداها گوش می‌دهد.", "تناقض‌ها، سؤال‌ها و اتحادها در دفتر وقایع ثبت می‌شوند.", "Townspeople_voting_in_town_square.jpeg"],
  DAY_VOTING: ["رأی‌گیری", "اکنون باید یک نفر را انتخاب کرد.", "رأی، مظنون دوم و اعتماد هر بازیکن ثبت می‌شود.", "Townspeople_voting_in_town_square.jpeg"],
  NIGHT_ACTION: ["شب", "خیابان‌ها دوباره خالی شده‌اند.", "عملیات مخفی در سکوت و دور از چشم شهر انجام می‌شود.", "Silhouette_holding_handgun_in_alley.jpeg"],
  GAME_OVER: ["پایان بازی", "راز شهر آشکار شد.", "نتیجه نهایی در دفتر وقایع ثبت شده است.", "Person_reading_newspaper_in_city.jpeg"],
};

const eventLabels = {
  GAME_CREATED: "بازی ساخته شد",
  MAFIA_STRATEGY_SELECTED: "استراتژی مافیا انتخاب شد",
  ROLE_CLAIMED: "ادعای نقش ثبت شد",
  DISCUSSION_STARTED: "بحث شهر آغاز شد",
  PLAYER_SPOKE: "بازیکن صحبت کرد",
  PLAYER_ASKED: "یک سؤال عمومی مطرح شد",
  PLAYER_ANSWERED: "پاسخ سؤال ثبت شد",
  PLAYER_PASSED: "بازیکن از نوبت گفتگو گذشت",
  VOTE_CAST: "رأی ثبت شد",
  VOTE_TIED: "رأی‌ها مساوی شد",
  PLAYER_SHUNNED: "یک بازیکن برای شب طرد شد",
  NIGHT_STARTED: "شب آغاز شد",
  NIGHT_RESULT: "نتیجه شب اعلام شد",
  SHUN_CLEARED: "اثر طرد پایان یافت",
  PLAYER_ELIMINATED: "بازیکن حذف شد",
  ROLE_REVEALED: "نقش بازیکن آشکار شد",
  WILL_REVEALED: "وصیت بازیکن خوانده شد",
  GAME_OVER: "بازی پایان یافت",
};

let currentGameId = null;
let eventSource = null;
let refreshQueued = false;

function renderPlayers(state) {
  const claims = state.role_claims || {};
  const revealed = state.revealed_roles || {};
  $("#players").innerHTML = Object.entries(state.players).map(([id, player]) => {
    const classes = ["player-card", !player.alive ? "dead" : "", player.shunned ? "shunned" : ""].filter(Boolean).join(" ");
    const label = revealed[id] ? `نقش: ${revealed[id]}` : claims[id] ? `ادعا: ${claims[id]}` : "بدون ادعا";
    return `<article class="${classes}">
      <img src="${playerImages[id]}" alt="پرتره ${id}" />
      <div class="player-meta"><h4>${id}</h4><p>${label}</p></div>
    </article>`;
  }).join("");
  $("#alive-count").textContent = `${state.alive_players.length} بازیکن زنده`;
}

function renderScene(state) {
  const [kicker, heading, detail, image] = phaseCopy[state.phase] || phaseCopy.NIGHT_1_MAFIA;
  $("#phase-title").textContent = heading;
  $("#scene-kicker").textContent = kicker;
  $("#scene-heading").textContent = heading;
  $("#scene-detail").textContent = state.winner ? `برنده: ${state.winner}` : detail;
  const imageElement = $("#scene-image");
  const nextSource = `/ui/Images/${image}`;
  if (!imageElement.src.endsWith(nextSource)) imageElement.src = nextSource;
  $("#round-badge").textContent = `روز ${state.round}`;
}

function eventDescription(event) {
  const actor = event.actor || event.player;
  const target = event.target;
  const suffix = actor ? ` — ${actor}${target ? ` ← ${target}` : ""}` : "";
  if (event.type === "NIGHT_RESULT") {
    return event.result === "NO_DEATH" ? "امشب هیچ‌کس کشته نشد" : `${event.player} در شب کشته شد`;
  }
  if (event.type === "GAME_OVER") return `برنده: ${event.winner}`;
  return `${eventLabels[event.type] || event.type}${suffix}`;
}

function appendEvent(event) {
  const list = $("#timeline");
  const item = document.createElement("li");
  item.innerHTML = `<time>روز ${event.round} · ${event.phase}</time>${eventDescription(event)}`;
  list.appendChild(item);
  while (list.children.length > 80) list.removeChild(list.firstChild);
  list.scrollTop = list.scrollHeight;
}

async function refreshState() {
  if (!currentGameId || refreshQueued) return;
  refreshQueued = true;
  try {
    const [stateResponse, runResponse] = await Promise.all([
      fetch(`/game/${currentGameId}/public-state`),
      fetch(`/game/${currentGameId}/run-state`),
    ]);
    if (!stateResponse.ok || !runResponse.ok) throw new Error("state unavailable");
    const state = await stateResponse.json();
    const run = await runResponse.json();
    renderPlayers(state);
    renderScene(state);
    renderRunState(run);
  } finally {
    refreshQueued = false;
  }
}

function renderRunState(run) {
  const labels = { QUEUED: "در صف", RUNNING: "در حال اجرا", COMPLETED: "کامل شد", FAILED: "خطا", CANCELLED: "لغو شد" };
  $("#run-badge").textContent = labels[run.status] || run.status;
  if (run.last_action) {
    const action = run.last_action;
    $("#last-action").textContent = `حرکت ${run.current_step}: ${action.player_id} · ${action.action} · ${action.source}`;
  }
}

function connectStream(url) {
  if (eventSource) eventSource.close();
  eventSource = new EventSource(url);
  eventSource.addEventListener("open", () => $("#connection-dot").classList.add("online"));
  eventSource.addEventListener("error", () => $("#connection-dot").classList.remove("online"));
  eventSource.addEventListener("game-event", (message) => {
    appendEvent(JSON.parse(message.data));
    refreshState();
  });
  eventSource.addEventListener("run-state", (message) => {
    renderRunState(JSON.parse(message.data));
    refreshState();
  });
  eventSource.addEventListener("stream-end", () => {
    eventSource.close();
    $("#connection-dot").classList.remove("online");
    refreshState();
  });
}

$("#mode").addEventListener("change", (event) => {
  $("#budget-field").classList.toggle("is-hidden", event.target.value !== "live");
});

$("#create-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("#start-button");
  const error = $("#form-error");
  button.disabled = true;
  error.textContent = "";
  try {
    const response = await fetch("/games/ai", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mode: $("#mode").value,
        seed: Number($("#seed").value),
        live_action_budget: Number($("#budget").value),
      }),
    });
    if (!response.ok) {
      const body = await response.json();
      throw new Error(body.detail || "ساخت بازی ناموفق بود");
    }
    const created = await response.json();
    currentGameId = created.game_id;
    $("#game-id").textContent = currentGameId;
    $("#timeline").innerHTML = "";
    $("#lobby").classList.add("is-hidden");
    $("#game").classList.remove("is-hidden");
    await refreshState();
    connectStream(created.stream_url);
  } catch (reason) {
    error.textContent = reason.message;
  } finally {
    button.disabled = false;
  }
});

$("#new-game").addEventListener("click", () => {
  if (eventSource) eventSource.close();
  currentGameId = null;
  $("#game").classList.add("is-hidden");
  $("#lobby").classList.remove("is-hidden");
});
