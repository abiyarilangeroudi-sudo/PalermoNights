const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const assets = {
  town: "/ui/Images/Townspeople_voting_in_town_square.jpeg",
  mafia: "/ui/Images/Silhouette_holding_handgun_in_alley.jpeg",
  doctor: "/ui/Images/Doctor_protecting_patient.jpeg",
  detective: "/ui/Images/Detective_searching_dark_street.jpeg",
  citizen: "/ui/Images/Silhouettes_having_secret_conver.jpeg",
  morning: "/ui/Images/Person_reading_newspaper_in_city.jpeg",
};

const soundAssets = {
  cityMusic: "/ui/Voice/City-Music.mp3",
  mafiaMusic: "/ui/Voice/Mafia-Music.mp3",
  newspaper: "/ui/Voice/newspaper.mp3",
  typewriter: "/ui/Voice/typewriter.mp3",
  footsteps: "/ui/Voice/Footsteps.mp3",
  button: "/ui/Voice/Buttom.mp3",
};

function createAudio(src, loop = false, volume = 1) {
  if (typeof Audio !== "function") return null;
  const audio = new Audio(src);
  audio.preload = "auto";
  audio.loop = loop;
  audio.volume = volume;
  return audio;
}

const audio = {
  cityMusic: createAudio(soundAssets.cityMusic, true, 0.5),
  mafiaMusic: createAudio(soundAssets.mafiaMusic, true, 0.5),
  newspaper: createAudio(soundAssets.newspaper, false, 1),
  typewriter: createAudio(soundAssets.typewriter, true, 1),
  footsteps: createAudio(soundAssets.footsteps, false, 1),
  button: createAudio(soundAssets.button, false, 1),
};

function playAudio(track, restart = false) {
  if (!track) return;
  if (restart) track.currentTime = 0;
  const result = track.play();
  if (result?.catch) result.catch(() => {});
}

function stopAudio(track, reset = false) {
  if (!track) return;
  track.pause();
  if (reset) track.currentTime = 0;
}

function playEffect(name, restart = true) {
  playAudio(audio[name], restart);
}

function stopEffect(name, reset = true) {
  stopAudio(audio[name], reset);
}

function setBackgroundMusic(trackName) {
  const active = audio[trackName];
  [audio.cityMusic, audio.mafiaMusic].forEach((track) => {
    if (track && track !== active) stopAudio(track, true);
  });
  playAudio(active);
}

function isMafiaRole(role) {
  return role === "MAFIA_BOSS" || role === "MAFIA_DEPUTY";
}

function storyMusic(number) {
  return isMafiaRole(state.private?.role) || (number >= 8 && number <= 11)
    ? "mafiaMusic"
    : "cityMusic";
}

const characters = [
  { id: 1, name: "Matteo Ricci", age: 24 },
  { id: 2, name: "Vittorio Moretti", age: 72 },
  { id: 3, name: "Rosa Greco", age: 68 },
  { id: 4, name: "Marco Conti", age: 39 },
  { id: 5, name: "Luca Romano", age: 56 },
  { id: 6, name: "Isabella Bellini", age: 32 },
  { id: 7, name: "Elena Rossi", age: 29 },
].map((character) => ({
  ...character,
  image: `/ui/Images/Character_${character.id}.jpeg`,
  profileImage: `/ui/Images/Profile_Character_${character.id}.jpg`,
}));

const copy = {
  fa: {
    homeKicker: "یک شهر · هفت چهره · دو دروغ‌گو",
    homeTitle: "شب‌های<br>پالرمو",
    homeLead: "حقیقت با سپیده‌دم نمی‌آید. باید آن را از میان نگاه‌ها، ادعاها و سکوت‌ها پیدا کنی.",
    newGame: "شروع بازی جدید",
    characterKicker: "اسلاید اول",
    characterTitle: "چهره‌ات را انتخاب کن",
    characterLead: "تو تنها بازیکن انسانی هستی. شش شخصیت دیگر هر کدام یک Agent مستقل‌اند.",
    age: "سال",
    loading: "شهر در حال بیدار شدن است…",
    yourRole: "نقش واقعی تو",
    roleReveal: "هویت محرمانه",
    continue: "ادامه",
    claimTitle: "شهر باید تو را با چه نقشی بشناسد؟",
    claimText: "یکی از سه نقش زیر را ادعا کن. ادعای تو عمومی است و لازم نیست حقیقت را بگویی.",
    claimsTitle: "همه ادعاها روی میز است",
    claimsText: "این‌ها فقط ادعا هستند؛ هیچ‌کدام را حقیقت قطعی فرض نکن.",
    discussion: "بحث شهر",
    yourTurn: "نوبت توست",
    answerTurn: "یک سؤال در انتظار پاسخ توست",
    statementPlaceholder: "تحلیل، دفاع یا اتهام خود را بنویس…",
    answerPlaceholder: "پاسخ خود را بنویس…",
    mentionHint: "برای انتخاب بازیکن @ بزن",
    speak: "ثبت صحبت",
    answer: "ثبت پاسخ",
    pass: "سکوت می‌کنم",
    voteTitle: "رأی خود را ثبت کن",
    voteText: "روی تصویر شخصی که بیش از همه به او مظنون هستی کلیک کن.",
    voteResult: "نتیجه رأی شهر",
    tied: "آرا مساوی شد؛ هیچ‌کس مجازات نمی‌شود.",
    shunned: "امشب از توانایی شبانه محروم شد.",
    eliminated: "با رأی شهر از بازی حذف شد.",
    mafiaNight: "شب، شهر را بی‌دفاع کرده است",
    mafiaText: "هدف عملیات شبانه را انتخاب کن. تصمیم تو از دید شهر پنهان می‌ماند.",
    mafiaPartner: "اطلاعات محرمانه مافیا",
    yourBoss: "رئیس تو",
    yourDeputy: "معاون تو",
    deputyWaitingNight: "امشب فرمان با رئیس است",
    deputyWaitingText: "{name} رئیس مافیاست و هدف عملیات را انتخاب می‌کند. تو به‌عنوان معاون امشب اقدام مستقلی نداری.",
    deputyCommandNight: "فرمان مافیا اکنون با توست",
    deputyCommandText: "رئیس حذف شده است. به‌عنوان جانشین، هدف عملیات شبانه را انتخاب کن.",
    mafiaDisabledNight: "عملیات امشب از دسترس تو خارج است",
    mafiaDisabledText: "امشب از اقدام شبانه محروم شده‌ای و نمی‌توانی هدفی انتخاب کنی.",
    waitForMorning: "منتظر نتیجه شب بمان",
    privateFacts: "اطلاعات محرمانه تو",
    doctorNight: "یک نفر به محافظت تو نیاز دارد",
    doctorText: "بیمار امشب را انتخاب کن. نمی‌توانی هدف شب قبل را دوباره محافظت کنی.",
    detectiveNight: "ردی را در تاریکی دنبال کن",
    detectiveText: "یک نفر را برای تحقیق انتخاب کن. نتیجه فقط برای تو آشکار می‌شود.",
    citizenNight: "شهروندان فقط می‌توانند صبر کنند",
    citizenText: "درها را قفل کن و تا صبح منتظر بمان. امشب توانایی ویژه‌ای نداری.",
    nightContinue: "عبور از شب",
    selectTarget: "انتخاب هدف",
    morning: "صبح در پالرمو",
    nextDay: "شروع روز بعد",
    nobodyDied: "شب آرام گذشت؛ هیچ‌کس کشته نشد.",
    wasKilled: "دیشب کشته شد.",
    investigation: "نتیجه تحقیق خصوصی",
    gameOver: "پرونده شهر بسته شد",
    winner: "برنده",
    newStory: "بازی جدید",
    waiting: "Agentها در حال تصمیم‌گیری‌اند…",
    offline: "حالت جایگزین آفلاین فعال شد",
    degraded: "اکشن جایگزین",
    networkError: "ارتباط با شهر قطع شد. دوباره تلاش کن.",
    claimedRole: "نقش ادعایی",
    facts: "دفتر وقایع",
    factsTitle: "دفتر وقایع بازی",
    factsIntro: "اطلاعات عمومی شهر و سرنخ‌های محرمانه‌ای که فقط تو می‌دانی.",
    factsStatus: "وضعیت شهر",
    factsClaims: "ادعاهای ثبت‌شده",
    factsEvents: "وقایع قطعی",
    factsEmpty: "هنوز واقعه‌ای ثبت نشده است.",
    factsAlive: "زنده",
    factsEliminated: "حذف‌شده",
    factsShunned: "محروم از اقدام شبانه",
    factsNoDeath: "شب بدون قربانی سپری شد.",
    factsNightKill: "در عملیات شب حذف شد.",
    factsDayElimination: "با رأی شهر حذف شد.",
    consoleOverview: "نمای کلی", consoleTimeline: "رویدادها", consolePrivate: "اطلاعات من", consoleActions: "نوبت", consoleNotes: "یادداشت‌ها",
    trueRole: "نقش واقعی", revealedRole: "نقش آشکارشده", trust: "اعتماد", investigations: "تحقیقات", previousProtection: "محافظت شب قبل",
    noInvestigation: "هنوز تحقیقی ثبت نشده است.", legalActions: "انتخاب‌های مجاز اکنون", discussionOrder: "ترتیب گفتگو", notesPlaceholder: "تحلیل‌ها و سرنخ‌های خودت را اینجا بنویس…", suspicionBoard: "درجه سوءظن شخصی",
    ask: "پرسیدن سؤال", askTarget: "سؤال از", questionFrom: "سؤال از طرف", choosePlayer: "یک نفر را انتخاب کن",
    voteTarget: "مظنون اصلی و رأی تو", trustedPlayer: "قابل‌اعتمادترین فرد", secondSuspect: "مظنون دوم", confirmVote: "ثبت تصمیم رأی", voteHelp: "رأی را انتخاب کن؛ گزینه‌های دیگر برای شهروندان اختیاری‌اند.",
    strategyTitle: "استراتژی مافیا را تعیین کن", strategyText: "این تصمیم محرمانه است و مسیر استدلال مافیا را در طول بازی هدایت می‌کند.", chooseStrategy: "ثبت استراتژی",
    strategies: { ROLE_CLAIM_ATTACK: "حمله به ادعاها", CREATE_TWO_SIDES: "ساختن دو جبهه", FOLLOW_CITIZEN_ERROR_WAVE: "دنبال‌کردن خطای شهر", USE_CONTRADICTION: "استفاده از تناقض‌ها" },
    close: "بستن",
    roles: { MAFIA_BOSS: "رئیس مافیا", MAFIA_DEPUTY: "معاون مافیا", DOCTOR: "پزشک", DETECTIVE: "کارآگاه", CITIZEN: "شهروند" },
    roleNotes: {
      MAFIA_BOSS: "معاونت را می‌شناسی. شب‌ها هدف حذف را تعیین می‌کنی و باید هویتت را پنهان نگه داری.",
      MAFIA_DEPUTY: "رئیس را می‌شناسی و اگر حذف شود، مسئول عملیات شبانه خواهی شد.",
      DOCTOR: "هر شب می‌توانی از یک نفر محافظت کنی؛ حتی از خودت.",
      DETECTIVE: "هر شب می‌توانی نقش واقعی یک نفر را در سکوت کشف کنی.",
      CITIZEN: "توانایی شبانه نداری؛ قدرت تو در مشاهده، بحث و رأی است.",
    },
    claims: { CITIZEN: "شهروند ساده", DOCTOR: "پزشک", DETECTIVE: "کارآگاه" },
  },
  en: {
    homeKicker: "ONE CITY · SEVEN FACES · TWO LIARS",
    homeTitle: "PALERMO<br>NIGHTS",
    homeLead: "Truth does not arrive with dawn. Find it in the glances, claims, and silences of the city.",
    newGame: "START A NEW GAME",
    characterKicker: "SLIDE ONE",
    characterTitle: "Choose your face",
    characterLead: "You are the only human player. Each of the other six characters is an independent AI agent.",
    age: "years old",
    loading: "The city is waking up…",
    yourRole: "YOUR TRUE ROLE",
    roleReveal: "CONFIDENTIAL IDENTITY",
    continue: "CONTINUE",
    claimTitle: "Which role should the city believe?",
    claimText: "Claim one of these three roles. Your claim is public, and it does not have to be true.",
    claimsTitle: "Every claim is on the table",
    claimsText: "These are claims, not verified truths. Trust carefully.",
    discussion: "CITY DISCUSSION",
    yourTurn: "It is your turn",
    answerTurn: "A question is waiting for your answer",
    statementPlaceholder: "Write your analysis, defense, or accusation…",
    answerPlaceholder: "Write your answer…",
    mentionHint: "Type @ to choose a player",
    speak: "SPEAK",
    answer: "ANSWER",
    pass: "REMAIN SILENT",
    voteTitle: "Cast your vote",
    voteText: "Click the portrait of the person you suspect most.",
    voteResult: "THE CITY HAS DECIDED",
    tied: "The vote is tied. Nobody is punished.",
    shunned: "loses their night ability until dawn.",
    eliminated: "has been eliminated by the city.",
    mafiaNight: "Night leaves the city defenseless",
    mafiaText: "Choose the target of tonight's operation. Your decision remains hidden from the city.",
    mafiaPartner: "Confidential Mafia intelligence",
    yourBoss: "Your Boss",
    yourDeputy: "Your Deputy",
    deputyWaitingNight: "The Boss commands tonight",
    deputyWaitingText: "{name} is the Mafia Boss and chooses the target. As Deputy, you have no independent action tonight.",
    deputyCommandNight: "The Mafia command is now yours",
    deputyCommandText: "The Boss has been eliminated. As successor, choose tonight's target.",
    mafiaDisabledNight: "Tonight's operation is unavailable",
    mafiaDisabledText: "You are barred from night action and cannot select a target tonight.",
    waitForMorning: "Wait for the night's result",
    privateFacts: "Your confidential intelligence",
    doctorNight: "Someone needs your protection",
    doctorText: "Choose tonight's patient. You cannot protect the same target twice in a row.",
    detectiveNight: "Follow a trail through the dark",
    detectiveText: "Choose one person to investigate. Only you will see the result.",
    citizenNight: "Citizens can only wait",
    citizenText: "Lock the doors and wait for morning. You have no special night ability.",
    nightContinue: "ENTER THE NIGHT",
    selectTarget: "SELECT TARGET",
    morning: "MORNING IN PALERMO",
    nextDay: "START THE NEXT DAY",
    nobodyDied: "The night passed quietly. Nobody died.",
    wasKilled: "was killed last night.",
    investigation: "PRIVATE INVESTIGATION RESULT",
    gameOver: "THE CITY'S CASE IS CLOSED",
    winner: "WINNER",
    newStory: "NEW GAME",
    waiting: "The agents are deciding…",
    offline: "Offline fallback agents are active",
    degraded: "fallback actions",
    networkError: "The connection to the city was lost. Try again.",
    claimedRole: "Claimed role",
    facts: "Case file",
    factsTitle: "Game case file",
    factsIntro: "Public city facts and confidential intelligence known only to you.",
    factsStatus: "City status",
    factsClaims: "Registered claims",
    factsEvents: "Confirmed events",
    factsEmpty: "No confirmed event yet.",
    factsAlive: "alive",
    factsEliminated: "eliminated",
    factsShunned: "barred from night action",
    factsNoDeath: "The night passed without a victim.",
    factsNightKill: "was eliminated during the night.",
    factsDayElimination: "was eliminated by the city vote.",
    consoleOverview: "Overview", consoleTimeline: "Timeline", consolePrivate: "My intel", consoleActions: "Turn", consoleNotes: "Notes",
    trueRole: "True role", revealedRole: "Revealed role", trust: "Trust", investigations: "Investigations", previousProtection: "Previous protection",
    noInvestigation: "No investigation has been recorded yet.", legalActions: "Available actions now", discussionOrder: "Discussion order", notesPlaceholder: "Write your own analysis and clues here…", suspicionBoard: "Personal suspicion board",
    ask: "ASK A QUESTION", askTarget: "Ask", questionFrom: "Question from", choosePlayer: "Choose a player",
    voteTarget: "Primary suspect and vote", trustedPlayer: "Most trusted player", secondSuspect: "Second suspect", confirmVote: "SUBMIT VOTE DECISION", voteHelp: "Choose your vote; additional citizen selections are optional.",
    strategyTitle: "Choose the Mafia strategy", strategyText: "This choice is confidential and guides the Mafia's reasoning throughout the game.", chooseStrategy: "CONFIRM STRATEGY",
    strategies: { ROLE_CLAIM_ATTACK: "Attack role claims", CREATE_TWO_SIDES: "Create two sides", FOLLOW_CITIZEN_ERROR_WAVE: "Follow the town's error wave", USE_CONTRADICTION: "Exploit contradictions" },
    close: "Close",
    roles: { MAFIA_BOSS: "Mafia Boss", MAFIA_DEPUTY: "Mafia Deputy", DOCTOR: "Doctor", DETECTIVE: "Detective", CITIZEN: "Citizen" },
    roleNotes: {
      MAFIA_BOSS: "You know your deputy. Choose the night target and keep your identity hidden.",
      MAFIA_DEPUTY: "You know the Boss and inherit the night operation if the Boss is eliminated.",
      DOCTOR: "Protect one person every night, including yourself.",
      DETECTIVE: "Quietly discover one player's true role every night.",
      CITIZEN: "You have no night ability. Observation, discussion, and voting are your power.",
    },
    claims: { CITIZEN: "Citizen", DOCTOR: "Doctor", DETECTIVE: "Detective" },
  },
  de: {
    homeKicker: "EINE STADT · SIEBEN GESICHTER · ZWEI LÜGNER",
    homeTitle: "PALERMO<br>BEI NACHT",
    homeLead: "Die Wahrheit kommt nicht mit dem Morgen. Finde sie in Blicken, Behauptungen und im Schweigen der Stadt.",
    newGame: "NEUES SPIEL STARTEN",
    characterKicker: "FOLIE EINS",
    characterTitle: "Wähle dein Gesicht",
    characterLead: "Du bist der einzige menschliche Spieler. Die sechs anderen Figuren sind unabhängige KI-Agenten.",
    age: "Jahre",
    loading: "Die Stadt erwacht…",
    yourRole: "DEINE WAHRE ROLLE",
    roleReveal: "VERTRAULICHE IDENTITÄT",
    continue: "WEITER",
    claimTitle: "Welche Rolle soll die Stadt dir glauben?",
    claimText: "Behaupte eine dieser drei Rollen. Die Behauptung ist öffentlich und muss nicht wahr sein.",
    claimsTitle: "Alle Behauptungen liegen auf dem Tisch",
    claimsText: "Das sind Behauptungen, keine bestätigten Wahrheiten. Vertraue vorsichtig.",
    discussion: "STADTDISKUSSION",
    yourTurn: "Du bist an der Reihe",
    answerTurn: "Eine Frage wartet auf deine Antwort",
    statementPlaceholder: "Schreibe deine Analyse, Verteidigung oder Anschuldigung…",
    answerPlaceholder: "Schreibe deine Antwort…",
    mentionHint: "@ eingeben, um einen Spieler auszuwählen",
    speak: "SPRECHEN",
    answer: "ANTWORTEN",
    pass: "SCHWEIGEN",
    voteTitle: "Gib deine Stimme ab",
    voteText: "Klicke auf das Porträt der Person, die du am meisten verdächtigst.",
    voteResult: "DIE STADT HAT ENTSCHIEDEN",
    tied: "Die Abstimmung endet unentschieden. Niemand wird bestraft.",
    shunned: "verliert bis zum Morgen die Nachtfähigkeit.",
    eliminated: "wurde von der Stadt eliminiert.",
    mafiaNight: "Die Nacht lässt die Stadt schutzlos",
    mafiaText: "Wähle das Ziel der nächtlichen Operation. Deine Entscheidung bleibt verborgen.",
    mafiaPartner: "Vertrauliche Mafia-Information",
    yourBoss: "Dein Boss",
    yourDeputy: "Dein Stellvertreter",
    deputyWaitingNight: "Heute Nacht führt der Boss",
    deputyWaitingText: "{name} ist der Mafia-Boss und wählt das Ziel. Als Stellvertreter hast du heute keine eigene Aktion.",
    deputyCommandNight: "Das Kommando gehört jetzt dir",
    deputyCommandText: "Der Boss wurde eliminiert. Wähle als Nachfolger das Ziel der Nacht.",
    mafiaDisabledNight: "Die Nachtaktion ist nicht verfügbar",
    mafiaDisabledText: "Du bist von der Nachtaktion ausgeschlossen und kannst heute kein Ziel wählen.",
    waitForMorning: "Auf das Ergebnis der Nacht warten",
    privateFacts: "Deine vertraulichen Informationen",
    doctorNight: "Jemand braucht deinen Schutz",
    doctorText: "Wähle den Patienten dieser Nacht. Dasselbe Ziel darf nicht zweimal folgen.",
    detectiveNight: "Folge einer Spur durch die Dunkelheit",
    detectiveText: "Wähle eine Person für die Untersuchung. Nur du siehst das Ergebnis.",
    citizenNight: "Bürger können nur warten",
    citizenText: "Verriegle die Türen und warte auf den Morgen. Du hast keine Nachtfähigkeit.",
    nightContinue: "IN DIE NACHT",
    selectTarget: "ZIEL WÄHLEN",
    morning: "MORGEN IN PALERMO",
    nextDay: "NÄCHSTEN TAG STARTEN",
    nobodyDied: "Die Nacht blieb ruhig. Niemand ist gestorben.",
    wasKilled: "wurde letzte Nacht getötet.",
    investigation: "PRIVATES ERMITTLUNGSERGEBNIS",
    gameOver: "DER FALL DER STADT IST GESCHLOSSEN",
    winner: "SIEGER",
    newStory: "NEUES SPIEL",
    waiting: "Die Agenten entscheiden…",
    offline: "Offline-Ersatzagenten sind aktiv",
    degraded: "Ersatzaktionen",
    networkError: "Die Verbindung zur Stadt wurde unterbrochen. Versuche es erneut.",
    claimedRole: "Behauptete Rolle",
    facts: "Fallakte",
    factsTitle: "Spielakte",
    factsIntro: "Öffentliche Stadtfakten und vertrauliche Hinweise, die nur du kennst.",
    factsStatus: "Stadtstatus",
    factsClaims: "Registrierte Behauptungen",
    factsEvents: "Bestätigte Ereignisse",
    factsEmpty: "Noch kein bestätigtes Ereignis.",
    factsAlive: "lebend",
    factsEliminated: "eliminiert",
    factsShunned: "von der Nachtaktion ausgeschlossen",
    factsNoDeath: "Die Nacht endete ohne Opfer.",
    factsNightKill: "wurde in der Nacht eliminiert.",
    factsDayElimination: "wurde durch die Stadtwahl eliminiert.",
    consoleOverview: "Übersicht", consoleTimeline: "Chronik", consolePrivate: "Meine Infos", consoleActions: "Zug", consoleNotes: "Notizen",
    trueRole: "Wahre Rolle", revealedRole: "Enthüllte Rolle", trust: "Vertrauen", investigations: "Ermittlungen", previousProtection: "Letzter Schutz",
    noInvestigation: "Noch keine Ermittlung vorhanden.", legalActions: "Jetzt verfügbare Aktionen", discussionOrder: "Gesprächsreihenfolge", notesPlaceholder: "Schreibe hier deine Analyse und Hinweise…", suspicionBoard: "Persönliche Verdachtsliste",
    ask: "FRAGE STELLEN", askTarget: "Frage an", questionFrom: "Frage von", choosePlayer: "Person wählen",
    voteTarget: "Hauptverdacht und Stimme", trustedPlayer: "Vertrauenswürdigste Person", secondSuspect: "Zweiter Verdacht", confirmVote: "WAHLENTSCHEIDUNG SENDEN", voteHelp: "Wähle deine Stimme; weitere Angaben sind freiwillig.",
    strategyTitle: "Mafia-Strategie wählen", strategyText: "Diese Wahl ist vertraulich und lenkt die Überlegungen der Mafia im Spiel.", chooseStrategy: "STRATEGIE BESTÄTIGEN",
    strategies: { ROLE_CLAIM_ATTACK: "Rollenbehauptungen angreifen", CREATE_TWO_SIDES: "Zwei Lager bilden", FOLLOW_CITIZEN_ERROR_WAVE: "Fehlerwelle der Stadt nutzen", USE_CONTRADICTION: "Widersprüche ausnutzen" },
    close: "Schließen",
    roles: { MAFIA_BOSS: "Mafia-Boss", MAFIA_DEPUTY: "Mafia-Stellvertreter", DOCTOR: "Arzt", DETECTIVE: "Detektiv", CITIZEN: "Bürger" },
    roleNotes: {
      MAFIA_BOSS: "Du kennst deinen Stellvertreter. Wähle nachts das Ziel und verbirg deine Identität.",
      MAFIA_DEPUTY: "Du kennst den Boss und übernimmst die Nachtoperation, wenn er eliminiert wird.",
      DOCTOR: "Schütze jede Nacht eine Person, auch dich selbst.",
      DETECTIVE: "Entdecke jede Nacht heimlich die wahre Rolle einer Person.",
      CITIZEN: "Du hast keine Nachtfähigkeit. Beobachtung, Diskussion und Abstimmung sind deine Stärke.",
    },
    claims: { CITIZEN: "Bürger", DOCTOR: "Arzt", DETECTIVE: "Detektiv" },
  },
};

