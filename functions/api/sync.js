// Sync of job marks between devices. A device sends its sync code in the X-Sync-Code header;
// devices with the same code share one set of marks. Only a hash of the code is stored.
const STATUSES = new Set(["saved", "applied", "hidden"]);
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json", "cache-control": "no-store" } });

async function space(request) {
  const code = (request.headers.get("x-sync-code") || "").trim().toUpperCase();
  if (!/^[A-Z0-9]{16,64}$/.test(code)) return null;
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("job-finder:" + code));
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, "0")).join("");
}

export async function onRequestGet({ request, env }) {
  const sp = await space(request);
  if (!sp) return json({ error: "bad sync code" }, 400);
  const { results } = await env.DB.prepare(
    "SELECT job_id, status, opened_at, updated_at FROM sync_marks WHERE space = ?").bind(sp).all();
  return json({ marks: results });
}

// Body: {updates: [{job_id, status: "saved"|"applied"|"hidden"|null, opened_at: ISO|null, updated_at: ISO}]}
// A row is replaced only by a change made later than the stored one.
export async function onRequestPost({ request, env }) {
  const sp = await space(request);
  if (!sp) return json({ error: "bad sync code" }, 400);
  const body = await request.json().catch(() => null);
  const updates = Array.isArray(body?.updates) ? body.updates.slice(0, 5000) : null;
  if (!updates) return json({ error: "expected {updates: [...]}" }, 400);
  const iso = (s) => typeof s === "string" && s.length <= 40 && !Number.isNaN(Date.parse(s));
  const stmts = [];
  for (const u of updates) {
    if (typeof u?.job_id !== "string" || !u.job_id || u.job_id.length > 64) continue;
    if (u.status != null && !STATUSES.has(u.status)) continue;
    if (u.opened_at != null && !iso(u.opened_at)) continue;
    if (!iso(u.updated_at)) continue;
    stmts.push(env.DB.prepare(
      `INSERT INTO sync_marks (space, job_id, status, opened_at, updated_at) VALUES (?1, ?2, ?3, ?4, ?5)
       ON CONFLICT(space, job_id) DO UPDATE SET status = excluded.status, opened_at = excluded.opened_at,
         updated_at = excluded.updated_at
       WHERE excluded.updated_at > sync_marks.updated_at`
    ).bind(sp, u.job_id, u.status ?? null, u.opened_at ?? null, u.updated_at));
  }
  for (let i = 0; i < stmts.length; i += 100) await env.DB.batch(stmts.slice(i, i + 100));
  return json({ saved: stmts.length });
}
