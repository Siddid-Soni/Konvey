import "./style.css";

type Run = {
  id: string; prompt: string; status: string; created: number; model: string;
  usd: number | null; title: string | null; video: string | null; error: string | null;
};
type Ev = { seq: number; t: number; type: string; [k: string]: any };
type StageId = "research" | "plan" | "scenes" | "render" | "done";
type StageState = "idle" | "active" | "done" | "warn" | "failed";
type StageRec = { state: StageState; at: number; end: number };
type Tone = "" | "good" | "warn" | "bad";
type Scene = {
  id: string; state: "waiting" | "writing" | "done" | "rejected"; beats: number; chars: number;
  attempts: number; examples: string[]; problems: string[]; render: string;
};
type Item = { t: number; text: string; tone: Tone; detail?: string };

const STAGES: { id: StageId; label: string }[] = [
  { id: "research", label: "Research" },
  { id: "plan", label: "Plan" },
  { id: "scenes", label: "Scenes" },
  { id: "render", label: "Render" },
  { id: "done", label: "Video" },
];
const SCENE_IDS = ["S1", "S2", "S3"];
const EXAMPLES = [
  "Why do we have leap years?",
  "Why is the sum of two odd numbers always even?",
  "How do the phases of the Moon happen?",
];

// ---------- helpers ---------------------------------------------------------

const $ = <T extends HTMLElement = HTMLElement>(id: string) =>
  (document.getElementById(id) as T | null) ?? (() => { throw new Error(`missing #${id}`) })();
const esc = (s: unknown) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
const clip = (s: unknown, n: number) => {
  const one = String(s ?? "").replace(/\s+/g, " ").trim();
  return one.length > n ? one.slice(0, n - 1) + "…" : one;
};
const tail = (s: string, n = 4000) => (s.length > n ? "…" + s.slice(-n) : s);
const fmtDur = (s: number) =>
  s < 60 ? `${Math.round(s)}s` : `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, "0")}s`;
const fmtT = (t: number) => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
const agoText = (unix: number) => {
  const s = Date.now() / 1000 - unix;
  if (s < 90) return "now";
  if (s < 3600) return `${Math.round(s / 60)}m`;
  if (s < 86400) return `${Math.round(s / 3600)}h`;
  return new Date(unix * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" });
};
const who = (agent: string) =>
  agent === "Agent 1" ? "Research" : agent === "Agent 2" ? "Plan" : /^S\d$/.test(agent) ? `Scene ${agent.slice(1)}` : agent;
const keyOf = (agent: string) => (agent === "Agent 2" ? "plan" : agent === "Agent 1" ? "research" : agent);
const pretty = (s: string) => {
  const n = Number(s);
  return s.trim() !== "" && Number.isFinite(n) ? n.toLocaleString(undefined, { maximumSignificantDigits: 8 }) : s;
};
// Why a run stopped, in words a viewer can act on. The raw error is kept for Checks.
const stopReason = (err: string) => {
  if (/ValidationError/.test(err)) return "a check rejected the plan after every try";
  if (/timed? ?out/i.test(err)) return "the model did not answer in time";
  return clip(err.replace(/^\w+(Error|Exception):\s*/, ""), 90);
};
// a delta redraws ~3x/s, so the headline is only re-matched when the text grew
const headlineOf = (id: string, html: string) => {
  const hit = S.heads.get(id);
  if (hit?.len === html.length) return hit.head;
  const h2 = html.match(/<h2[^>]*>([\s\S]*?)<\/h2>/);
  const vo = html.match(/vo="([^"]+)"/);
  const head = clip((h2?.[1] ?? vo?.[1] ?? "").replace(/<[^>]+>/g, " "), 120);
  S.heads.set(id, { len: html.length, head });
  return head;
};

const clamp = (n: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, n));

// ---------- layout (persisted) ---------------------------------------------

type Layout = { dock: "left" | "right"; side: number; details: number; detailsOpen: boolean };
const LAYOUT_KEY = "konvey.layout";
function loadLayout(): Layout {
  const base: Layout = { dock: "right", side: 240, details: 420, detailsOpen: true };
  try {
    const saved = JSON.parse(localStorage.getItem(LAYOUT_KEY) || "{}");
    return {
      dock: saved.dock === "left" ? "left" : "right",
      side: clamp(Number(saved.side) || base.side, 180, 380),
      details: clamp(Number(saved.details) || base.details, 260, 900),
      detailsOpen: saved.detailsOpen !== false,
    };
  } catch {
    return base;
  }
}
const layout: Layout = loadLayout();
function saveLayout() {
  try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch { /* private mode: layout just resets */ }
}
// The width the user chose is kept as it is; what is shown never takes the page's room
// (the page keeps at least 280px), so a width saved on a wide window fits a narrow one.
const shownDetails = () => clamp(layout.details, 260, Math.max(260, innerWidth - layout.side - 280));
function applyLayout() {
  const app = $("app");
  app.dataset.dock = layout.dock;
  app.style.setProperty("--side-w", `${layout.side}px`);
  app.style.setProperty("--details-w", `${shownDetails()}px`);
}