Object.assign(copy.fa, { tutorial: "آموزش و قوانین بازی", stopped: "اجرای بازی متوقف شد", failedText: "بازی به دلیل خطای اجرا ادامه پیدا نکرد. می‌توانی بازی جدیدی شروع کنی.", cancelledText: "این مسابقه لغو شده است.", reconnect: "تلاش دوباره برای اتصال", sessionExpired: "این مسابقه دیگر در سرور موجود نیست. بازی جدیدی شروع کن." });
Object.assign(copy.en, { tutorial: "HOW TO PLAY & RULES", stopped: "The game has stopped", failedText: "The game could not continue because of an error. You can start a new game.", cancelledText: "This match was cancelled.", reconnect: "RETRY CONNECTION", sessionExpired: "This match is no longer available on the server. Start a new game." });
Object.assign(copy.de, { tutorial: "ANLEITUNG & REGELN", stopped: "Das Spiel wurde angehalten", failedText: "Das Spiel konnte wegen eines Fehlers nicht fortgesetzt werden. Du kannst ein neues Spiel starten.", cancelledText: "Diese Partie wurde abgebrochen.", reconnect: "VERBINDUNG ERNEUT VERSUCHEN", sessionExpired: "Diese Partie ist auf dem Server nicht mehr verfügbar. Starte ein neues Spiel." });

