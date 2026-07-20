/**
 * CoolDecide's own trigger worker — fully standalone.
 *
 * (This replaces the old shared "nyxtold-trigger" worker, which lived in the
 * youtube-shorts-bot repo and also woke the story bots. Those channels are shut
 * down; CoolDecide now carries its own alarm clock so nothing depends on a dead
 * repo.)
 *
 * Jobs:
 *  1. scheduled(): every 5 minutes (Cloudflare cron — effectively free, unlike
 *     GitHub Actions minutes) it reads the bot's committed schedule
 *     (dashboard/kids.json -> schedule.upcoming) and, on the first tick after a
 *     slot time passes, fires a `post-now` repository_dispatch. The GitHub run
 *     builds and uploads born-public the moment the build finishes (slot + build
 *     time — still a random minute, since the slot is random and builds vary),
 *     with ZERO held minutes — instead of waking hourly and sleeping to the slot
 *     (which burned ~5x the free tier).
 *  2. fetch(): /pause and /resume endpoints for the dashboard's pause buttons —
 *     they commit dashboard/controls.json in THIS repo, which
 *     scheduler.should_post() reads and obeys. /wake fires an upkeep poke
 *     (cron-tick) on demand; /health for reachability checks.
 *
 * Secrets (set in Cloudflare, never in code):
 *   GH_TOKEN     — GitHub token with Contents read/write on vonsidy/cooldecide-bot
 *                  (read the schedule, write controls.json, send dispatches).
 *   PAUSE_SECRET — optional; shared with the dashboard so /pause isn't wide open.
 */

const REPO = "vonsidy/cooldecide-bot";
const DASH = "dashboard/kids.json";       // where schedule.upcoming lives
const CONTROLS = "dashboard/controls.json";
const BOT_ID = "kids";                    // controls.json key scheduler checks
const ALLOW_ORIGIN = "*";                 // pause is gated by PAUSE_SECRET, not origin

// Fire post-now on the first tick AT/AFTER the slot time (owner's call: exact-minute
// uploads don't matter — random + insta-public does, and the slot itself is random).
// Firing after the slot means run.py's hold is zero: the bot builds and uploads the
// moment it's done, so every billed minute is real work. The upload lands at
// slot + build time (~7-12 min), which still varies day to day. The window is one
// cron-tick wide (5 min) so each slot fires exactly once; a rare double-fire is
// harmless — the second run finds the quota met (YouTube-verified) and exits cheap.
const SLOT_PAST_MAX = 5;  // fire when the slot passed less than this many min ago

function gh(env) {
  return {
    Authorization: `Bearer ${env.GH_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "cooldecide-trigger",
    "Content-Type": "application/json",
  };
}

function cors() {
  return {
    "Access-Control-Allow-Origin": ALLOW_ORIGIN,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, X-Pause-Secret",
    "Access-Control-Max-Age": "86400",
  };
}

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors(), "Content-Type": "application/json" },
  });
}

async function dispatch(env, eventType) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/dispatches`, {
    method: "POST",
    headers: gh(env),
    body: JSON.stringify({ event_type: eventType }),
  });
  // 204 = accepted. 404 = the token can't see the repo (GitHub hides private
  // repos from under-scoped tokens rather than returning 403).
  const body = r.status === 204 ? "" : (await r.text()).slice(0, 160);
  console.log(`dispatch ${eventType}:`, r.status, body);
  return r.status;
}

// The bot's committed upcoming slot times (ISO strings) as Date[].
async function getUpcoming(env) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${DASH}`, {
    headers: gh(env),
  });
  if (!r.ok) throw new Error(`get ${DASH} ${r.status}`);
  const data = await r.json();
  const j = JSON.parse(atob(String(data.content).replace(/\n/g, "")));
  const up = (j.schedule && j.schedule.upcoming) || [];
  return up.map((s) => new Date(s)).filter((d) => !isNaN(d.getTime()));
}

async function fireIfDue(env, now) {
  try {
    const upcoming = await getUpcoming(env);
    const due = upcoming.some((t) => {
      const min = (t.getTime() - now.getTime()) / 60000;   // negative = slot passed
      return min <= 0 && min > -SLOT_PAST_MAX;
    });
    if (due) await dispatch(env, "post-now");
  } catch (e) {
    console.log("slot check FAILED:", String(e));
  }
}

async function getControls(env) {
  const r = await fetch(`https://api.github.com/repos/${REPO}/contents/${CONTROLS}`, {
    headers: gh(env),
  });
  if (!r.ok) throw new Error(`get controls ${r.status}`);
  const data = await r.json();
  const decoded = atob(String(data.content).replace(/\n/g, ""));
  return { sha: data.sha, ctl: JSON.parse(decoded) };
}

async function setPause(env, days) {
  const { sha, ctl } = await getControls(env);
  const until = days == null
    ? null
    : new Date(Date.now() + days * 86400000).toISOString();
  ctl[BOT_ID] = { paused_until: until };
  const put = await fetch(`https://api.github.com/repos/${REPO}/contents/${CONTROLS}`, {
    method: "PUT",
    headers: gh(env),
    body: JSON.stringify({
      message: `${days == null ? "resume" : "pause"} ${BOT_ID} via dashboard`,
      content: btoa(JSON.stringify(ctl, null, 2) + "\n"),
      sha,
    }),
  });
  if (!put.ok) throw new Error(`put controls ${put.status} ${await put.text()}`);
  return until;
}

export default {
  async scheduled(event, env, ctx) {
    await fireIfDue(env, new Date());
  },

  async fetch(request, env) {
    if (request.method === "OPTIONS") return new Response(null, { headers: cors() });

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (path === "/" || path === "/health") return json({ ok: true, repo: REPO });

    // Manual upkeep poke — also proves THIS worker's token reaches the repo.
    if (path === "/wake") {
      const status = await dispatch(env, "cron-tick");
      return json({ ok: status === 204, status });
    }

    if (path !== "/pause" && path !== "/resume") return json({ error: "not found" }, 404);
    if (request.method !== "POST") return json({ error: "use POST" }, 405);

    if (env.PAUSE_SECRET) {
      const given = request.headers.get("X-Pause-Secret") || url.searchParams.get("s");
      if (given !== env.PAUSE_SECRET) return json({ error: "unauthorized" }, 401);
    }

    let body = {};
    try { body = await request.json(); } catch (_) { /* allow query params */ }
    const days = Number(body.days || url.searchParams.get("days") || 1);

    try {
      const until = await setPause(env, path === "/resume" ? null : days);
      return json({ ok: true, bot: BOT_ID, paused_until: until });
    } catch (e) {
      return json({ error: String((e && e.message) || e) }, 500);
    }
  },
};