// ---------- state -----------------------------------------------------------

const blankScene = (id: string): Scene => ({
  id, state: "waiting", beats: 0, chars: 0, attempts: 1, examples: [], problems: [], render: "",
});

function freshState() {
  return {
    stages: Object.fromEntries(STAGES.map((s) => [s.id, { state: "idle", at: 0, end: 0 } as StageRec])) as Record<StageId, StageRec>,
    scenes: Object.fromEntries(SCENE_IDS.map((id) => [id, blankScene(id)])) as Record<string, Scene>,
    items: [] as Item[],
    texts: {} as Record<string, string>,
    events: [] as Ev[],               // every event but the text stream, for the full log
    logOpen: false,
    logView: "events" as "events" | "worker",
    logQuery: "",
    logWarnOnly: false,
    logOpenSeqs: new Set<number>(),   // which event rows the reader has expanded
    workerText: "",
    tries: {} as Record<string, number>,   // attempts allowed per agent, from agent.request
    heads: new Map<string, { len: number; head: string }>(),   // a scene's headline, per run
    pref: {} as Record<string, boolean>,   // a scene's stream: the user's choice, else open while writing
    usd: null as number | null,
    planTotal: 0,
    seconds: null as number | null,
    lastT: 0,
    video: null as string | null,
    title: "",
    error: "",
    model: "",
    showAll: false,
    tab: "summary",
  };
}

type State = ReturnType<typeof freshState> & {
  run: Run | null; es: EventSource | null; view: "compose" | "run";
};
const S: State = { ...freshState(), run: null, es: null, view: "compose" };
let runList: Run[] = [];
let frame = 0;

const scene = (id: string): Scene => (S.scenes[id] ??= blankScene(id));
const isOpen = (id: string) => S.pref[id] ?? scene(id).state === "writing";
const live = () => S.run?.status === "running";

function log(t: number, text: string, tone: Tone = "", detail?: string) {
  S.items.push({ t, text, tone, detail });
}
function start(id: StageId, t: number) {
  const c = S.stages[id];
  if (c.state === "idle") Object.assign(c, { state: "active", at: t });
}
function finish(id: StageId, t: number, state: StageState = "done") {
  const c = S.stages[id];
  if (c.state === "active" || c.state === "idle") Object.assign(c, { state, end: t });
}
function closeAll(t: number, state: "done" | "failed") {
  for (const id of ["research", "plan", "scenes", "render"] as StageId[]) {
    if (S.stages[id].state === "active") finish(id, t, state);
  }
  if (state === "done") Object.assign(S.stages.done, { state: "done", at: t, end: t });
}
function elapsed(): number {
  if (S.seconds != null) return S.seconds;
  if (live() && S.run) return Math.max(0, Date.now() / 1000 - S.run.created);
  return S.lastT;
}

// ---------- events -> state -------------------------------------------------