const tutorialGuide = {
  en: {
    kicker: "COMPLETE BEGINNER'S GUIDE",
    title: "How to play Palermo Nights",
    intro: "A social-deduction game for seven characters: you are the only human, while six independent AI agents speak, question, vote, deceive, and use their roles. Your true role is secret. Read the city, protect your faction, and survive until its victory condition is met.",
    summary: [["7", "players"], ["2", "hidden factions"], ["1", "human player"]],
    sections: [
      ["1. Objective", `<p>Every player belongs to either the <strong>Citizen faction</strong> or the <strong>Mafia faction</strong>. Citizens win by eliminating both Mafia members. Mafia wins as soon as the number of living Mafia members equals the number of living Citizens.</p><p>Your personal role may give you private information or a night ability, but victory belongs to your whole faction.</p>`],
      ["2. Roles in the city", `<p>Roles are assigned randomly and remain secret until a player is eliminated.</p><div class="tutorial-role-grid"><div class="tutorial-role"><b>Mafia Boss × 1</b><p>Knows the Deputy, chooses the Mafia's night target, and must hide among the city.</p></div><div class="tutorial-role"><b>Mafia Deputy × 1</b><p>Knows the Boss. If the Boss is eliminated, the Deputy takes command of future night attacks.</p></div><div class="tutorial-role"><b>Doctor × 1</b><p>Protects one living player each night, including themself. The same target cannot be protected on two consecutive nights.</p></div><div class="tutorial-role"><b>Detective × 1</b><p>Investigates one living player each night and privately learns that player's exact role.</p></div><div class="tutorial-role"><b>Citizens × 3</b><p>Have no night ability. Their power is observation, discussion, questioning, and voting.</p></div></div>`],
      ["3. Hidden identity and public claims", `<p>After seeing your true role, you publicly claim to be a <strong>Citizen, Doctor, or Detective</strong>. Anyone—including Mafia—may lie. Mafia roles can never be claimed directly.</p><p>A claim is not proof. Compare it with later statements, votes, night results, and contradictions.</p>`],
      ["4. Day discussion", `<ol><li>Living players speak in a random order.</li><li>On your turn you may make a statement, ask another living player a question, or remain silent.</li><li>Questions must be answered before voting begins.</li><li>Use <strong>@</strong> while writing to select a character accurately.</li></ol><p>The event journal records public facts and your own private information. Other players' hidden roles and private clues are never shown to you.</p>`],
      ["5. Voting and the special first day", `<p>Each living player submits a vote. Citizens may optionally choose a second suspect and a trusted player after selecting their vote. Mafia has no optional trust selections. All selected players must be distinct and cannot be yourself.</p><ul><li><strong>Day 1:</strong> the top-voted player is shunned, not eliminated. That player cannot use a night ability; the Doctor and Detective also cannot target them that night. The shun ends in the morning.</li><li><strong>Day 2 and later:</strong> the top-voted player is eliminated. Their true role—and any recorded last will—is revealed.</li><li><strong>Tie:</strong> nobody is punished or eliminated.</li></ul>`],
      ["6. Night", `<p>Night abilities resolve together:</p><ul><li>The active Mafia leader attacks one Citizen.</li><li>The Doctor protects one eligible player. If that person is attacked, nobody dies.</li><li>The Detective investigates one eligible player and receives a private result.</li><li>Citizens wait for morning.</li></ul><p>If the Boss is dead, the Deputy becomes the active attacker. In the morning, the city learns whether someone died and sees the victim's true role.</p>`],
      ["7. Elimination and the end of the game", `<p>Eliminated players no longer speak, vote, or act at night. The game checks victory immediately after every elimination and night resolution.</p><div class="tutorial-note"><strong>Citizens win:</strong> both Mafia members are eliminated.<br><strong>Mafia wins:</strong> living Mafia reaches parity with living Citizens—for example, two Mafia against two Citizens.</div>`],
      ["8. Beginner strategy", `<ul><li>Do not trust a role claim by itself; track whether actions and explanations remain consistent.</li><li>Ask direct questions and remember who avoids answering.</li><li>Use the trusted-player and second-suspect choices as real information about alliances.</li><li>If you have a special role, revealing it too early may make you a Mafia target; waiting too long may waste your information.</li><li>Review previous conversations and votes in the journal.</li></ul>`],
    ],
    back: "BACK TO HOME",
    start: "START A NEW GAME",
  },
  de: {
    kicker: "VOLLSTÄNDIGE ANLEITUNG FÜR EINSTEIGER",
    title: "So spielt man Palermo bei Nacht",
    intro: "Ein Social-Deduction-Spiel mit sieben Figuren: Du bist der einzige Mensch, während sechs unabhängige KI-Agenten reden, fragen, abstimmen, täuschen und ihre Rollen einsetzen. Deine wahre Rolle ist geheim. Beobachte die Stadt, schütze deine Fraktion und überlebe bis zu ihrem Sieg.",
    summary: [["7", "Spieler"], ["2", "geheime Fraktionen"], ["1", "menschlicher Spieler"]],
    sections: [
      ["1. Ziel des Spiels", `<p>Jeder gehört entweder zur <strong>Bürgerfraktion</strong> oder zur <strong>Mafiafraktion</strong>. Die Bürger gewinnen, wenn beide Mafiosi eliminiert sind. Die Mafia gewinnt, sobald gleich viele Mafiosi wie Bürger leben.</p><p>Deine Rolle kann dir geheime Informationen oder eine Nachtfähigkeit geben, aber der Sieg gilt für deine gesamte Fraktion.</p>`],
      ["2. Rollen in der Stadt", `<p>Die Rollen werden zufällig verteilt und bleiben bis zur Eliminierung geheim.</p><div class="tutorial-role-grid"><div class="tutorial-role"><b>Mafia-Boss × 1</b><p>Kennt den Stellvertreter, wählt nachts das Angriffsziel und muss seine Identität verbergen.</p></div><div class="tutorial-role"><b>Mafia-Stellvertreter × 1</b><p>Kennt den Boss und übernimmt nach dessen Eliminierung die Nachtangriffe.</p></div><div class="tutorial-role"><b>Arzt × 1</b><p>Schützt jede Nacht eine lebende Person, auch sich selbst. Dieselbe Person darf nicht in zwei aufeinanderfolgenden Nächten geschützt werden.</p></div><div class="tutorial-role"><b>Detektiv × 1</b><p>Untersucht jede Nacht eine lebende Person und erfährt heimlich deren genaue Rolle.</p></div><div class="tutorial-role"><b>Bürger × 3</b><p>Haben keine Nachtfähigkeit. Ihre Stärke sind Beobachtung, Diskussion, Fragen und Abstimmung.</p></div></div>`],
      ["3. Geheime Identität und öffentliche Behauptung", `<p>Nachdem du deine echte Rolle gesehen hast, behauptest du öffentlich, <strong>Bürger, Arzt oder Detektiv</strong> zu sein. Jeder darf lügen—auch die Mafia. Mafia-Rollen können nie direkt behauptet werden.</p><p>Eine Behauptung ist kein Beweis. Vergleiche sie mit späteren Aussagen, Stimmen, Nachtresultaten und Widersprüchen.</p>`],
      ["4. Diskussion am Tag", `<ol><li>Die lebenden Spieler sprechen in zufälliger Reihenfolge.</li><li>Du kannst in deinem Zug etwas sagen, einer lebenden Person eine Frage stellen oder schweigen.</li><li>Alle Fragen müssen vor der Abstimmung beantwortet werden.</li><li>Tippe beim Schreiben <strong>@</strong>, um eine Figur eindeutig auszuwählen.</li></ol><p>Das Ereignisprotokoll enthält öffentliche Fakten und deine eigenen geheimen Informationen. Verborgene Rollen und private Hinweise anderer Spieler bleiben unsichtbar.</p>`],
      ["5. Abstimmung und der besondere erste Tag", `<p>Jeder lebende Spieler stimmt ab. Bürger können danach freiwillig einen zweiten Verdacht und eine Vertrauensperson wählen. Für die Mafia entfallen diese Angaben. Alle gewählten Personen müssen verschieden sein; Selbstwahl ist ausgeschlossen.</p><ul><li><strong>Tag 1:</strong> Die Person mit den meisten Stimmen wird geächtet, nicht eliminiert. Sie kann nachts keine Fähigkeit einsetzen; Arzt und Detektiv können sie in dieser Nacht ebenfalls nicht als Ziel wählen. Am Morgen endet die Ächtung.</li><li><strong>Ab Tag 2:</strong> Die Person mit den meisten Stimmen wird eliminiert. Ihre echte Rolle und ein vorhandenes Testament werden enthüllt.</li><li><strong>Gleichstand:</strong> Niemand wird bestraft oder eliminiert.</li></ul>`],
      ["6. Nacht", `<p>Alle Nachtfähigkeiten werden gemeinsam ausgewertet:</p><ul><li>Der aktive Mafia-Anführer greift einen Bürger an.</li><li>Der Arzt schützt eine erlaubte Person. Wird sie angegriffen, stirbt niemand.</li><li>Der Detektiv untersucht eine erlaubte Person und erhält das Ergebnis privat.</li><li>Die Bürger warten auf den Morgen.</li></ul><p>Ist der Boss tot, übernimmt der Stellvertreter den Angriff. Am Morgen erfährt die Stadt, ob jemand gestorben ist, und sieht die wahre Rolle des Opfers.</p>`],
      ["7. Eliminierung und Spielende", `<p>Eliminierte Spieler dürfen nicht mehr reden, abstimmen oder nachts handeln. Nach jeder Eliminierung und jeder Nacht wird sofort geprüft, ob eine Fraktion gewonnen hat.</p><div class="tutorial-note"><strong>Die Bürger gewinnen:</strong> Beide Mafiosi sind eliminiert.<br><strong>Die Mafia gewinnt:</strong> Es leben gleich viele Mafiosi wie Bürger—zum Beispiel zwei Mafiosi gegen zwei Bürger.</div>`],
      ["8. Tipps für Einsteiger", `<ul><li>Vertraue keiner Rollenbehauptung allein; prüfe, ob Aussagen und Handlungen zusammenpassen.</li><li>Stelle direkte Fragen und merke dir, wer Antworten vermeidet.</li><li>Behandle Vertrauensperson und zweiten Verdacht als echte Hinweise auf Bündnisse.</li><li>Mit einer Spezialrolle macht dich ein zu frühes Geständnis zum Ziel; zu langes Schweigen kann deine Informationen wertlos machen.</li><li>Lies frühere Gespräche und Stimmen im Journal nach.</li></ul>`],
    ],
    back: "ZURÜCK ZUM START",
    start: "NEUES SPIEL STARTEN",
  },
  fa: {
    kicker: "راهنمای کامل برای بازیکن تازه‌کار",
    title: "چگونه شب‌های پالرمو را بازی کنیم؟",
    intro: "یک بازی استنتاج اجتماعی با هفت شخصیت: تو تنها بازیکن انسانی هستی و شش Agent مستقل هوش مصنوعی صحبت می‌کنند، سؤال می‌پرسند، رأی می‌دهند، فریب می‌دهند و از نقش‌هایشان استفاده می‌کنند. نقش واقعی تو محرمانه است؛ شهر را بخوان، از جناحت محافظت کن و تا پیروزی آن زنده بمان.",
    summary: [["۷", "بازیکن"], ["۲", "جناح مخفی"], ["۱", "بازیکن انسانی"]],
    sections: [
      ["۱. هدف بازی", `<p>هر بازیکن عضو یکی از دو جناح <strong>شهروندان</strong> یا <strong>مافیا</strong> است. شهروندان با حذف هر دو عضو مافیا برنده می‌شوند. مافیا زمانی برنده است که تعداد مافیای زنده با تعداد شهروندان زنده برابر شود.</p><p>نقش شخصی تو ممکن است اطلاعات محرمانه یا توانایی شبانه بدهد، اما پیروزی متعلق به کل جناح توست.</p>`],
      ["۲. نقش‌های شهر", `<p>نقش‌ها به‌صورت تصادفی تقسیم می‌شوند و تا زمان حذف بازیکن مخفی می‌مانند.</p><div class="tutorial-role-grid"><div class="tutorial-role"><b>رئیس مافیا × ۱</b><p>معاون را می‌شناسد، هدف حمله شبانه را انتخاب می‌کند و باید هویتش را از شهر پنهان کند.</p></div><div class="tutorial-role"><b>معاون مافیا × ۱</b><p>رئیس را می‌شناسد و اگر رئیس حذف شود، فرمان حمله‌های شبانه را در دست می‌گیرد.</p></div><div class="tutorial-role"><b>پزشک × ۱</b><p>هر شب از یک بازیکن زنده، حتی خودش، محافظت می‌کند. نمی‌تواند دو شب پیاپی از یک نفر محافظت کند.</p></div><div class="tutorial-role"><b>کارآگاه × ۱</b><p>هر شب یک بازیکن زنده را بررسی می‌کند و نقش دقیق او را به‌صورت محرمانه می‌فهمد.</p></div><div class="tutorial-role"><b>شهروند × ۳</b><p>توانایی شبانه ندارند؛ قدرتشان در مشاهده، بحث، سؤال و رأی‌دادن است.</p></div></div>`],
      ["۳. هویت مخفی و ادعای عمومی", `<p>پس از دیدن نقش واقعی، باید در برابر شهر ادعا کنی که <strong>شهروند، پزشک یا کارآگاه</strong> هستی. همه—از جمله مافیا—اجازه دارند دروغ بگویند. نمی‌توان مستقیماً ادعای نقش مافیا کرد.</p><p>ادعا مدرک نیست. آن را با گفته‌های بعدی، رأی‌ها، نتیجه شب و تناقض‌های رفتاری مقایسه کن.</p>`],
      ["۴. گفت‌وگوی روز", `<ol><li>بازیکنان زنده با ترتیبی تصادفی صحبت می‌کنند.</li><li>در نوبت خود می‌توانی تحلیل یا اتهام بنویسی، از یک بازیکن زنده سؤال بپرسی یا سکوت کنی.</li><li>پیش از رأی‌گیری، تمام سؤال‌ها باید پاسخ داده شوند.</li><li>هنگام نوشتن از علامت <strong>@</strong> برای انتخاب دقیق شخصیت استفاده کن.</li></ol><p>دفتر وقایع، واقعیت‌های عمومی و اطلاعات محرمانه خودت را ثبت می‌کند. نقش‌ها و سرنخ‌های خصوصی دیگران هرگز به تو نمایش داده نمی‌شوند.</p>`],
      ["۵. رأی‌گیری و قانون ویژه روز اول", `<p>هر بازیکن زنده یک رأی اصلی ثبت می‌کند. شهروندان می‌توانند پس از انتخاب هدف رأی، مظنون دوم و فرد قابل‌اعتماد را به‌صورت اختیاری مشخص کنند. این دو گزینه برای مافیا وجود ندارند. نمی‌توانی خودت را انتخاب کنی و گزینه‌ها باید افراد متفاوتی باشند.</p><ul><li><strong>روز اول:</strong> فرد دارای بیشترین رأی حذف نمی‌شود، بلکه برای یک شب محروم می‌شود. او نمی‌تواند از توانایی شبانه استفاده کند و پزشک و کارآگاه هم نمی‌توانند آن شب او را هدف بگیرند. محرومیت صبح پایان می‌یابد.</li><li><strong>از روز دوم:</strong> فرد دارای بیشترین رأی حذف می‌شود و نقش واقعی و وصیت ثبت‌شده‌اش آشکار می‌شود.</li><li><strong>تساوی آرا:</strong> هیچ‌کس مجازات یا حذف نمی‌شود.</li></ul>`],
      ["۶. شب", `<p>توانایی‌های شبانه با هم محاسبه می‌شوند:</p><ul><li>فرمانده فعال مافیا به یک شهروند حمله می‌کند.</li><li>پزشک از یک هدف مجاز محافظت می‌کند؛ اگر همان فرد هدف حمله باشد، کسی کشته نمی‌شود.</li><li>کارآگاه یک هدف مجاز را بررسی می‌کند و نتیجه را فقط خودش می‌بیند.</li><li>شهروندان تا صبح منتظر می‌مانند.</li></ul><p>اگر رئیس مافیا مرده باشد، معاون حمله را انجام می‌دهد. صبح، شهر می‌فهمد آیا کسی کشته شده و نقش واقعی قربانی را می‌بیند.</p>`],
      ["۷. حذف و پایان بازی", `<p>بازیکن حذف‌شده دیگر حق صحبت، رأی یا اقدام شبانه ندارد. پس از هر حذف و پایان هر شب، شرط پیروزی فوراً بررسی می‌شود.</p><div class="tutorial-note"><strong>پیروزی شهروندان:</strong> هر دو عضو مافیا حذف شوند.<br><strong>پیروزی مافیا:</strong> تعداد مافیای زنده با شهروندان زنده برابر شود؛ مثلاً دو مافیا در برابر دو شهروند.</div>`],
      ["۸. راهبردهای ساده برای شروع", `<ul><li>فقط به ادعای نقش اعتماد نکن؛ هماهنگی حرف‌ها و رفتارها را دنبال کن.</li><li>سؤال مستقیم بپرس و به کسانی که از پاسخ فرار می‌کنند توجه کن.</li><li>انتخاب فرد قابل‌اعتماد و مظنون دوم را سرنخی درباره اتحادها بدان.</li><li>اگر نقش ویژه داری، افشای خیلی زود تو را هدف مافیا می‌کند؛ سکوت طولانی هم ممکن است اطلاعاتت را بی‌فایده کند.</li><li>در دفتر وقایع، گفتگوها و رأی‌های قبلی را مرور کن.</li></ul>`],
    ],
    back: "بازگشت به خانه",
    start: "شروع بازی جدید",
  },
};

