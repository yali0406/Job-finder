// Admin only: the list of people who may sign in. Adding an email is the invite.
import { json, normEmail } from "../../_lib.js";

export async function onRequestGet({ env }) {
  const { results } = await env.DB.prepare(
    "SELECT email, name, role, created_at, last_login FROM users ORDER BY created_at"
  ).all();
  return json(results);
}

export async function onRequestPost({ request, env, data }) {
  const { email } = (await request.json().catch(() => ({}))) || {};
  const e = normEmail(email);
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(e)) return json({ error: "invalid email" }, 400);
  await env.DB.prepare("INSERT OR IGNORE INTO users (email, invited_by) VALUES (?, ?)").bind(e, data.user.email).run();
  return json({ invited: e });
}

export async function onRequestDelete({ request, env, data }) {
  const e = normEmail(new URL(request.url).searchParams.get("email"));
  if (!e || e === data.user.email) return json({ error: "cannot remove yourself" }, 400);
  await env.DB.batch([
    env.DB.prepare("DELETE FROM sessions WHERE email = ?").bind(e),
    env.DB.prepare("DELETE FROM marks WHERE email = ?").bind(e),
    env.DB.prepare("DELETE FROM users WHERE email = ?").bind(e),
  ]);
  return json({ removed: e });
}