function apply(e: Ev) {
  const t = e.t as number;
  switch (e.type) {
    case "run.start":
      S.model = e.model || S.model;
      start("research", t);
      log(t, "Started");
      break;

    case "agent.request":
      S.tries[e.agent] = e.of;
      if (e.agent === "Agent 1") {
        start("research", t);
        if (e.attempt === 1) log(t, "Researching the topic");
      } else if (e.agent === "Agent 2") {
        start("plan", t);
        S.texts.plan = "";
        if (e.attempt === 1) log(t, "Planning the three scenes");
      } else if (SCENE_IDS.includes(e.agent)) {
        const sc = scene(e.agent);
        sc.attempts = e.attempt;
        sc.chars = 0;
        S.texts[e.agent] = "";
      }
      break;

    case "agent.delta": {
      const key = keyOf(e.agent);
      S.texts[key] = (S.texts[key] ?? "") + (e.text ?? "");
      if (SCENE_IDS.includes(key)) {
        const sc = scene(key);
        sc.chars = S.texts[key].length;
        if (sc.state === "waiting") sc.state = "writing";
      }
      break;
    }

    case "agent.done":
      if (e.agent === "Agent 1") {
        finish("research", t);
        log(t, `Research done · ${clip(e.topic, 90)}`, "good", `${e.concepts} key concepts · ${e.examples} worked examples`);
      }
      break;

    case "agent.rejected": {
      const last = e.attempt >= (S.tries[e.agent] ?? Infinity);
      log(t, last ? `${who(e.agent)} still doesn't pass the checks` : `${who(e.agent)} didn't pass the checks · trying again`,
        "warn", (e.problems ?? []).join("\n"));
      break;
    }

    case "tool.call": {
      const res = String(e.result ?? "");
      if (e.name === "calc") log(t, `Computed ${clip(e.input, 60)} = ${clip(pretty(res), 30)}`);
      else if (/ERROR|REJECTED/.test(res)) log(t, "A script step failed", "warn", res);
      break;
    }

    case "plan.ready":
      finish("plan", t);
      start("scenes", t);
      S.title = e.title || S.title;
      S.planTotal = e.total ?? 0;
      for (const s of e.scenes ?? []) scene(s.id).beats = s.beats ?? scene(s.id).beats;
      log(t, `Plan ready · ${clip(e.title, 80)}`, "good", `${e.scenes?.length ?? 0} scenes · ${e.total}s`);
      break;

    case "scene.state": {
      const id = e.scene as string;
      const sc = scene(id);
      start("scenes", t);
      if (e.state === "writing") {
        sc.state = "writing";
        sc.examples = e.examples ?? [];
        log(t, `${who(id)} started${sc.examples.length ? ` · ${sc.examples.join(", ")}` : ""}`);
      } else if (e.state === "done") {
        sc.state = "done";
        sc.beats = e.beats ?? sc.beats;
        sc.problems = [];
        log(t, `${who(id)} written · ${sc.beats} beats`, "good");
      } else if (e.state === "rejected") {
        sc.state = "rejected";
        sc.problems = e.problems ?? [];
        log(t, `${who(id)} needs a look`, "bad", sc.problems.join("\n"));
      }
      break;
    }

    case "run.scenes_done": {
      finish("scenes", t);
      const bad: string[] = e.rejected ?? [];
      log(t, bad.length ? `${bad.join(", ")} need a look` : "All three scenes written", bad.length ? "warn" : "good");
      break;
    }

    case "render.start":
      start("render", t);
      log(t, `Rendering ${(e.scenes ?? []).length} scenes`);
      break;

    case "render.scene": {
      const sc = scene(e.scene);
      sc.render = e.state === "done" ? "done" : e.state === "failed" ? "failed" : "rendering";
      if (e.state === "failed") log(t, `${who(e.scene)} did not render`, "bad", e.error);
      break;
    }

    case "render.done":
      finish("render", t);
      S.video = `/api/runs/${S.run!.id}/files/${e.video}`;
      log(t, "Video ready", "good");
      break;

    case "render.skipped":
      finish("render", t, "warn");
      log(t, `Render skipped · ${clip(e.reason, 100)}`, "warn", e.reason);
      break;

    case "cost.updated":
      S.usd = e.usd ?? S.usd;
      break;

    case "run.finished":
      closeAll(t, "done");
      S.seconds = e.seconds ?? t;
      S.usd = e.usd ?? S.usd;
      S.run!.status = "finished";
      log(t, `Finished in ${fmtDur(e.seconds ?? t)}`, "good");
      break;

    case "run.failed":
      closeAll(t, "failed");
      S.error = e.error ?? "";
      S.run!.status = "failed";
      log(t, `Stopped · ${stopReason(S.error)}`, "bad", S.error);
      break;

    // the user's own stop: the stages close, the head reads "Stopped by you", and the
    // server ends the stream right after this event
    case "run.cancelled":
      closeAll(t, "failed");
      S.run!.status = "cancelled";
      log(t, "Stopped");
      break;
  }
}

// ---------- drawing ---------------------------------------------------------

function schedule() {
  if (!frame) frame = requestAnimationFrame(draw);
}

function draw() {
  frame = 0;
  $("compose").hidden = S.view !== "compose";
  $("run").hidden = S.view !== "run";
  if (S.view === "run" && S.run) {
    drawHead();
    drawStages();
    drawVideo();
    drawScenes();
    drawItems();
  }
  drawDrawer();
  drawRuns();
  drawLogs();
}

// ---------- full log --------------------------------------------------------