const state = {
  lang: "en",
  characterId: null,
  characterMap: {},
  gameId: null,
  playerId: "P1",
  token: null,
  public: null,
  private: null,
  run: null,
  events: [],
  nightReplay: [],
  journalFilters: { player: "", round: "", kind: "" },
  archiveMode: false,
  availableActions: [],
  playerNames: {},
  observationUrl: null,
  consoleTab: "timeline",
  notes: { text: "", suspicion: {} },
  eventSource: null,
  stage: "home",
  narrativeRound: 1,
  voteRound: null,
  nightRound: null,
  shownDiscussion: new Set(),
  currentEventId: null,
  currentResultId: null,
  acknowledgedResults: new Set(),
  drafts: {},
  pendingAction: null,
};

let typingVersion = 0;
let typewriterRun = null;
let syncPromise = null;
let syncAgain = false;
let syncNeedsRoute = false;
let syncTimer = null;
let actionInFlight = false;
const SESSION_KEY = "palermo-active-session-v1";
let recoveryTimer = null;
let recoveryDelay = 1000;

async function fetchWithTimeout(url, options = {}, timeoutMs = 15000) {
  const controller = new AbortController();
  let timer;
  const deadline = new Promise((_, reject) => {
    timer = setTimeout(() => { controller.abort(); reject(new Error("request_timeout")); }, timeoutMs);
  });
  try {
    return await Promise.race([(async () => {
      const response = await fetch(url, { ...options, signal: controller.signal });
      // Read the body inside the same deadline; headers alone are not completion.
      const raw = typeof response.text === "function" ? await response.text() : JSON.stringify(await response.json?.() ?? {});
      return { ok: response.ok, status: response.status,
        json: async () => JSON.parse(raw), text: async () => raw };
    })(), deadline]);
  } finally { clearTimeout(timer); }
}

function scheduleRecovery() {
  if (!state.gameId || state.archiveMode || state.stage === "home" || recoveryTimer) return;
  $("#connection-state").classList.add("offline");
  recoveryTimer = window.setTimeout(async () => {
    recoveryTimer = null;
    try {
      await syncState(true);
      if (state.stage === "connection_error") {
        restoreStory(readStored(SESSION_KEY, {})?.stage || "play");
        connectStream(`/game/${state.gameId}/stream`);
      }
    }
    catch (error) {
      if ([401, 404].includes(error.status)) {
        clearSession(); state.eventSource?.close();
        state.gameId = null; state.token = null; state.stage = "home";
        refreshResumeControls(); showScreen("home"); toast(text("sessionExpired"));
      } else { recoveryDelay = Math.min(recoveryDelay * 2, 15000); scheduleRecovery(); }
    }
  }, recoveryDelay);
}

function draftKey(kind = state.stage) {
  const previous = kind === "human_discussion" ? state.events.filter(e =>
    e.actor === state.playerId && ["PLAYER_SPOKE", "PLAYER_ANSWERED", "PLAYER_ASKED"].includes(e.type)).at(-1)?.event_id || "start" : "";
  return `${state.public?.round || 1}:${kind}:${previous}`;
}
function saveDraft(kind, values) {
  state.drafts[draftKey(kind)] = values;
  saveSession();
}

function readStored(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; } catch { return fallback; }
}

function saveSession() {
  if (state.archiveMode) return;
  if (!state.gameId || !state.token || ["home", "restoring", "connection_error"].includes(state.stage)) return;
  const session = Object.fromEntries([
    "gameId", "playerId", "token", "characterId", "lang", "stage", "narrativeRound",
    "voteRound", "nightRound", "currentEventId", "currentResultId",
    "drafts", "pendingAction",
  ].map((key) => [key, state[key]]));
  session.shownDiscussion = [...state.shownDiscussion];
  session.acknowledgedResults = [...state.acknowledgedResults];
  try { localStorage.setItem(SESSION_KEY, JSON.stringify(session)); } catch { /* Storage may be disabled. */ }
}

function clearSession() {
  try { localStorage.removeItem(SESSION_KEY); } catch { /* Storage may be disabled. */ }
}

async function restoreSession() {
  const saved = readStored(SESSION_KEY, null);
  if (!saved || typeof saved.gameId !== "string" || typeof saved.token !== "string"
      || !characters.some((item) => item.id === saved.characterId)) return;
  showLoading(true);
  state.gameId = saved.gameId;
  state.token = saved.token;
  state.playerId = "P1";
  state.characterId = saved.characterId;
  state.characterMap = buildCharacterMap(saved.characterId);
  state.observationUrl = `/game/${state.gameId}/player/${state.playerId}/observation`;
  state.stage = "restoring";
  state.narrativeRound = Math.max(1, Number(saved.narrativeRound) || 1);
  state.voteRound = saved.voteRound;
  state.nightRound = saved.nightRound;
  state.currentEventId = saved.currentEventId;
  state.currentResultId = saved.currentResultId;
  state.drafts = saved.drafts || {};
  state.pendingAction = saved.pendingAction || null;
  state.shownDiscussion = new Set(Array.isArray(saved.shownDiscussion) ? saved.shownDiscussion : []);
  state.acknowledgedResults = new Set(Array.isArray(saved.acknowledgedResults) ? saved.acknowledgedResults : []);
  state.notes = readStored(`palermo-notes-${saved.gameId}`, { text: "", suspicion: {} });
  setLanguage(["fa", "en", "de"].includes(saved.lang) ? saved.lang : "en");
  try {
    await syncState(false);
    showScreen("story-screen");
    restoreStory(saved.stage);
    connectStream(`/game/${state.gameId}/stream`);
  } catch (error) {
    if ([401, 404].includes(error.status)) {
      clearSession();
      state.gameId = null;
      state.token = null;
      state.stage = "home";
      showScreen("home");
      toast(text("sessionExpired"));
    } else {
      showScreen("story-screen");
      showStopped(true);
      scheduleRecovery();
    }
  } finally { showLoading(false); }
}

function restoreStory(stage) {
  if (["FAILED", "CANCELLED"].includes(state.run.status)) return showStopped();
  if (stage === "role") return showRoleReveal();
  if (state.availableActions.includes("SELECT_STRATEGY")) return showStrategy();
  if (state.availableActions.includes("ROLE_CLAIM")) return showClaim();
  if (stage === "claims") return showClaims();
  const event = state.events.find((item) => item.event_id === state.currentEventId);
  if (stage === "discussion_event" && event) return showDiscussionEvent(event);
  const result = state.events.find((item) => item.event_id === state.currentResultId);
  if (stage === "vote_result" && result) return showVoteResult(result);
  if (stage === "morning" && result) return showMorning(result);
  if (["night_intro", "night_action", "night_wait"].includes(stage)) {
    if (nightResultEvent()) return showMorning(nightResultEvent());
    return showNight();
  }
  if (stage === "vote_wait" && state.availableActions.includes("SUBMIT_VOTE_DECISION")) return showVote();
  if (["wait_opening", "wait_strategy", "wait_claims", "vote_wait"].includes(stage)) {
    state.stage = stage;
    showWaiting(stage === "vote_wait" ? 6 : 3);
    return routeAfterSync();
  }
  if (stage === "game_over" && state.public.phase === "GAME_OVER") return showGameOver();
  state.stage = "play";
  routePlay();
}

function text(key) { return copy[state.lang][key]; }
function formatText(key, values = {}) {
  return Object.entries(values).reduce(
    (value, [name, replacement]) => value.replaceAll(`{${name}}`, String(replacement)),
    text(key),
  );
}
function escapeHTML(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

function characterImage(characterId) { return `/ui/Images/Character_${characterId}.jpeg`; }
function playerCharacter(playerId) { return state.characterMap[playerId] || characters[Number(playerId.slice(1)) - 1]; }
function playerName(playerId) { return state.playerNames[playerId] || playerCharacter(playerId)?.name || playerId; }
function playerNameMatches(value) {
  if (!state.public?.players) return [];
  const persianNames = { 1: "متئو", 2: "ویتوریو", 3: "روزا", 4: "مارکو", 5: "لوکا", 6: "ایزابلا", 7: "النا" };
  const names = Object.keys(state.public.players).flatMap((id) => [
    [playerName(id), id], [playerName(id).split(" ")[0], id], [persianNames[playerCharacter(id)?.id], id],
  ]).filter(([name]) => name).sort((a, b) => b[0].length - a[0].length);
  if (!names.length) return [];
  const expression = new RegExp(`(?<![\\p{L}\\p{N}_])(?:${names.map(([name]) => name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})(?![\\p{L}\\p{N}_])`, "gu");
  return [...String(value ?? "").matchAll(expression)].map((match) => ({ index: match.index, name: match[0], id: names.find(([name]) => name === match[0])[1] }));
}
function decoratePlayerNames(root) {
  if (!root || !state.public?.players || typeof document.createTreeWalker !== "function") return;
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.textContent?.trim() || node.parentElement?.closest(".player-reference, .player-picker, .character-card, .target-card, .claim-card, .mafia-partner, .facts-claims, #facts-player, .mention-menu, textarea, select, option, [data-typewriter]")) return NodeFilter.FILTER_REJECT;
      return playerNameMatches(node.textContent).length ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach((node) => {
    const fragment = document.createDocumentFragment();
    let cursor = 0;
    for (const match of playerNameMatches(node.textContent)) {
      if (match.index > cursor) fragment.append(document.createTextNode(node.textContent.slice(cursor, match.index)));
      const label = document.createElement("span");
      label.className = "player-reference";
      const photo = document.createElement("img");
      photo.src = playerCharacter(match.id).profileImage;
      photo.alt = "";
      photo.loading = "lazy";
      label.append(photo, document.createTextNode(match.name));
      fragment.append(label);
      cursor = match.index + match.name.length;
    }
    fragment.append(document.createTextNode(node.textContent.slice(cursor)));
    node.replaceWith(fragment);
  });
}

function enhancePlayerSelects(root) {
  if (!root || typeof document.createElement !== "function") return;
  $$("#ask-target, #trusted-player, #second-suspect, [data-journal-filter='player']", root).forEach((select) => {
    if (select.closest(".player-picker")) return;
    const picker = document.createElement("span");
    picker.className = "player-picker";
    select.before(picker);
    picker.append(select);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "player-picker-button";
    button.setAttribute("aria-haspopup", "listbox");
    button.setAttribute("aria-expanded", "false");
    const menu = document.createElement("span");
    menu.className = "player-picker-menu";
    menu.setAttribute("role", "listbox");
    menu.hidden = true;
    const labelFor = (option) => {
      const photo = option.value ? `<img class="picker-photo" src="${escapeHTML(playerCharacter(option.value).profileImage)}" alt="" />` : "";
      return `${photo}<span>${escapeHTML(option.textContent)}</span>`;
    };
    const close = () => { menu.hidden = true; button.setAttribute("aria-expanded", "false"); picker.closest(".dialogue-box")?.classList.remove("mention-open"); };
    const update = () => {
      button.innerHTML = labelFor(select.selectedOptions[0] || select.options[0]);
      button.disabled = select.disabled;
      if (select.disabled) close();
      $$('[data-player-value]', menu).forEach((item) => {
        const option = [...select.options].find((o) => o.value === item.dataset.playerValue);
        item.disabled = Boolean(option?.disabled);
        item.hidden = Boolean(option?.hidden);
      });
      $$('[data-player-value]', menu).forEach((item) => item.setAttribute("aria-selected", String(item.dataset.playerValue === select.value)));
    };
    menu.innerHTML = [...select.options].map((option) => `<button type="button" role="option" data-player-value="${escapeHTML(option.value)}">${labelFor(option)}</button>`).join("");
    button.addEventListener("click", () => {
      if (select.disabled) return;
      const open = menu.hidden;
      $$(".player-picker-menu", root).forEach((other) => { other.hidden = true; other.previousElementSibling?.setAttribute("aria-expanded", "false"); });
      menu.classList.toggle("open-below", button.getBoundingClientRect().top < 300 && window.innerHeight - button.getBoundingClientRect().bottom > 180);
      menu.hidden = !open;
      button.setAttribute("aria-expanded", String(open));
      picker.closest(".dialogue-box")?.classList.toggle("mention-open", open);
    });
    button.addEventListener("keydown", (event) => {
      if (event.key === "Escape") return close();
      if (!["ArrowDown", "ArrowUp"].includes(event.key)) return;
      event.preventDefault();
      if (select.disabled) return;
      const options = [...select.options].filter((o) => !o.disabled && !o.hidden);
      const next = (options.findIndex((o) => o.value === select.value) + (event.key === "ArrowDown" ? 1 : -1) + options.length) % options.length;
      select.value = options[next].value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      update();
    });
    menu.addEventListener("click", (event) => {
      const item = event.target.closest("[data-player-value]");
      if (!item || item.disabled || select.disabled) return;
      select.value = item.dataset.playerValue;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      update(); close(); button.focus();
    });
    select.addEventListener("change", update);
    select.addEventListener("picker-refresh", update);
    select.tabIndex = -1;
    select.setAttribute("aria-hidden", "true");
    picker.append(button, menu);
    update();
    picker.addEventListener("focusout", () => window.setTimeout(() => { if (!picker.contains(document.activeElement)) close(); }, 0));
  });
}
function claimedRole(playerId) {
  const role = state.public?.role_claims?.[playerId];
  return role ? (text("claims")[role] || text("roles")[role] || role) : "—";
}
function replacePlayerReferences(value) {
  const referenceLabel = { fa: "رویداد ثبت‌شده", en: "recorded event", de: "protokolliertes Ereignis" }[state.lang] || "recorded event";
  return String(value ?? "").replace(/\bP([1-7])\b/g, (playerId) => playerName(playerId))
    .replace(/\bevt_\d+\b/g, referenceLabel);
}

function mafiaPartnerMarkup(compact = false) {
  if (state.private?.faction !== "MAFIA") return "";
  const partnerId = state.private.mafia_private_information?.partner;
  const partner = partnerId ? playerCharacter(partnerId) : null;
  if (!partner) return "";
  const partnerRole = state.private.role === "MAFIA_DEPUTY" ? "MAFIA_BOSS" : "MAFIA_DEPUTY";
  const relationship = state.private.role === "MAFIA_DEPUTY" ? text("yourBoss") : text("yourDeputy");
  return `<div class="mafia-partner${compact ? " is-compact" : ""}">
    <img src="${partner.profileImage}" alt="${escapeHTML(partner.name)}" />
    <div><span>${text("mafiaPartner")}</span><b>${escapeHTML(partner.name)}</b><small>${relationship}: ${escapeHTML(text("roles")[partnerRole])}</small></div>
  </div>`;
}

