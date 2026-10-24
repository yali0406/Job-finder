// Everything on the site is private: no session → the login page (or 401 for the API).
import { json, sessionUser } from "./_lib.js";

const PUBLIC = [/^\/login(\.html)?$/, /^\/api\/auth\//, /^\/favicon/];

export async function onRequest(context) {
  const { request, env, next, data } = context;
  const path = new URL(request.url).pathname;
  if (PUBLIC.some((re) => re.test(path))) return next();

  const user = await sessionUser(env, request);
  if (!user) {
    if (path.startsWith("/api/")) return json({ error: "not signed in" }, 401);
    return Response.redirect(new URL("/login.html", request.url).toString(), 302);
  }
  data.user = user;
  const res = await next();
  // Pages and data are per user now: never let a shared cache keep them.
  const out = new Response(res.body, res);
  out.headers.set("Cache-Control", "private, no-store");
  return out;
}