const fieldsOf = (e: Ev) =>
  Object.entries(e)
    .filter(([k]) => !["seq", "t", "type"].includes(k))
    .map(([k, v]) => `${k}=${Array.isArray(v) ? v.join(" | ") : typeof v === "string" ? v : JSON.stringify(v)}`)
    .join("  ");

function levelOf(e: Ev): "bad" | "warn" | "" {
  if (e.type === "run.failed" || (e.type === "render.scene" && e.state === "failed")
      || (e.type === "scene.state" && e.state === "rejected")) return "bad";
  if (e.type === "agent.rejected" || e.type === "render.skipped"
      || (e.type === "tool.call" && /ERROR|REJECTED/.test(String(e.result ?? "")))) return "warn";
  return "";
}

let logsSig = "";

function drawLogs() {
  $("logs").hidden = !S.logOpen;
  if (!S.logOpen) return;
  document.querySelectorAll<HTMLElement>("[data-logtab]").forEach((b) => {
    const on = b.dataset.logtab === S.logView;
    b.classList.toggle("on", on);
    b.setAttribute("aria-selected", String(on));
  });
  // the drawer is redrawn ~3x/s while text streams in; only rebuild the rows when they changed
  const sig = [S.logView, S.logQuery, S.logWarnOnly, S.events.length, S.workerText.length,
               S.logOpenSeqs.size].join("|");
  if (sig === logsSig) return;
  logsSig = sig;
  const q = S.logQuery.trim().toLowerCase();
  const body = $("logs-body");
  const keep = body.scrollTop;
  if (S.logView === "events") {
    const rows = S.events.filter((e) =>
      (!S.logWarnOnly || levelOf(e)) && (!q || `${e.type} ${e.agent ?? ""} ${e.scene ?? ""} ${fieldsOf(e)}`.toLowerCase().includes(q)));
    $("logs-count").textContent = `${rows.length} of ${S.events.length} events`;
    body.innerHTML = rows.length
      ? rows.map((e) => `<details class="log ${levelOf(e)}" data-seq="${e.seq}" ${S.logOpenSeqs.has(e.seq) ? "open" : ""}>
          <summary><span class="t mono">${fmtT(e.t)}</span><span class="k mono">${esc(e.type)}</span><span class="m">${esc(fieldsOf(e))}</span></summary>
          <pre class="raw mono">${esc(JSON.stringify(e, null, 2))}</pre>
        </details>`).join("")
      : `<p class="quiet pad">No events match.</p>`;
  } else {
    const lines = S.workerText.split("\n");
    const shown = lines.filter((l) =>
      (!S.logWarnOnly || /error|warn|traceback|rejected|failed/i.test(l)) && (!q || l.toLowerCase().includes(q)));
    $("logs-count").textContent = `${shown.length} of ${lines.length} lines`;
    body.innerHTML = `<pre class="raw mono worker">${esc(shown.join("\n")) || "Nothing matches."}</pre>`;
  }
  body.scrollTop = keep;
}

async function loadWorker() {
  const runId = S.run?.id;
  if (!runId) return;
  try {
    const r = await fetch(`/api/runs/${runId}/log`);
    if (r.ok && S.run?.id === runId) {
      S.workerText = await r.text();
      drawLogs();
    }
  } catch { /* keep the last text */ }
}

const TABS: [string, string][] = [
  ["summary", "Summary"], ["research", "Research"], ["plan", "Plan"],
  ["S1", "Scene 1"], ["S2", "Scene 2"], ["S3", "Scene 3"], ["checks", "Checks"],
];
const FILES: Record<string, string> = {
  research: "agent1-output.json", plan: "agent2-output.json",
  S1: "agent3-S1.html", S2: "agent3-S2.html", S3: "agent3-S3.html",
};

function statusLine(r: Run): { text: string; tone: string } {
  if (r.status === "failed") return { text: `Stopped · ${stopReason(S.error || r.error || "")}`, tone: "bad" };
  if (r.status === "cancelled") return { text: "Stopped by you", tone: "" };
  if (r.status === "finished") return { text: S.video ? "Video ready" : "Finished without a video", tone: "good" };
  const cur = STAGES.find((s) => S.stages[s.id].state === "active")?.id ?? "";
  const done = SCENE_IDS.filter((id) => scene(id).state === "done").length;
  const labels: Record<string, string> = {
    research: "Researching the topic",
    plan: "Planning the scenes",
    scenes: `Writing the scenes · ${done} of 3 done`,
    render: "Rendering the video",
    done: "Finishing",
  };
  return { text: labels[cur] ?? "Starting", tone: "running" };
}

