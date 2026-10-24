import { randomToken, setCookie } from "../../_lib.js";

export async function onRequestGet({ request, env }) {
  const state = randomToken();
  const url = new URL("https://accounts.google.com/o/oauth2/v2/auth");
  url.search = new URLSearchParams({
    client_id: env.GOOGLE_CLIENT_ID,
    redirect_uri: new URL("/api/auth/callback", request.url).toString(),
    response_type: "code",
    scope: "openid email profile",
    state,
    prompt: "select_account",
  }).toString();
  return new Response(null, {
    status: 302,
    headers: { Location: url.toString(), "Set-Cookie": setCookie("oauth_state", state, 600) },
  });
}
