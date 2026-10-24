// The signed-in user's marks on jobs: status (saved / applied / hidden) and when they opened the job link.
import { json } from "../_lib.js";

const STATUSES = new Set(["saved", "applied", "hidden"]);

export async function onRequestGet({ env, data }) {
  const { results } = await env.DB.prepare("SELECT job_id, status, opened_at FROM marks WHERE email = ?")
    .bind(data.user.email).all();
  const out = {};
  for (const r of results) out[r.job_id] = { status: r.status, opened_at: r.opened_at };
  return json(out);
}

// Body: {updates: [{job_id, status?: "saved"|"applied"|"hidden"|null, opened_at?: ISO string|null}]}
// A field left out keeps its stored value.
export async function onRequestPost({ request, env, data }) {
  const body = await request.json().catch(() => null);
  const updates = Array.isArray(body?.updates) ? body.updates.slice(0, 2000) : null;
  if (!updates) return json({ error: "expected {updates: [...]}" }, 400);

  const stmts = [];
  for (const u of updates) {
    if (typeof u?.job_id !== "string" || !u.job_id || u.job_id.length > 64) continue;
    const hasStatus = "status" in u, hasOpened = "opened_at" in u;
    if (hasStatus && u.status !== null && !STATUSES.has(u.status)) continue;
    if (!hasStatus && !hasOpened) continue;
    stmts.push(env.DB.prepare(
      `INSERT INTO marks (email, job_id, status, opened_at) VALUES (?1, ?2, ?3, ?4)
       ON CONFLICT(email, job_id) DO UPDATE SET
         status = CASE WHEN ?5 THEN ?3 ELSE marks.status END,
         opened_at = CASE WHEN ?6 THEN ?4 ELSE marks.opened_at END,
         updated_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')`
    ).bind(data.user.email, u.job_id, hasStatus ? u.status : null, hasOpened ? u.opened_at : null,
           hasStatus ? 1 : 0, hasOpened ? 1 : 0));
  }
  if (stmts.length) await env.DB.batch(stmts);
  return json({ saved: stmts.length });
}