function drawHead() {
  const r = S.run!;
  const { text, tone } = statusLine(r);
  $("title").textContent = S.title || r.title || r.prompt;
  const st = $("status");
  st.textContent = text;
  st.className = `status ${tone}`;
  const again = r.status === "failed" || r.status === "cancelled"
    ? `<button class="btn primary-ghost" type="button" data-act="again">Try again</button>` : "";
  const stop = live() ? `<button class="btn" type="button" data-act="stop">Stop</button>` : "";
  const show = layout.detailsOpen ? "" : `<button class="btn" type="button" data-act="details-show">Show details</button>`;
  $("actions").innerHTML = `${again}${stop}${show}`;
  drawMeta();
}

function drawMeta() {
  const r = S.run;
  if (!r || S.view !== "run") return;
  const parts = [fmtDur(elapsed())];
  if (S.usd != null) parts.push(`$${S.usd.toFixed(4)}`);
  const model = r.model || S.model;
  if (model) parts.push(model);
  $("meta").textContent = parts.join(" · ");
}

function drawStages() {
  const finished = S.run?.status === "finished";
  $("stages").innerHTML = STAGES.map((s) => {
    const c = S.stages[s.id];
    let state: string = c.state;
    if (s.id === "render" && c.state === "idle" && finished) state = "skipped";
    if (c.state === "warn") state = "skipped";
    let note = "";
    if (state === "active") note = fmtDur(Math.max(0, elapsed() - c.at));
    else if (state === "done" && c.end > c.at && c.at > 0) note = fmtDur(c.end - c.at);
    else if (state === "skipped") note = "skipped";
    else if (state === "failed") note = "stopped";
    return `<li class="stage ${state}"><i class="dot"></i><span class="name">${s.label}</span><span class="time mono">${note}</span></li>`;
  }).join("");
}

function drawVideo() {
  const box = $("video");
  if (!S.video) {
    box.hidden = true;
    if (box.dataset.src) { box.innerHTML = ""; box.dataset.src = ""; }
    return;
  }
  box.hidden = false;
  if (box.dataset.src !== S.video) {
    box.dataset.src = S.video;
    box.innerHTML = `<video src="${esc(S.video)}" controls playsinline preload="metadata" aria-label="Finished video"></video>`;
  }
}

function sceneState(sc: Scene): string {
  const retry = sc.attempts > 1 ? ` · retry ${sc.attempts - 1}` : "";
  switch (sc.state) {
    case "waiting": return live() ? "Waiting" : "Not started";
    case "writing": return `Writing · ${(sc.chars / 1000).toFixed(1)}k${retry}`;
    case "rejected": return "Needs a look";
    default: {
      const render = sc.render === "rendering" ? "rendering" : sc.render === "done" ? "rendered" : sc.render === "failed" ? "render failed" : "";
      return [`${sc.beats} beats`, render].filter(Boolean).join(" · ");
    }
  }
}

function drawScenes() {
  const box = $("scenes");
  // keep each open stream where the reader left it; follow the text when they were at the bottom
  const keep = new Map<string, { top: number; bottom: boolean }>();
  box.querySelectorAll<HTMLElement>("[data-stream]").forEach((el) =>
    keep.set(el.dataset.stream!, { top: el.scrollTop, bottom: el.scrollHeight - el.scrollTop - el.clientHeight < 24 }));
  box.innerHTML = SCENE_IDS.map((id, i) => {
    const sc = scene(id);
    const open = isOpen(id);
    const head = headlineOf(id, S.texts[id] ?? "")
      || (sc.state === "waiting" ? (live() ? "Waiting for the plan" : "Not started") : "");
    const stream = open
      ? `<pre class="stream mono" data-stream="${id}">${esc(tail(S.texts[id] ?? "")) || "Waiting for the first words…"}</pre>`
      : "";
    return `<li class="scene ${sc.state}">
      <button class="row" type="button" data-scene="${id}" aria-expanded="${open}">
        <span class="idx mono">${i + 1}</span>
        <span class="txt"><span class="name">Scene ${i + 1}</span><span class="line">${esc(head)}</span></span>
        <span class="st mono">${sceneState(sc)}</span>
        <span class="bar" aria-hidden="true"></span>
      </button>${stream}
    </li>`;
  }).join("");
  box.querySelectorAll<HTMLElement>("[data-stream]").forEach((el) => {
    const k = keep.get(el.dataset.stream!);
    if (k) el.scrollTop = k.bottom ? el.scrollHeight : k.top;
  });
}

