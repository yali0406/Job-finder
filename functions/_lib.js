// Shared helpers for the Pages Functions: cookies, sessions, JSON responses.
export const SESSION_COOKIE = "sid";
const SESSION_DAYS = 30;

export function cookie(request, name) {
  const m = (request.headers.get("Cookie") || "").match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return m ? decodeURIComponent(m[1]) : null;
}

export function setCookie(name, value, maxAge) {
  return `${name}=${encodeURIComponent(value)}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAge}`;
}

export function json(data, status = 200, headers = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...headers },
  });
}

export function randomToken() {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export const normEmail = (e) => String(e || "").trim().toLowerCase();

export function isAdminEmail(env, email) {
  return !!env.ADMIN_EMAIL && normEmail(env.ADMIN_EMAIL) === normEmail(email);
}

export async function createSession(env, email) {
  const token = randomToken();
  const expires = new Date(Date.now() + SESSION_DAYS * 864e5).toISOString();
  await env.DB.prepare("INSERT INTO sessions (token, email, expires_at) VALUES (?, ?, ?)").bind(token, email, expires).run();
  return setCookie(SESSION_COOKIE, token, SESSION_DAYS * 86400);
}

export async function sessionUser(env, request) {
  const token = cookie(request, SESSION_COOKIE);
  if (!token) return null;
  return env.DB.prepare(
    `SELECT u.email, u.name, u.role FROM sessions s JOIN users u ON u.email = s.email
     WHERE s.token = ? AND s.expires_at > strftime('%Y-%m-%dT%H:%M:%SZ', 'now')`
  ).bind(token).first();
}