function factEventText(event) {
  if (event.type === "PLAYER_SHUNNED") {
    return `${playerName(event.player)} — ${text("factsShunned")}`;
  }
  if (event.type === "PLAYER_ELIMINATED") {
    const role = state.public?.revealed_roles?.[event.player];
    return `${playerName(event.player)} ${text("factsDayElimination")}${role ? ` — ${text("revealedRole")}: ${text("roles")[role]}` : ""}`;
  }
  if (event.type === "NIGHT_RESULT") {
    return event.result === "PLAYER_KILLED"
      ? `${playerName(event.player)} ${text("factsNightKill")}${event.revealed_role ? ` — ${text("roles")[event.revealed_role]}` : ""}`
      : text("factsNoDeath");
  }
  return "";
}

function eventProfilePlayer(event) {
  return event.actor || event.player || event.target || event.targets?.[0] || null;
}

function profileImageMarkup(playerId, className = "event-profile") {
  const character = playerId ? playerCharacter(playerId) : null;
  if (!character) return "";
  return `<img class="${className}" src="${character.profileImage}" alt="${escapeHTML(character.name)}" loading="lazy" />`;
}

function positionText(event) {
  const position = event.position;
  if (!position?.target) return "";
  const label = {fa: "مظنون اعلام‌شده", en: "Declared suspect", de: "Genannter Verdächtiger"}[state.lang];
  return `${label}: ${playerName(position.target)}. ${replacePlayerReferences(position.reason || "")}`;
}

function eventSummary(event) {
  if (["PLAYER_SHUNNED", "PLAYER_ELIMINATED", "NIGHT_RESULT"].includes(event.type)) return factEventText(event);
  if (event.type === "ROLE_CLAIMED") return `${playerName(event.actor)} — ${text("claimedRole")}: ${text("claims")[event.claimed_role] || event.claimed_role}`;
  if (event.type === "PLAYER_SPOKE") return `${playerName(event.actor)}: ${eventDialogue(event)}`;
  if (event.type === "PLAYER_ASKED") return `${playerName(event.actor)} → ${playerName(event.target)}: ${eventDialogue(event)}`;
  if (event.type === "PLAYER_ANSWERED") {
    const targets = event.targets || (event.target ? [event.target] : []);
    return `${playerName(event.actor)} → ${targets.map(playerName).join("، ")}: ${eventDialogue(event)}`;
  }
  if (event.type === "PLAYER_PASSED") return `${playerName(event.actor)} — ${eventDialogue(event)}`;
  if (event.type === "VOTE_CAST") return `${playerName(event.actor)} → ${playerName(event.target)}`;
  if (event.type === "ROLE_REVEALED") return `${playerName(event.player)} — ${text("revealedRole")}: ${text("roles")[event.role] || event.role}`;
  if (event.type === "INVESTIGATION_RESULT") return `${text("investigation")}: ${playerName(event.target)} — ${text("roles")[event.result] || event.result}`;
  if (event.type === "MAFIA_STRATEGY_SELECTED") return `${text("strategyTitle")}: ${text("strategies")[event.strategy] || event.strategy}`;
  return replacePlayerReferences(event.text || event.type.replaceAll("_", " "));
}

function renderClaims() {
  const claims = Object.entries(state.public.role_claims || {}).map(([playerId, role]) => {
    const player = state.public.players[playerId];
    const revealed = state.public.revealed_roles?.[playerId];
    const conflict = (revealed && revealed !== role) || (["DOCTOR", "DETECTIVE"].includes(role) && Object.entries(state.public.revealed_roles || {}).some(([id, actual]) => id !== playerId && actual === role));
    return `<li>${profileImageMarkup(playerId, "facts-profile")}<span><b>${escapeHTML(playerName(playerId))}</b><small>${text("claimedRole")}: ${escapeHTML(text("claims")[role] || role)}</small>${conflict ? `<small class="journal-conflict">${journalText("rejected")}</small>` : ""}${revealed ? `<small>${text("revealedRole")}: ${escapeHTML(text("roles")[revealed])}</small>` : ""}${!player.alive ? `<small>${text("factsEliminated")}</small>` : ""}</span></li>`;
  }).join("");
  return journalDisclosure("claims", text("factsClaims"), `<ul class="facts-claims">${claims || `<li class="facts-empty">${text("factsEmpty")}</li>`}</ul>`);
}

function renderTimeline() {
  return `<section id="journal-results" class="facts-section">${renderJournal(true)}</section>`;
}

function renderJournalPlayer() {
  if (!state.public || !state.private?.role) return "";
  const role = text("roles")[state.private.role] || state.private.role;
  return `${profileImageMarkup(state.playerId, "facts-player-photo")}<span><b>${escapeHTML(playerName(state.playerId))}</b><small>${escapeHTML(role)}</small></span>`;
}

function renderPrivateIntel() {
  if (!state.private) return renderClaims();
  const mafia = state.private.faction === "MAFIA" && isMafiaRole(state.private.role);
  const strategy = mafia ? state.private.mafia_private_information?.strategy : null;
  const scenario = strategy && text("strategies")[strategy] || journalText("scenarioPending");
  const isCitizen = ["CITIZEN", "DOCTOR", "DETECTIVE"].includes(state.private.role);
  const trust = isCitizen ? Object.entries(state.private.trust || {}).sort((a, b) => b[1] - a[1]).map(([playerId, value]) => `<li><span>${escapeHTML(playerName(playerId))}</span><div class="trust-meter"><i style="width:${value}%"></i></div><b>${value}</b></li>`).join("") : "";
  const investigations = (state.private.investigations || []).map((item) => `<li><span class="fact-round">${String(item.round).padStart(2, "0")}</span><p>${escapeHTML(playerName(item.target))} — ${escapeHTML(text("roles")[item.result] || item.result)}</p></li>`).join("");
  return `${mafia ? mafiaPartnerMarkup(true) : ""}
    ${mafia ? `<section class="facts-section mafia-scenario"><h3>${journalText("mafiaScenario")}</h3><p>${escapeHTML(scenario)}</p></section>` : ""}
    ${renderClaims()}
    ${trust ? journalDisclosure("trust", text("trust"), `<ul class="trust-list">${trust}</ul>`) : ""}
    ${investigations ? `<section class="facts-section"><h3>${text("investigations")}</h3><ul class="facts-events">${investigations}</ul></section>` : ""}
    ${state.private.previous_protection_target ? `<section class="facts-section"><h3>${text("previousProtection")}</h3><p>${escapeHTML(playerName(state.private.previous_protection_target))}</p></section>` : ""}`;
}

function renderFacts() {
  const drawer = $("#game-facts");
  if (!drawer) return;
  $("#facts-title").textContent = text("factsTitle");
  $("#facts-player").innerHTML = renderJournalPlayer();
  $("#facts-close").setAttribute("aria-label", text("close"));
  $("#facts-toggle").setAttribute("aria-label", text("facts"));
  $("#facts-toggle-label").textContent = text("facts");
  if (!["timeline", "private"].includes(state.consoleTab)) state.consoleTab = "timeline";
  const tabKeys = { timeline: "consoleTimeline", private: "consolePrivate" };
  $$('[data-console-tab]').forEach((button) => { button.textContent = text(tabKeys[button.dataset.consoleTab]); button.classList.toggle("is-active", button.dataset.consoleTab === state.consoleTab); });
  if (!state.public) {
    $("#facts-content").innerHTML = `<p class="facts-empty">${text("factsEmpty")}</p>`;
    return;
  }

  const renderers = { timeline: renderTimeline, private: renderPrivateIntel };
  const scrollTop = drawer.scrollTop;
  const expanded = new Map($$("[data-journal-key]", drawer).map((element) => [element.dataset.journalKey, element.open]));
  $("#facts-content").innerHTML = renderers[state.consoleTab]();
  decoratePlayerNames($("#facts-content"));
  enhancePlayerSelects($("#facts-content"));
  $$("[data-journal-key]", drawer).forEach((element) => {
    if (expanded.has(element.dataset.journalKey)) element.open = expanded.get(element.dataset.journalKey);
  });
  drawer.scrollTop = scrollTop;
  $$('[data-journal-filter]').forEach((input) => input.addEventListener("change", () => {
    state.journalFilters[input.dataset.journalFilter] = input.value;
    $("#journal-results").innerHTML = renderJournal(true);
    decoratePlayerNames($("#journal-results"));
  }));
}

function setFactsOpen(open) {
  $("#game-facts")?.classList.toggle("is-open", open);
  $("#game-facts")?.setAttribute("aria-hidden", String(!open));
  $("#facts-scrim")?.classList.toggle("is-open", open);
  $("#facts-toggle")?.setAttribute("aria-expanded", String(open));
  if (open) {
    playEffect("newspaper", true);
    renderFacts();
  }
}

function setLanguage(language) {
  state.lang = language;
  document.documentElement.lang = language;
  document.documentElement.dir = language === "fa" ? "rtl" : "ltr";
  $$("[data-language]").forEach((button) => button.classList.toggle("is-selected", button.dataset.language === language));
  $("#home-kicker").textContent = text("homeKicker");
  $("#home-title").innerHTML = text("homeTitle");
  $("#home-lead").textContent = text("homeLead");
  $("#new-game-label").textContent = text("newGame");
  const tutorialLabel = $("#tutorial-open-label");
  if (tutorialLabel) tutorialLabel.textContent = text("tutorial");
  $("#character-kicker").textContent = text("characterKicker");
  $("#character-title").textContent = text("characterTitle");
  $("#character-lead").textContent = text("characterLead");
  $("#loading-text").textContent = text("loading");
  renderCharacters();
  renderTutorial();
  refreshResumeControls();
  renderFacts();
  renderArchives();
}

function showScreen(id) {
  $$(".screen").forEach((screen) => screen.classList.toggle("is-active", screen.id === id));
  if (id !== "story-screen") setBackgroundMusic("cityMusic");
}

function renderTutorial() {
  const content = $("#tutorial-content");
  const guide = tutorialGuide[state.lang];
  if (!content || !guide) return;
  content.innerHTML = `
    <header class="tutorial-hero">
      <p class="eyebrow">${guide.kicker}</p>
      <h1>${guide.title}</h1>
      <p>${guide.intro}</p>
      <div class="tutorial-summary">
        ${guide.summary.map(([value, label]) => `<div><b>${value}</b><span>${label}</span></div>`).join("")}
      </div>
    </header>
    ${guide.sections.map(([title, body]) => `
      <section class="tutorial-section">
        <h2>${title}</h2>
        ${body}
      </section>
    `).join("")}
  `;
  $("#tutorial-back-label").textContent = guide.back;
  $("#tutorial-start-label").textContent = guide.start;
}

function renderCharacters() {
  $("#character-grid").innerHTML = characters.map((character) => `
    <button class="character-card" type="button" data-character="${character.id}" aria-label="${escapeHTML(character.name)}">
      <img src="${character.image}" alt="${escapeHTML(character.name)}" />
      <span class="pick-mark">↗</span>
      <span class="character-info"><b>${escapeHTML(character.name)}</b><span>${character.age} ${text("age")}</span></span>
    </button>
  `).join("");
  $$("[data-character]").forEach((button) => button.addEventListener("click", () => startGame(Number(button.dataset.character))));
}

function buildCharacterMap(selectedId) {
  const ordered = [characters.find((item) => item.id === selectedId), ...characters.filter((item) => item.id !== selectedId)];
  return Object.fromEntries(ordered.map((character, index) => [`P${index + 1}`, character]));
}

function showLoading(show) { $("#loading").classList.toggle("is-hidden", !show); }
function toast(message) {
  const element = $("#toast");
  element.textContent = message;
  element.classList.add("is-visible");
  window.setTimeout(() => element.classList.remove("is-visible"), 3500);
}

async function startGame(characterId) {
  state.archiveMode = false;
  state.journalFilters = { player: "", round: "", kind: "" };
  state.archiveSaveFailed = false;
  state.characterId = characterId;
  state.characterMap = buildCharacterMap(characterId);
  showLoading(true);
  try {
    const createRequest = () => fetchWithTimeout("/games/interactive", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        language: state.lang,
        character_id: characterId,
        ai_mode: "luna",
      }),
    });
    let response = await createRequest();
    if (response.status === 401) {
      const key = window.prompt({ fa: "کد دسترسی بازی آنلاین را وارد کن", en: "Enter the online play access code", de: "Zugangscode für das Online-Spiel eingeben" }[state.lang]);
      if (!key) return;
      const access = await fetchWithTimeout("/session", { method: "POST", headers: { "X-Play-Key": key } });
      if (!access.ok) throw new Error("access_denied");
      response = await createRequest();
    }
    if (!response.ok) {
      const error = new Error(await response.text()); error.status = response.status; throw error;
    }
    const created = await response.json();
    state.gameId = created.game_id;
    state.playerId = created.human.player_id;
    state.token = created.human.token;
    state.observationUrl = created.observation_url || `/game/${created.game_id}/player/${created.human.player_id}/observation`;
    state.availableActions = [];
    state.playerNames = {};
    state.consoleTab = "timeline";
    state.notes = { text: "", suspicion: {} };
    state.narrativeRound = 1;
    state.voteRound = null;
    state.nightRound = null;
    state.currentResultId = null;
    state.currentEventId = null;
    state.shownDiscussion.clear();
    state.acknowledgedResults.clear();
    state.events = [];
    state.drafts = {};
    state.pendingAction = null;
    state.nightReplay = [];
    state.stage = "role";
    saveSession();
    connectStream(created.stream_url);
    await syncState();
    showScreen("story-screen");
    showRoleReveal();
  } catch (error) {
    console.error(error);
    toast(error.status === 429 ? ({ fa: "ظرفیت یا سهمیهٔ بازی پر شده؛ بازی قبلی را ادامه بده یا کمی بعد تلاش کن.", en: "Game capacity or quota reached. Resume your game or try again later.", de: "Spiellimit erreicht. Bestehendes Spiel fortsetzen oder später versuchen." }[state.lang]) : text("networkError"));
    if (state.gameId) { showScreen("story-screen"); showStopped(true); scheduleRecovery(); }
  } finally {
    showLoading(false);
  }
}

