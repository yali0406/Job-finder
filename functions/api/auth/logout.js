import { SESSION_COOKIE, cookie, setCookie } from "../../_lib.js";

export async function onRequestPost({ request, env }) {
  const token = cookie(request, SESSION_COOKIE);
  if (token) await env.DB.prepare("DELETE FROM sessions WHERE token = ?").bind(token).run();
  return new Response(null, { status: 204, headers: { "Set-Cookie": setCookie(SESSION_COOKIE, "", 0) } });
}