function drawItems() {
  const all = S.items;
  const shown = S.showAll ? all : all.slice(-6);
  const rows = shown.map((i) => {
    const firstLine = i.detail?.split("\n").find((l) => l.trim() && !l.trim().endsWith(":")) ?? "";
    return `<li class="item ${i.tone}"><span class="t mono">${fmtT(i.t)}</span>
      <span class="tx">${esc(i.text)}${firstLine ? `<small>${esc(clip(firstLine, 150))}</small>` : ""}</span></li>`;
  }).join("");
  const more = all.length > 6
    ? `<li class="more"><button class="link" type="button" data-act="more">${S.showAll ? "Show less" : `Show all ${all.length}`}</button></li>`
    : "";
  $("items").innerHTML = rows + more;
}

let lastTab = "";
function drawDrawer() {
  const show = S.view === "run" && !!S.run && layout.detailsOpen;
  $("drawer").hidden = !show;
  if (!show) return;
  $("tabs").innerHTML = TABS.map(([id, label]) =>
    `<button class="tab ${id === S.tab ? "on" : ""}" type="button" data-tab="${id}" aria-selected="${id === S.tab}">${label}</button>`).join("");
  const body = $("drawer-body");
  const keep = body.scrollTop;
  body.innerHTML = S.tab === "summary"
    ? summaryHtml()
    : `<pre class="raw mono">${esc(rawText())}</pre>`;
  body.scrollTop = S.tab === lastTab ? keep : 0;
  lastTab = S.tab;
}

function rawText(): string {
  if (S.tab === "checks") {
    return S.items.filter((i) => i.detail).map((i) => `${fmtT(i.t)}  ${i.text}\n${i.detail}`).join("\n\n")
      || "No checks have failed in this run.";
  }
  return S.texts[S.tab] || "Not available yet.";
}

function summaryHtml(): string {
  const r = S.run!;
  const kv = (k: string, v: string) => `<div class="kv"><dt>${esc(k)}</dt><dd class="mono">${esc(v)}</dd></div>`;
  const flagged = S.items.filter((i) => i.tone === "warn" || i.tone === "bad").length;
  const stages = STAGES.filter((s) => s.id !== "done").map((s) => {
    const c = S.stages[s.id];
    const v = c.state === "active" ? "now"
      : c.end > c.at && c.at > 0 ? fmtDur(c.end - c.at)
      : c.state === "failed" ? "stopped"
      : c.state === "warn" || (s.id === "render" && r.status === "finished") ? "skipped" : "—";
    return kv(s.label, v);
  }).join("");
  const scenes = SCENE_IDS.map((id, i) => {
    const sc = scene(id);
    const notes = [sc.examples.length ? sc.examples.join(", ") : "no examples", sc.attempts > 1 ? `${sc.attempts - 1} rewrite${sc.attempts > 2 ? "s" : ""}` : ""]
      .filter(Boolean).join(" · ");
    return `<li><span>Scene ${i + 1}</span><span class="mono">${esc(sceneState(sc))}</span><small>${esc(notes)}</small></li>`;
  }).join("");
  return `<section class="sum">
    <h2>Run</h2>
    <dl>${kv("Model", r.model || S.model || "—")}${kv("Cost", S.usd != null ? `$${S.usd.toFixed(4)}` : "—")}
      ${kv("Elapsed", fmtDur(elapsed()))}${kv("Planned length", S.planTotal ? `${S.planTotal}s` : "—")}
      ${kv("Checks that flagged something", String(flagged))}</dl>
    <h2>Stages</h2>
    <dl>${stages}</dl>
    <h2>Scenes</h2>
    <ul class="plain">${scenes}</ul>
    <p class="quiet">The raw model output and every check are in the tabs above.</p>
  </section>`;
}

let runsSig = "";
function drawRuns() {
  // rebuilt on every frame while a run streams; the minute bucket keeps the "when" labels fresh
  const sig = `${S.run?.id ?? ""}|${Math.floor(Date.now() / 60000)}|`
    + runList.map((r) => `${r.id},${r.status},${r.title ?? ""}`).join("|");
  if (sig === runsSig) return;
  runsSig = sig;
  const row = (r: Run) => `<li><button class="run ${S.run?.id === r.id ? "on" : ""}" type="button" data-id="${r.id}">
      <i class="dot ${r.status}"></i><span class="ttl">${esc(r.title || r.prompt)}</span><span class="when">${agoText(r.created)}</span>
    </button></li>`;
  const group = (label: string, list: Run[]) =>
    list.length ? `<h3>${label}</h3><ul>${list.map(row).join("")}</ul>` : "";
  const running = runList.filter((r) => r.status === "running");
  const earlier = runList.filter((r) => r.status !== "running");
  $("runs").innerHTML = (group("Running", running) + group("Earlier", earlier))
    || `<p class="quiet pad">Your videos will show up here.</p>`;
}