async function syncState(route = true) {
  if (!state.gameId || state.archiveMode) return;
  syncNeedsRoute = syncNeedsRoute || route;
  if (syncPromise) {
    syncAgain = true;
    return syncPromise;
  }
  const requestedGameId = state.gameId;
  syncPromise = (async () => {
  const headers = { "X-Player-Token": state.token };
  const [observationResponse, runResponse] = await Promise.all([
    fetchWithTimeout(state.observationUrl || `/game/${state.gameId}/player/${state.playerId}/observation`, { headers }),
    fetchWithTimeout(`/game/${state.gameId}/run-state`, { headers }),
  ]);
  if (![observationResponse, runResponse].every((response) => response.ok)) {
    const error = new Error("state unavailable");
    error.status = !observationResponse.ok ? observationResponse.status : runResponse.status;
    throw error;
  }
  const observation = await observationResponse.json();
  const run = await runResponse.json();
  if (state.gameId !== requestedGameId || state.archiveMode) return;
  state.public = observation.public_state;
  state.private = observation.private_state;
  state.availableActions = observation.available_actions || [];
  state.playerNames = observation.player_names || {};
  state.events = observation.events || [];
  state.nightReplay = observation.night_replay || [];
  state.run = run;
  if (state.pendingAction && run.accepted_request_ids?.includes(state.pendingAction.id)) {
    delete state.drafts[state.pendingAction.draft_key];
    state.pendingAction = null;
    saveSession();
  }
  recoveryDelay = 1000;
  window.clearTimeout(recoveryTimer); recoveryTimer = null;
  $("#connection-state").classList.remove("offline");
  saveCompletedReport();
  renderFacts();
  $("#round-label").textContent = `DAY ${String(state.public.round).padStart(2, "0")}`;
  const fallbackCount = Number(state.run.fallback_actions || 0);
  $("#agent-status").classList.toggle("degraded", fallbackCount > 0);
  $("#agent-status").innerHTML = `<i></i> 6 × ${escapeHTML(state.run.ai_model || "AGENT")}${fallbackCount ? ` · ${fallbackCount} ${text("degraded")}` : ""}`;
  if (state.run.mode === "offline") $("#agent-status").title = text("offline");
  else if (fallbackCount) $("#agent-status").title = text("degraded");
  })();
  let synced = false;
  try {
    await syncPromise;
    synced = true;
  } finally {
    syncPromise = null;
    const shouldRoute = syncNeedsRoute;
    syncNeedsRoute = false;
    if (synced && shouldRoute && state.gameId === requestedGameId) routeAfterSync();
    if (syncAgain && state.gameId === requestedGameId) {
      syncAgain = false;
      scheduleSync();
    }
  }
}

function scheduleSync() {
  syncNeedsRoute = true;
  window.clearTimeout(syncTimer);
  syncTimer = window.setTimeout(() => {
    syncState(true).catch(() => scheduleRecovery());
  }, 100);
}

function connectStream(url) {
  if (state.eventSource) state.eventSource.close();
  const connection = $("#connection-state");
  state.eventSource = new EventSource(url);
  state.eventSource.addEventListener("open", () => connection.classList.remove("offline"));
  state.eventSource.addEventListener("error", () => { connection.classList.add("offline"); scheduleRecovery(); });
  state.eventSource.addEventListener("game-event", scheduleSync);
  // SSE carries public progress only; fetch the authenticated participant view.
  state.eventSource.addEventListener("run-state", scheduleSync);
  state.eventSource.addEventListener("stream-end", () => {
    state.eventSource.close();
    scheduleSync();
  });
}

function slideName(number) {
  return ["", "CHARACTER", "ROLE REVEAL", "PUBLIC CLAIM", "THE CLAIMS", "CITY DISCUSSION", "THE VOTE", "VOTE RESULT", "MAFIA NIGHT", "DOCTOR", "DETECTIVE", "NIGHT WATCH", "MORNING"][number];
}

function storyStageName(number) {
  const names = {
    fa: ["", "انتخاب چهره", "آشکارشدن نقش", "ادعای نقش", "ادعاها", "بحث شهر", "رأی‌گیری", "نتیجهٔ رأی", "شب مافیا", "اقدام پزشک", "استعلام کارآگاه", "انتظار شب", "صبح"],
    en: ["", "Character", "Role reveal", "Role claim", "Claims", "City discussion", "Voting", "Vote result", "Mafia night", "Doctor", "Detective", "Night watch", "Morning"],
    de: ["", "Figur", "Rollenaufdeckung", "Rollenbehauptung", "Behauptungen", "Stadtgespräch", "Abstimmung", "Abstimmungsergebnis", "Mafia-Nacht", "Arzt", "Detektiv", "Nachtwache", "Morgen"],
  };
  return (names[state.lang] || names.en)[number] || slideName(number);
}

function cancelTypewriter() {
  if (typewriterRun) {
    typewriterRun.timers.forEach((timer) => {
      window.clearTimeout(timer);
      window.clearInterval(timer);
    });
  }
  typewriterRun = null;
  stopEffect("typewriter");
}

function finishTypewriter(run) {
  run.remaining -= 1;
  if (run.remaining <= 0 && typewriterRun === run) {
    typewriterRun = null;
    stopEffect("typewriter");
  }
}

function typeText(element, value, run) {
  if (run !== typewriterRun) return;
  let index = 0;
  const timer = window.setInterval(() => {
    if (run !== typewriterRun) {
      window.clearInterval(timer);
      run.timers.delete(timer);
      return;
    }
    element.textContent += value[index] || "";
    index += 1;
    if (index >= value.length) {
      window.clearInterval(timer);
      run.timers.delete(timer);
      element.removeAttribute("data-typewriter");
      decoratePlayerNames(element);
      finishTypewriter(run);
    }
  }, 18);
  run.timers.add(timer);
}

function renderStory({ number, image, html, wide = false, centered = false, scrollable = false }) {
  typingVersion += 1;
  cancelTypewriter();
  $("#story-image").src = image;
  $("#scene-label").textContent = { fa: "مرحلهٔ فعلی", en: "Current scene", de: "Aktuelle Szene" }[state.lang] || "Current scene";
  $("#slide-name").textContent = storyStageName(number);
  $("#slide-round").textContent = number >= 5 && state.public?.round ? `${journalText("day")} ${state.public.round}` : "";
  const content = $("#story-content");
  content.className = `story-content${wide ? " wide" : ""}${centered ? " centered" : ""}${scrollable ? " scrollable-form" : ""}`;
  content.innerHTML = html;
  decoratePlayerNames(content);
  enhancePlayerSelects(content);
  const stage = $("#story-stage");
  stage.classList.remove("entering");
  requestAnimationFrame(() => stage.classList.add("entering"));
  setBackgroundMusic(storyMusic(number));
  stopEffect("footsteps");
  const typewriterElements = $$('[data-typewriter]', content);
  if (!typewriterElements.length || window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    typewriterElements.forEach((element) => { element.removeAttribute("data-typewriter"); });
    decoratePlayerNames(content);
    saveSession();
    return;
  }
  const run = { version: typingVersion, remaining: typewriterElements.length, timers: new Set() };
  typewriterRun = run;
  playEffect("typewriter", true);
  typewriterElements.forEach((element, index) => {
    const value = element.textContent;
    element.textContent = "";
    const timer = window.setTimeout(() => {
      run.timers.delete(timer);
      typeText(element, value, run);
    }, index * 180);
    run.timers.add(timer);
  });
  saveSession();
}

function showRoleReveal() {
  state.stage = "role";
  const character = playerCharacter(state.playerId);
  const role = state.private.role;
  renderStory({
    number: 2,
    image: character.image,
    html: `<div class="role-overlay">
      <p class="eyebrow">${text("roleReveal")}</p>
      <h2>${escapeHTML(character.name)}</h2>
      <span class="age">${character.age} ${text("age")}</span>
      <span class="role-chip">${text("yourRole")}: ${escapeHTML(text("roles")[role])}</span>
      ${mafiaPartnerMarkup()}
      <p class="role-note" data-typewriter>${escapeHTML(text("roleNotes")[role])}</p>
      <button id="role-next" class="primary-button" type="button"><span>${text("continue")}</span><span>←</span></button>
    </div>`,
  });
  $("#role-next").addEventListener("click", continueAfterRoleReveal);
}

async function continueAfterRoleReveal() {
  await syncState(false);
  if (state.availableActions.includes("SELECT_STRATEGY")) return showStrategy();
  if (state.availableActions.includes("ROLE_CLAIM")) return showClaim();
  state.stage = "wait_opening";
  showWaiting(2);
}

function showStrategy() {
  state.stage = "strategy";
  const character = playerCharacter(state.playerId);
  renderStory({
    number: 2,
    image: assets.mafia,
    html: `<p class="eyebrow">${text("privateFacts")}</p><h2 data-typewriter>${text("strategyTitle")}</h2><p class="story-text">${text("strategyText")}</p>
      <div class="strategy-grid">${Object.entries(text("strategies")).map(([strategy, label]) => `<button class="choice-button strategy-choice" data-strategy="${strategy}" type="button">${escapeHTML(label)}</button>`).join("")}</div>`,
  });
  $$('[data-strategy]').forEach((button) => button.addEventListener("click", async () => {
    await submitAndAdvance({ action: "SELECT_STRATEGY", strategy: button.dataset.strategy }, "wait_strategy", 2);
  }));
}

function showClaim() {
  state.stage = "claim";
  const character = playerCharacter(state.playerId);
  renderStory({
    number: 3,
    image: character.image,
    html: `<p class="eyebrow">${slideName(3)}</p>
      <h2 data-typewriter>${text("claimTitle")}</h2>
      <p class="story-text" data-typewriter>${text("claimText")}</p>
      <div class="story-actions">
        ${["CITIZEN", "DOCTOR", "DETECTIVE"].map((role) => `<button class="choice-button" data-claim="${role}" type="button">${text("claims")[role]}</button>`).join("")}
      </div>`,
  });
  $$("[data-claim]").forEach((button) => button.addEventListener("click", async () => {
    await submitAndAdvance({ action: "ROLE_CLAIM", claimed_role: button.dataset.claim }, "wait_claims", 3);
  }));
}

function showWaiting(number) {
  renderStory({
    number,
    image: number >= 8 ? assets.citizen : assets.town,
    centered: true,
    html: `<img class="loading-mark" src="/ui/Images/Logo-transparent.png?v=20261006" alt="" aria-hidden="true" /><p class="story-text" data-typewriter>${text("waiting")}</p>`,
  });
  playEffect("footsteps", true);
}

function showClaims() {
  state.stage = "claims";
  renderStory({
    number: 4,
    image: assets.town,
    wide: true,
    html: `<div class="selection-heading">
      <p class="eyebrow">${slideName(4)}</p><h2>${text("claimsTitle")}</h2><p>${text("claimsText")}</p>
    </div>
    <div class="claims-grid">${Object.entries(state.public.role_claims).map(([playerId, role]) => {
      const character = playerCharacter(playerId);
      return `<article class="claim-card ${playerId === state.playerId ? "is-human" : ""}">
        <img src="${character.image}" alt="${escapeHTML(character.name)}" />
        <div><b>${escapeHTML(character.name)}</b><span>${escapeHTML(text("roles")[role])}</span></div>
      </article>`;
    }).join("")}</div>
    <div class="story-actions"><button id="claims-next" class="primary-button" type="button"><span>${text("continue")}</span><span>←</span></button></div>`,
  });
  $("#claims-next").addEventListener("click", () => { state.stage = "play"; routePlay(); });
}

const discussionTypes = new Set(["PLAYER_SPOKE", "PLAYER_ASKED", "PLAYER_ANSWERED", "PLAYER_PASSED"]);

function routePlay() {
  if (!state.public || !state.run) return;
  if (["FAILED", "CANCELLED"].includes(state.run.status)) return showStopped();
  const event = state.events.find((item) => (
    discussionTypes.has(item.type)
    && item.round === state.narrativeRound
    && !state.shownDiscussion.has(item.event_id)
  ));
  if (event) return showDiscussionEvent(event);

  const actions = state.availableActions;
  if (state.public.round === state.narrativeRound && state.run.status === "WAITING_FOR_HUMAN" && actions.some((action) => ["SPEAK", "ASK", "PASS", "ANSWER"].includes(action))) {
    return showHumanDiscussion(actions);
  }
  const result = state.events.find((item) => item.round === state.narrativeRound
    && !state.acknowledgedResults.has(item.event_id)
    && (isVoteResult(item) || item.type === "NIGHT_RESULT"));
  if (result) {
    state.voteRound = result.round;
    state.nightRound = result.round;
    return result.type === "NIGHT_RESULT" ? showMorning(result) : showVoteResult(result);
  }
  if (state.public.phase === "DAY_VOTING" && state.public.round === state.narrativeRound
      && actions.includes("SUBMIT_VOTE_DECISION") && state.run.status === "WAITING_FOR_HUMAN") return showVote();
  if (state.public.phase === "GAME_OVER") return showGameOver();
  if (state.public.players[state.playerId]?.alive === false) return showSpectator();
  state.stage = "play_wait";
  showWaiting(5);
}

function showSpectator() {
  state.stage = "play_wait";
  renderStory({ number: 5, image: assets.town, centered: true,
    html: `<h2>${state.lang === "fa" ? "در حال تماشای بازی" : state.lang === "de" ? "Du schaust zu" : "Watching the game"}</h2><p class="story-text">${state.lang === "fa" ? "بازی برای دیگران ادامه دارد. گفتگوها و نتیجه‌ها در دفتر وقایع ثبت می‌شوند." : state.lang === "de" ? "Das Spiel geht weiter. Gespräche und Ergebnisse stehen im Journal." : "The game continues. Follow conversations and results in the journal."}</p>` });
}

function eventDialogue(event) {
  if (event.type === "PLAYER_PASSED") return state.lang === "fa" ? "ترجیح می‌دهم فعلاً سکوت کنم." : state.lang === "de" ? "Ich schweige vorerst." : "I choose to remain silent for now.";
  return [replacePlayerReferences(event.text || "…"), positionText(event)].filter(Boolean).join("\n");
}

function dialogueDensity(value) {
  const length = String(value).length;
  if (length > 520) return " is-dense";
  if (length > 280) return " is-compact";
  return "";
}

function showDiscussionEvent(event) {
  state.stage = "discussion_event";
  state.currentEventId = event.event_id;
  const actor = event.actor || event.player;
  const character = playerCharacter(actor);
  const dialogue = eventDialogue(event);
  renderStory({
    number: 5,
    image: character.image,
    html: `<div class="dialogue-box"><p class="eyebrow">${text("discussion")} · ${String(event.discussion_turn || "").padStart(2, "0")}</p>
      <span class="claim-badge">${text("claimedRole")}: ${escapeHTML(claimedRole(actor))}</span>
      <span class="quote-mark">“</span><blockquote class="dialogue-copy${dialogueDensity(dialogue)}" data-typewriter>${escapeHTML(dialogue)}</blockquote>
      <p class="speaker-name">${escapeHTML(character.name)} · ${escapeHTML(event.type.replace("PLAYER_", ""))}</p>
      <button id="dialogue-next" class="primary-button" type="button"><span>${text("continue")}</span><span>←</span></button>
    </div>`,
  });
  $("#dialogue-next").addEventListener("click", () => {
    state.shownDiscussion.add(state.currentEventId);
    state.stage = "play";
    routePlay();
  });
}

