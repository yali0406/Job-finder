// Google sends the user back here with a code; we swap it for their verified email.
// Only the admin (ADMIN_EMAIL) and emails the admin invited may sign in.
import { cookie, createSession, isAdminEmail, normEmail, setCookie } from "../../_lib.js";

const fail = (request, reason) =>
  Response.redirect(new URL(`/login.html?error=${reason}`, request.url).toString(), 302);

export async function onRequestGet({ request, env }) {
  const params = new URL(request.url).searchParams;
  const state = cookie(request, "oauth_state");
  if (!params.get("code") || !state || params.get("state") !== state) return fail(request, "state");

  const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      code: params.get("code"),
      client_id: env.GOOGLE_CLIENT_ID,
      client_secret: env.GOOGLE_CLIENT_SECRET,
      redirect_uri: new URL("/api/auth/callback", request.url).toString(),
      grant_type: "authorization_code",
    }),
  });
  if (!tokenRes.ok) return fail(request, "google");
  const { id_token } = await tokenRes.json();
  // The id_token came straight from Google over TLS in exchange for our secret, so its payload can be trusted as is.
  const bin = atob(id_token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/"));
  const claims = JSON.parse(new TextDecoder().decode(Uint8Array.from(bin, (c) => c.charCodeAt(0))));
  const email = normEmail(claims.email);
  if (!email || !claims.email_verified) return fail(request, "email");

  const admin = isAdminEmail(env, email);
  const known = await env.DB.prepare("SELECT email FROM users WHERE email = ?").bind(email).first();
  if (!admin && !known) return fail(request, "not_invited");

  await env.DB.prepare(
    `INSERT INTO users (email, name, role, last_login) VALUES (?1, ?2, ?3, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
     ON CONFLICT(email) DO UPDATE SET name = ?2, last_login = excluded.last_login,
       role = CASE WHEN ?3 = 'admin' THEN 'admin' ELSE users.role END`
  ).bind(email, claims.name || "", admin ? "admin" : "user").run();

  const headers = new Headers({ Location: new URL("/", request.url).toString() });
  headers.append("Set-Cookie", await createSession(env, email));
  headers.append("Set-Cookie", setCookie("oauth_state", "", 0));
  return new Response(null, { status: 302, headers });
}