// ---------- data ------------------------------------------------------------

async function refreshRuns() {
  try {
    runList = await (await fetch("/api/runs")).json();
  } catch { return; }
  const fresh = S.run && runList.find((r) => r.id === S.run!.id);
  if (S.run && fresh && fresh.status !== S.run.status) {
    S.run.status = fresh.status;
    if (fresh.video && !S.video) S.video = fresh.video;
  }
  schedule();
}

function closeStream() {
  S.es?.close();
  S.es = null;
}

function attach(run: Run) {
  closeStream();
  Object.assign(S, freshState(), { run, view: "run" });
  S.model = run.model;
  S.usd = run.usd;
  S.video = run.video;
  const es = new EventSource(`/api/runs/${run.id}/events`);
  S.es = es;
  es.onmessage = (m) => {
    const e: Ev = JSON.parse(m.data);
    if (e.t > S.lastT) S.lastT = e.t;
    if (e.type !== "agent.delta") S.events.push(e);
    apply(e);
    schedule();
  };
  es.addEventListener("end", () => { es.close(); S.es = null; schedule(); });
  schedule();
}

function newRun() {
  closeStream();
  Object.assign(S, freshState(), { run: null, view: "compose" });
  schedule();
}

async function route() {
  const id = location.hash.match(/^#\/runs\/([\w-]+)$/)?.[1];
  if (!id) { newRun(); return; }
  if (S.run?.id === id) return;
  const r = await fetch(`/api/runs/${id}`);
  if (location.hash !== `#/runs/${id}`) return;   // a later navigation won
  if (!r.ok) { newRun(); return; }
  attach(await r.json());
}

async function start_(prompt: string): Promise<void> {
  const go = $<HTMLButtonElement>("go");
  const err = $("err");
  go.disabled = true;
  err.hidden = true;
  try {
    const r = await fetch("/api/runs", {
      method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ prompt }),
    });
    if (!r.ok) throw new Error(await r.text());
    const run: Run = await r.json();
    location.hash = `#/runs/${run.id}`;
    refreshRuns();
  } catch (e) {
    err.textContent = `Could not start the video · ${clip(e, 160)}`;
    err.hidden = false;
  } finally {
    go.disabled = false;
  }
}

async function openTab(id: string) {
  S.tab = id;
  draw();
  const file = FILES[id];
  const runId = S.run?.id;
  if (!file || !runId) return;
  try {
    const r = await fetch(`/api/runs/${runId}/files/${file}`);
    if (r.ok && S.run?.id === runId && S.tab === id) {
      S.texts[id] = await r.text();
      draw();
    }
  } catch { /* keep whatever streamed in */ }
}

async function stop() {
  if (!S.run) return;
  try {
    const r = await fetch(`/api/runs/${S.run.id}/cancel`, { method: "POST" });
    if (!r.ok) throw new Error(await r.text());
  } catch (e) {
    // the stream stays as it is: the run may still be going
    log(elapsed(), `Could not stop · ${clip(e, 120)}`, "bad");
    schedule();
  }
}

// ---------- drag: resize the sidebars, dock the details panel ---------------

type Drag = { kind: "side" | "details" | "move"; x0: number; moved: boolean; target: "left" | "right" | null };
let drag: Drag | null = null;

function showHint(side: "left" | "right" | null) {
  const h = $("dock-hint");
  h.hidden = !side;
  if (side) h.dataset.side = side;
}

function startDrag(kind: Drag["kind"], e: PointerEvent) {
  drag = { kind, x0: e.clientX, moved: false, target: null };
  window.addEventListener("pointermove", onDrag);
  window.addEventListener("pointerup", endDrag, { once: true });
  document.body.classList.add("dragging");
  e.preventDefault();
}

function onDrag(e: PointerEvent) {
  if (!drag) return;
  if (drag.kind === "move") {
    if (Math.abs(e.clientX - drag.x0) > 6) drag.moved = true;
    if (drag.moved) {
      drag.target = e.clientX < innerWidth / 2 ? "left" : "right";
      showHint(drag.target);
    }
    return;
  }
  if (drag.kind === "side") {
    layout.side = clamp(e.clientX - $("side").getBoundingClientRect().left, 180, 380);
  } else {
    const r = $("drawer").getBoundingClientRect();
    layout.details = layout.dock === "right" ? r.right - e.clientX : e.clientX - r.left;
  }
  applyLayout();
}