function activeMention(value, caret) {
  const prefix = value.slice(0, caret);
  const match = /(^|[\s([{،؛])@([^\n@،؛!?]{0,48})$/u.exec(prefix);
  if (!match) return null;
  return { start: caret - match[2].length - 1, end: caret, query: match[2] };
}

function insertPlayerMention(value, mention, name) {
  const suffix = value.slice(mention.end);
  const inserted = `@${name}${/^[\s،؛,!.?؟]/u.test(suffix) ? "" : " "}`;
  return {
    value: value.slice(0, mention.start) + inserted + suffix,
    caret: mention.start + inserted.length,
  };
}

function bindPlayerMentions() {
  const input = $("#human-text");
  const menu = $("#player-mentions");
  if (!input || !menu) return;
  const dialogue = menu.closest?.(".dialogue-box");
  let choices = [];
  let active = 0;
  let mention = null;
  const close = () => {
    menu.hidden = true;
    menu.innerHTML = "";
    dialogue?.classList.remove("mention-open");
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
  };
  const markActive = () => {
    $$('[data-mention-player]', menu).forEach((button, index) => {
      button.classList.toggle("is-active", index === active);
      button.setAttribute("aria-selected", String(index === active));
    });
    input.setAttribute("aria-activedescendant", `mention-option-${active}`);
  };
  const select = (playerId) => {
    if (!mention) return;
    const next = insertPlayerMention(input.value, mention, playerName(playerId));
    input.value = next.value;
    input.focus();
    input.setSelectionRange(next.caret, next.caret);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    close();
  };
  const refresh = () => {
    if (input.selectionStart !== input.selectionEnd) return close();
    mention = activeMention(input.value, input.selectionStart);
    if (!mention) return close();
    const query = mention.query.toLocaleLowerCase();
    choices = Object.keys(state.public?.players || {}).filter((id) => playerName(id).toLocaleLowerCase().includes(query));
    if (!choices.length) return close();
    active = 0;
    menu.innerHTML = choices.map((id, index) => {
      const character = playerCharacter(id);
      return `<button id="mention-option-${index}" type="button" role="option" data-mention-player="${escapeHTML(id)}" aria-selected="false"><img src="${escapeHTML(character.profileImage)}" alt="" /><span>${escapeHTML(playerName(id))}</span></button>`;
    }).join("");
    menu.hidden = false;
    dialogue?.classList.add("mention-open");
    input.setAttribute("aria-expanded", "true");
    markActive();
    $$('[data-mention-player]', menu).forEach((button) => {
      button.addEventListener("pointerdown", (event) => event.preventDefault());
      button.addEventListener("click", () => select(button.dataset.mentionPlayer));
    });
  };
  input.addEventListener("input", refresh);
  input.addEventListener("click", refresh);
  input.addEventListener("keyup", (event) => {
    if (["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) refresh();
  });
  input.addEventListener("keydown", (event) => {
    if (menu.hidden || !choices.length) return;
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      active = (active + (event.key === "ArrowDown" ? 1 : -1) + choices.length) % choices.length;
      markActive();
      $(`#mention-option-${active}`, menu)?.scrollIntoView({ block: "nearest" });
    } else if (event.key === "Enter" || event.key === "Tab") {
      event.preventDefault();
      select(choices[active]);
    } else if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  });
  input.addEventListener("blur", () => window.setTimeout(close, 100));
}

function showHumanDiscussion(actions) {
  state.stage = "human_discussion";
  const answering = actions.includes("ANSWER");
  const character = playerCharacter(state.playerId);
  const answeredIds = new Set(state.events
    .filter((event) => event.type === "PLAYER_ANSWERED")
    .flatMap((event) => event.question_ids || (event.question_id ? [event.question_id] : [])));
  const pendingQuestions = state.events.filter((event) => (
    event.type === "PLAYER_ASKED"
    && event.target === state.playerId
    && !answeredIds.has(event.question_id)
  ));
  const askCandidates = selectablePlayers((playerId) => playerId !== state.playerId);
  renderStory({
    number: 5,
    image: character.image,
    scrollable: answering,
    html: `<div class="dialogue-box${answering ? " is-answering" : ""}"><p class="eyebrow">${text("discussion")}</p><span class="claim-badge">${text("claimedRole")}: ${escapeHTML(claimedRole(state.playerId))}</span><h2 data-typewriter>${answering ? text("answerTurn") : text("yourTurn")}</h2>
      ${answering ? `<div class="question-list" tabindex="0" aria-label="${journalText("question")}">${pendingQuestions.map((question) => `<div class="question-card"><small>${text("questionFrom")} ${escapeHTML(playerName(question.actor))}</small><p>${escapeHTML(replacePlayerReferences(question.text))}</p></div>`).join("")}</div>` : ""}
      <div class="input-panel"><textarea id="human-text" maxlength="${answering ? 1200 : 500}" aria-controls="player-mentions" aria-autocomplete="list" aria-expanded="false" placeholder="${answering ? text("answerPlaceholder") : text("statementPlaceholder")}"></textarea>
        <div id="player-mentions" class="mention-menu" role="listbox" hidden></div>
        <small class="mention-hint">${text("mentionHint")}</small>
        ${!answering && actions.includes("ASK") ? `<label class="ask-panel"><span>${text("askTarget")}</span><select id="ask-target"><option value="">${text("choosePlayer")}</option>${askCandidates.map((playerId) => `<option value="${playerId}">${escapeHTML(playerName(playerId))}</option>`).join("")}</select></label>` : ""}
        <div class="story-actions">${actions.includes(answering ? "ANSWER" : "SPEAK") ? `<button id="submit-speech" class="primary-button" type="button">${answering ? text("answer") : text("speak")}</button>` : ""}
        ${!answering && actions.includes("ASK") ? `<button id="ask-player" class="secondary-button" type="button">${text("ask")}</button>` : ""}
        ${!answering && actions.includes("PASS") ? `<button id="pass-turn" class="secondary-button" type="button">${text("pass")}</button>` : ""}</div>
      </div>
    </div>`,
  });
  const draft = state.drafts[draftKey("human_discussion")] || {};
  $("#human-text").value = draft.text || "";
  const askTarget = $("#ask-target");
  if (askTarget && draft.target) { askTarget.value = draft.target; askTarget.dispatchEvent?.(new Event("change", { bubbles: true })); }
  const rememberDraft = () => saveDraft("human_discussion", { text: $("#human-text").value, target: $("#ask-target")?.value || "" });
  $("#human-text").addEventListener("input", rememberDraft);
  askTarget?.addEventListener("change", rememberDraft);
  bindPlayerMentions();
  $("#submit-speech")?.addEventListener("click", async () => {
    const value = $("#human-text").value.trim();
    if (!value) return $("#human-text").focus();
    const payload = { action: answering ? "ANSWER" : "SPEAK", text: value };
    await submitAndAdvance(payload, "play_wait", 5);
  });
  $("#ask-player")?.addEventListener("click", async () => {
    const value = $("#human-text").value.trim();
    const target = $("#ask-target").value;
    if (!value) return $("#human-text").focus();
    if (!target) return $("#ask-target").focus();
    await submitAndAdvance({ action: "ASK", target, text: value }, "play_wait", 5);
  });
  $("#pass-turn")?.addEventListener("click", async () => {
    await submitAndAdvance({ action: "PASS" }, "play_wait", 5);
  });
}

function selectablePlayers(filter = () => true) {
  return Object.entries(state.public.players)
    .filter(([playerId, player]) => player.alive && filter(playerId, player))
    .map(([playerId]) => playerId);
}

function targetCards(players, action) {
  return players.map((playerId) => {
    const character = playerCharacter(playerId);
    return `<button class="target-card" data-target="${playerId}" data-action="${action}" type="button">
      <img src="${character.image}" alt="${escapeHTML(character.name)}" />
      <span class="character-info"><b>${escapeHTML(character.name)}</b><span>${escapeHTML(claimedRole(playerId))}</span></span>
    </button>`;
  }).join("");
}

function bindTargets(payloadFactory, waitingSlide) {
  $$("[data-target]").forEach((button) => button.addEventListener("click", async () => {
    await submitAndAdvance(payloadFactory(button.dataset.target), waitingSlide,
      waitingSlide === "vote_wait" ? 6 : nightSlideNumber());
  }));
}

function showVote() {
  state.stage = "vote";
  state.voteRound = state.public.round;
  const candidates = selectablePlayers((playerId) => playerId !== state.playerId);
  const citizen = !isMafiaRole(state.private.role);
  const needsSecondSuspect = citizen;
  const options = (selected = "") => `<option value="">${text("choosePlayer")}</option>${candidates.map((playerId) => `<option value="${playerId}" ${selected === playerId ? "selected" : ""}>${escapeHTML(playerName(playerId))}</option>`).join("")}`;
  renderStory({
    number: 6,
    image: assets.town,
    wide: true,
    html: `<div class="selection-heading"><p class="eyebrow">${slideName(6)}</p><h2 data-typewriter>${text("voteTitle")}</h2><p>${state.lang === "fa" ? "هدف رأی را انتخاب کن. انتخاب‌های دیگر برای شهروندان اختیاری‌اند." : state.lang === "de" ? "Wähle dein Stimmziel. Weitere Angaben sind für Bürger freiwillig." : "Choose your vote. Citizens may optionally add a second suspect and a trusted player."}</p></div>
      <div class="vote-layout"><div class="target-grid">${targetCards(candidates, "SUBMIT_VOTE_DECISION")}</div>
      <div class="vote-decision-panel"><b>${text("voteTarget")}</b><span id="selected-vote">—</span>
        ${citizen ? `<label>${text("secondSuspect")}<select id="second-suspect" disabled>${options()}</select></label>
        <label>${text("trustedPlayer")}<select id="trusted-player" disabled>${options()}</select></label>` : ""}
        <button id="confirm-vote" class="primary-button" type="button" disabled>${text("confirmVote")}</button></div></div>`,
  });
  const draft = state.drafts[draftKey("vote")] || {};
  let voteTarget = candidates.includes(draft.voteTarget) ? draft.voteTarget : null;
  for (const [selector, value] of [["#trusted-player", draft.trusted], ["#second-suspect", draft.suspect]]) {
    const input = $(selector);
    if (input && candidates.includes(value)) { input.value = value; input.dispatchEvent?.(new Event("change", { bubbles: true })); }
  }
  const validate = () => {
    const trustedInput = $("#trusted-player");
    const suspectInput = $("#second-suspect");
    for (const input of [suspectInput, trustedInput].filter(Boolean)) {
      input.disabled = !voteTarget;
      if (input.value === voteTarget) input.value = "";
    }
    if (trustedInput?.value && trustedInput.value === suspectInput?.value) trustedInput.value = "";
    for (const [input, other] of [[suspectInput, trustedInput], [trustedInput, suspectInput]]) {
      if (!input) continue;
      for (const option of input.options) {
        option.disabled = Boolean(option.value && (option.value === voteTarget || option.value === other?.value));
        option.hidden = option.disabled;
      }
      input.dispatchEvent(new Event("picker-refresh"));
    }
    const trusted = trustedInput?.value || null;
    const suspect = suspectInput?.value || null;
    $("#confirm-vote").disabled = !voteTarget;
    saveDraft("vote", { voteTarget, trusted, suspect });
  };
  $$('[data-target]').forEach((button) => button.addEventListener("click", () => {
    voteTarget = button.dataset.target;
    $$('[data-target]').forEach((item) => item.classList.toggle("is-selected", item === button));
    $("#selected-vote").textContent = playerName(voteTarget);
    decoratePlayerNames($("#selected-vote"));
    validate();
  }));
  $("#trusted-player")?.addEventListener("change", validate);
  $("#second-suspect")?.addEventListener("change", validate);
  if (voteTarget) {
    $$('[data-target]').forEach((button) => button.classList.toggle("is-selected", button.dataset.target === voteTarget));
    $("#selected-vote").textContent = playerName(voteTarget);
    decoratePlayerNames($("#selected-vote"));
  }
  validate();
  $("#confirm-vote").addEventListener("click", async () => {
    const payload = { action: "SUBMIT_VOTE_DECISION", vote_target: voteTarget };
    if (citizen && $("#trusted-player").value) payload.trusted_player = $("#trusted-player").value;
    if (citizen && $("#second-suspect").value) payload.suspect_2 = $("#second-suspect").value;
    await submitAndAdvance(payload, "vote_wait", 6);
  });
}

function showVoteResult(event) {
  state.stage = "vote_result";
  state.currentResultId = event.event_id;
  state.voteRound = event.round;
  let detail = text("tied");
  let subject = "";
  if (event?.type === "PLAYER_SHUNNED") {
    subject = playerName(event.player);
    detail = `${subject} ${text("shunned")}`;
  } else if (event?.type === "PLAYER_ELIMINATED") {
    subject = playerName(event.player);
    detail = `${subject} ${text("eliminated")}`;
  }
  renderStory({
    number: 7,
    image: assets.town,
    html: `<span class="result-banner">${slideName(7)}</span><h2 data-typewriter>${text("voteResult")}</h2><p class="story-text" data-typewriter>${escapeHTML(detail)}</p>
      <button id="vote-next" class="primary-button" type="button"><span>${text("continue")}</span><span>←</span></button>`,
  });
  $("#vote-next").addEventListener("click", () => {
    state.acknowledgedResults.add(event.event_id);
    state.nightRound = event.round;
    if (state.public.phase === "GAME_OVER" && !nightResultEvent()) showGameOver(); else if (state.public.players[state.playerId]?.alive === false) { state.stage = "play"; routePlay(); } else showNight();
  });
}

function nightSlideNumber() {
  const role = state.private.role;
  if (["MAFIA_BOSS", "MAFIA_DEPUTY"].includes(role)) return 8;
  if (role === "DOCTOR") return 9;
  if (role === "DETECTIVE") return 10;
  return 11;
}

function showNight() {
  state.nightRound = state.voteRound || state.public.round;
  const role = state.private.role;
  const actions = state.availableActions;
  let number = nightSlideNumber();
  let image = assets.citizen;
  let title = text("citizenNight");
  let description = text("citizenText");
  let action = null;
  let passiveButtonLabel = text("nightContinue");
  const partner = state.private.mafia_private_information?.partner;
  if (role === "MAFIA_BOSS") {
    image = assets.mafia;
    if (actions.includes("KILL")) {
      title = text("mafiaNight"); description = text("mafiaText"); action = "KILL";
    } else {
      title = text("mafiaDisabledNight"); description = text("mafiaDisabledText");
      passiveButtonLabel = text("waitForMorning");
    }
  } else if (role === "MAFIA_DEPUTY") {
    image = assets.mafia;
    if (actions.includes("KILL")) {
      title = text("deputyCommandNight"); description = text("deputyCommandText"); action = "KILL";
    } else if (state.private.shunned || !state.private.alive) {
      title = text("mafiaDisabledNight"); description = text("mafiaDisabledText");
      passiveButtonLabel = text("waitForMorning");
    } else {
      title = text("deputyWaitingNight");
      description = formatText("deputyWaitingText", { name: playerName(partner) });
      passiveButtonLabel = text("waitForMorning");
    }
  } else if (role === "DOCTOR") {
    image = assets.doctor; title = text("doctorNight"); description = text("doctorText");
    if (actions.includes("PROTECT")) action = "PROTECT";
  } else if (role === "DETECTIVE") {
    image = assets.detective; title = text("detectiveNight"); description = text("detectiveText");
    if (actions.includes("INVESTIGATE")) action = "INVESTIGATE";
  }

  const eventReady = nightResultEvent();
  if (!action) {
    state.stage = "night_intro";
    renderStory({
      number, image,
      html: `<span class="night-icon">${String(number).padStart(2, "0")}</span><p class="eyebrow">NIGHT ${String(state.nightRound).padStart(2, "0")}</p><h2 data-typewriter>${title}</h2><p class="story-text" data-typewriter>${description}</p>
        <button id="night-next" class="primary-button" type="button"><span>${passiveButtonLabel}</span><span>←</span></button>`,
    });
    $("#night-next").addEventListener("click", () => {
      state.stage = "night_wait";
      if (nightResultEvent()) showMorning(nightResultEvent()); else showWaiting(number);
    });
    return;
  }

  const candidates = selectablePlayers((playerId, player) => {
    if (action === "KILL") return playerId !== state.playerId && playerId !== partner;
    if (["PROTECT", "INVESTIGATE"].includes(action) && player.shunned) return false;
    if (action === "PROTECT" && playerId === state.private.previous_protection_target) return false;
    return true;
  });
  state.stage = "night_action";
  renderStory({
    number, image, wide: true,
    html: `<div class="selection-heading"><p class="eyebrow">${text("selectTarget")}</p><h2 data-typewriter>${title}</h2><p>${description}</p></div>
      <div class="target-grid">${targetCards(candidates, action)}</div>`,
  });
  bindTargets((target) => ({ action, target }), "night_wait");
  if (eventReady) state.stage = "night_action";
}

function nightResultEvent() {
  return state.events.find((event) => event.type === "NIGHT_RESULT" && event.round === state.nightRound);
}

function showMorning(event) {
  state.stage = "morning";
  state.currentResultId = event.event_id;
  const killed = event?.result === "PLAYER_KILLED" ? event.player : null;
  let detail = killed ? `${playerName(killed)} ${text("wasKilled")} ${text("revealedRole")}: ${text("roles")[event.revealed_role] || event.revealed_role}.` : text("nobodyDied");
  const investigation = [...(state.private.investigations || [])].reverse().find((item) => item.round === event?.round);
  if (investigation) detail += ` ${text("investigation")}: ${playerName(investigation.target)} — ${text("roles")[investigation.result]}.`;
  renderStory({
    number: 12,
    image: assets.morning,
    html: `<span class="result-banner">${slideName(12)} · ${String(event?.round || state.public.round).padStart(2, "0")}</span><h2 data-typewriter>${text("morning")}</h2><p class="story-text" data-typewriter>${escapeHTML(detail)}</p>
      <button id="morning-next" class="primary-button" type="button"><span>${text("nextDay")}</span><span>←</span></button>`,
  });
  $("#morning-next").addEventListener("click", async (clickEvent) => {
    const button = clickEvent.currentTarget;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    try {
      // The runner may already have advanced while the morning slide was being read.
      // Refresh before routing so slide 12 never continues from a stale phase snapshot.
      await syncState(false);
      state.acknowledgedResults.add(event.event_id);
      state.narrativeRound = Number(event.round) + 1;
      state.stage = "play";
      routePlay();
    } catch (error) {
      console.error(error);
      toast(text("networkError"));
      button.disabled = false;
      button.removeAttribute("aria-busy");
    }
  });
}

function showGameOver() {
  state.stage = "game_over";
  const winner = state.public.winner ? text("roles")[state.public.winner] || state.public.winner : "—";
  renderStory({
    number: 12,
    image: assets.morning,
    centered: true,
    html: `<p class="eyebrow">GAME OVER</p><h2 data-typewriter>${text("gameOver")}</h2><p class="story-text">${text("winner")}: ${escapeHTML(winner)}</p>
      <button id="review-nights" class="secondary-button" type="button">${{fa:"بازبینی شب‌ها",en:"Review nights",de:"Nächte ansehen"}[state.lang]}</button>
      <details class="postgame-lesson"><summary>${state.lang === "fa" ? "درس این بازی" : state.lang === "de" ? "Aus diesem Spiel lernen" : "Learn from this game"}</summary><p>${state.lang === "fa" ? "کدام تصمیم با اطلاعات همان لحظه قابل دفاع بود؟ کجا نتیجه بیشتر به شانس وابسته بود؟ گفتگوها و رأی‌ها را مرور کن؛ پیروزی به‌تنهایی درستی یک راهبرد را ثابت نمی‌کند." : state.lang === "de" ? "Welche Entscheidung war mit dem damaligen Wissen begründet? Wo spielte Glück eine Rolle? Ein Sieg allein beweist keine Strategie." : "Which decisions made sense with the information available then? Where did luck matter? Winning alone does not validate a strategy."}</p><button id="download-analysis" class="secondary-button" type="button">${state.lang === "fa" ? "دریافت گزارش تحلیل" : state.lang === "de" ? "Analyse herunterladen" : "Download analysis"}</button></details>
      <button id="restart" class="primary-button" type="button"><span>${text("newStory")}</span><span>↻</span></button>`,
  });
  $("#review-nights").addEventListener("click", () => { state.consoleTab = "timeline"; state.journalFilters = {player:"",round:"",kind:""}; renderFacts(); setFactsOpen(true); });
  $("#download-analysis")?.addEventListener("click", async () => {
    const button = $("#download-analysis"); button.disabled = true;
    try {
      const response = await fetchWithTimeout(`/game/${state.gameId}/analysis`);
      if (!response.ok) throw new Error("analysis unavailable");
      const report = await response.json();
      const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type:"application/json"}));
      const link = document.createElement("a"); link.href = url; link.download = `${state.gameId}-analysis.json`; link.click(); URL.revokeObjectURL(url);
    } catch { toast(text("networkError")); }
    finally { button.disabled = false; }
  });
  $("#restart").addEventListener("click", goHome);
}

function showStopped(connectionError = false) {
  state.stage = connectionError ? "connection_error" : "stopped";
  renderStory({
    number: 12, image: assets.morning, centered: true,
    html: `<h2>${text("stopped")}</h2><p class="story-text">${text(connectionError ? "networkError" : state.run?.status === "CANCELLED" ? "cancelledText" : "failedText")}</p>
      ${connectionError ? `<button id="retry-connection" class="primary-button" type="button">${text("reconnect")}</button>` : ""}
      <button id="stopped-home" class="secondary-button" type="button">${text("newStory")}</button>`,
  });
  $("#retry-connection")?.addEventListener("click", restoreSession);
  $("#stopped-home").addEventListener("click", goHome);
}

async function submitAndAdvance(payload, waitingStage, slide) {
  if (actionInFlight) return;
  actionInFlight = true;
  const gameId = state.gameId;
  const previousStage = state.stage;
  const submittedDraftKey = draftKey(previousStage);
  const controls = $$("#story-content button, #story-content input, #story-content select, #story-content textarea")
    .map((element) => ({ element, disabled: element.disabled }));
  controls.forEach(({ element }) => { element.disabled = true; });
  // Persist the intended transition before sending: reload can recover even
  // when the server accepted the action but its response has not arrived.
  state.stage = waitingStage;
  saveSession();
  try {
    await submitHumanAction(payload);
    delete state.drafts[submittedDraftKey];
    if (state.gameId !== gameId || state.stage === "home") return;
    showWaiting(slide);
  } catch (error) {
    if (state.gameId !== gameId || state.stage === "home") return;
    // Reconcile ambiguous network failures before offering a retry.
    try { await syncState(false); } catch { /* Retain the action form for retry. */ }
    if (state.availableActions.includes(payload.action)) state.stage = previousStage;
    else showWaiting(slide);
    toast(text("networkError"));
    scheduleRecovery();
  } finally {
    controls.forEach(({ element, disabled }) => { element.disabled = disabled; });
    actionInFlight = false;
    if (state.gameId === gameId && state.stage !== "home") {
      // Always route the latest snapshot, independent of SSE/HTTP ordering.
      routeAfterSync();
      saveSession();
    }
  }
}

async function submitHumanAction(payload) {
  const legalActions = [...state.availableActions];
  try {
    if (!legalActions.includes(payload.action)) {
      await syncState(false);
      if (!state.availableActions.includes(payload.action)) throw new Error("stale action");
    }
    state.availableActions = [];
    const serialized = JSON.stringify(payload);
    if (!state.pendingAction || state.pendingAction.payload !== serialized) {
      state.pendingAction = {
        id: globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        payload: serialized,
        draft_key: draftKey(payload.action === "SUBMIT_VOTE_DECISION" ? "vote" : "human_discussion"),
        expected_event_id: state.events.at(-1)?.event_id || null,
      };
      saveSession();
    }
    const response = await fetchWithTimeout(`/game/${state.gameId}/interactive/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Player-Token": state.token },
      body: JSON.stringify({ ...payload, request_id: state.pendingAction.id, expected_event_id: state.pendingAction.expected_event_id }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      if (response.status === 409) {
        state.pendingAction = null;
        await syncState(false);
        routeAfterSync();
      }
      throw new Error(body.detail || body.error || "action failed");
    }
    await response.json();
    if (state.pendingAction) delete state.drafts[state.pendingAction.draft_key];
    state.pendingAction = null;
    saveSession();
    await syncState(false);
  } catch (error) {
    if (!state.availableActions.length) state.availableActions = legalActions;
    throw error;
  }
}

function isVoteResult(event) {
  return event.type === "VOTE_TIED" || event.type === "PLAYER_SHUNNED"
    || (event.type === "PLAYER_ELIMINATED" && event.reason === "DAY_VOTE");
}

function routeAfterSync() {
  if (state.archiveMode || !state.public || !state.run || actionInFlight || ["restoring", "home"].includes(state.stage)) return;
  if (["FAILED", "CANCELLED"].includes(state.run.status)) {
    if (state.stage !== "stopped") showStopped();
    return;
  }
  if (["wait_opening", "wait_strategy"].includes(state.stage)) {
    if (state.availableActions.includes("SELECT_STRATEGY")) return showStrategy();
    if (state.availableActions.includes("ROLE_CLAIM")) return showClaim();
    return;
  }
  if (state.stage === "wait_claims") {
    if (Object.keys(state.public.role_claims || {}).length === 7 || state.public.phase !== "ROLE_CLAIM") showClaims();
    return;
  }
  if (["play", "play_wait"].includes(state.stage)) {
    state.stage = "play";
    routePlay();
    return;
  }
  if (state.stage === "vote_wait") {
    const result = state.events.find((event) => event.round === state.voteRound && isVoteResult(event));
    if (result) showVoteResult(result);
    return;
  }
  if (state.stage === "night_wait") {
    const result = nightResultEvent();
    if (result) showMorning(result);
  }
}

function refreshResumeControls() {
  const saved = readStored(SESSION_KEY, null);
  const labels = { fa: ["ادامهٔ بازی", "پایان دادن به بازی"], en: ["Resume game", "End game"], de: ["Spiel fortsetzen", "Spiel beenden"] }[state.lang];
  for (const [index, id] of ["#resume-game", "#end-game"].entries()) {
    const button = $(id); if (!button) continue;
    button.hidden = !saved; button.textContent = labels[index];
  }
}

async function endSavedGame() {
  const saved = readStored(SESSION_KEY, null);
  if (!saved) return true;
  const prompt = { fa: "این بازی پایان یابد؟ دیگر نمی‌توانی آن را ادامه بدهی.", en: "End this game? It cannot be resumed.", de: "Dieses Spiel beenden? Es kann nicht fortgesetzt werden." }[state.lang];
  if (!window.confirm(prompt)) return false;
  try {
    const response = await fetchWithTimeout(`/game/${saved.gameId}/run/cancel`, {
      method: "POST", headers: { "X-Player-Token": saved.token },
    });
    await response.json();
    if (!response.ok && ![404, 409].includes(response.status)) throw new Error("cancel_failed");
    clearSession(); state.gameId = null; state.token = null; state.pendingAction = null;
    refreshResumeControls(); return true;
  } catch { toast(text("networkError")); return false; }
}

async function goHome() {
  const active = !state.archiveMode && state.gameId && state.run && ["QUEUED", "RUNNING", "WAITING_FOR_HUMAN"].includes(state.run.status);
  if (active) saveSession(); else if (!state.archiveMode) clearSession();
  setFactsOpen(false); cancelTypewriter(); stopEffect("footsteps");
  if (state.eventSource) state.eventSource.close();
  window.clearTimeout(syncTimer); window.clearTimeout(recoveryTimer); recoveryTimer = null;
  syncAgain = false; syncNeedsRoute = false;
  state.stage = "home"; state.archiveMode = false;
  renderArchives(); refreshResumeControls(); showScreen("home");
}

async function beginNewGame() {
  if (readStored(SESSION_KEY, null) && !await endSavedGame()) return;
  showScreen("character-screen");
}

document.addEventListener?.("click", (event) => {
  const button = event.target?.closest?.("button");
  if (button && !button.disabled && !button.matches("[data-language]")) playEffect("button", true);
});

$("#new-game").addEventListener("click", beginNewGame);
$("#resume-game")?.addEventListener("click", restoreSession);
$("#end-game")?.addEventListener("click", endSavedGame);
$("#tutorial-open")?.addEventListener("click", () => {
  renderTutorial();
  showScreen("tutorial-screen");
  $("#tutorial-screen")?.scrollTo?.(0, 0);
  $(".tutorial-scroll")?.scrollTo?.(0, 0);
});
$("#tutorial-back")?.addEventListener("click", () => showScreen("home"));
$("#tutorial-start")?.addEventListener("click", beginNewGame);
$$('[data-language]').forEach((button) => button.addEventListener("click", () => setLanguage(button.dataset.language)));
$$('[data-go-home]').forEach((button) => button.addEventListener("click", goHome));
$("#facts-toggle").addEventListener("click", () => setFactsOpen(!$("#game-facts").classList.contains("is-open")));
$("#facts-close").addEventListener("click", () => setFactsOpen(false));
$("#facts-scrim").addEventListener("click", () => setFactsOpen(false));
$$('[data-console-tab]').forEach((button) => button.addEventListener("click", () => { state.consoleTab = button.dataset.consoleTab; renderFacts(); }));
document.addEventListener("keydown", (event) => { if (event.key === "Escape") setFactsOpen(false); });
setLanguage("en");
refreshResumeControls();
window.addEventListener("pagehide", saveSession);
restoreSession();