function endDrag() {
  window.removeEventListener("pointermove", onDrag);
  document.body.classList.remove("dragging");
  if (drag?.kind === "move" && drag.moved && drag.target) {
    layout.dock = drag.target;
    applyLayout();
  }
  drag = null;
  showHint(null);
  saveLayout();
}

// ---------- wiring ----------------------------------------------------------

function onClick(ev: MouseEvent) {
  const el = (ev.target as HTMLElement).closest<HTMLElement>("[data-act],[data-id],[data-scene],[data-tab],[data-example],[data-logtab]");
  if (!el) return;
  if (el.dataset.logtab) {
    S.logView = el.dataset.logtab as "events" | "worker";
    draw();
    if (S.logView === "worker") loadWorker();
    return;
  }
  if (el.dataset.id) { location.hash = `#/runs/${el.dataset.id}`; return; }
  if (el.dataset.scene) { const id = el.dataset.scene; S.pref[id] = !isOpen(id); draw(); return; }
  if (el.dataset.tab) { openTab(el.dataset.tab); return; }
  if (el.dataset.example) {
    $<HTMLTextAreaElement>("prompt").value = el.dataset.example;
    $("prompt").focus();
    return;
  }
  switch (el.dataset.act) {
    case "new":
      if (location.hash) location.hash = ""; else newRun();
      break;
    case "logs-open":
      S.logOpen = true;
      draw();
      if (S.logView === "worker") loadWorker();
      break;
    case "logs-close":
      S.logOpen = false;
      draw();
      break;
    case "details-show":
      layout.detailsOpen = true;
      saveLayout();
      draw();
      break;
    case "details-hide":
      layout.detailsOpen = false;
      saveLayout();
      draw();
      break;
    case "stop": stop(); break;
    case "more": S.showAll = !S.showAll; draw(); break;
    case "again":
      if (S.run) start_(S.run.prompt);
      break;
  }
}

function boot() {
  applyLayout();
  window.addEventListener("resize", applyLayout);
  $("examples").innerHTML = EXAMPLES.map((e) =>
    `<button class="chip" type="button" data-example="${esc(e)}">${esc(e)}</button>`).join("");
  document.addEventListener("click", onClick);
  $("ask").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const prompt = $<HTMLTextAreaElement>("prompt").value.trim();
    if (prompt) start_(prompt);
  });
  $("prompt").addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" && (ev.metaKey || ev.ctrlKey)) $<HTMLFormElement>("ask").requestSubmit();
  });
  document.addEventListener("pointerdown", (ev) => {
    const el = (ev.target as HTMLElement).closest<HTMLElement>("[data-resize],[data-move]");
    if (!el || ev.button !== 0) return;
    startDrag(el.dataset.resize ? (el.dataset.resize as "side" | "details") : "move", ev);
  });
  $("logs-q").addEventListener("input", (ev) => { S.logQuery = (ev.target as HTMLInputElement).value; drawLogs(); });
  $("logs-warn").addEventListener("change", (ev) => { S.logWarnOnly = (ev.target as HTMLInputElement).checked; drawLogs(); });
  $("logs-body").addEventListener("toggle", (ev) => {
    const d = ev.target as HTMLDetailsElement;
    const seq = Number(d.dataset.seq);
    if (!seq) return;
    if (d.open) S.logOpenSeqs.add(seq); else S.logOpenSeqs.delete(seq);
  }, true);
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && S.logOpen) { S.logOpen = false; draw(); return; }
    // keyboard: the same handles, 16px a step
    const el = (ev.target as HTMLElement).closest<HTMLElement>("[data-resize]");
    if (!el || (ev.key !== "ArrowLeft" && ev.key !== "ArrowRight")) return;
    ev.preventDefault();
    const dir = ev.key === "ArrowRight" ? 1 : -1;
    if (el.dataset.resize === "side") layout.side = clamp(layout.side + dir * 16, 180, 380);
    else layout.details = shownDetails() + dir * 16 * (layout.dock === "right" ? -1 : 1);
    applyLayout();
    saveLayout();
  });
  window.addEventListener("hashchange", route);
  setInterval(() => { if (S.view === "run" && S.run) { drawMeta(); if (live()) drawStages(); } }, 1000);
  setInterval(refreshRuns, 4000);
  setInterval(() => { if (S.logOpen && S.logView === "worker" && live()) loadWorker(); }, 2000);
  refreshRuns().then(route);
}

boot();
