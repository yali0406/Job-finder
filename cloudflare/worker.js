// Cloudflare Worker that starts the "scan jobs" GitHub Action on a cron schedule.
// GitHub's own schedule is unreliable on the free plan (runs get delayed or dropped).
// Needs a secret GH_TOKEN: fine-grained token for this repo with "Actions: Read and write".
const REPO = "yali0406/Job-finder";
const WORKFLOW = "scan.yml";

async function dispatch(env) {
  const res = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GH_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "job-finder-cron",
    },
    body: JSON.stringify({ ref: "main", inputs: { linkedin: "auto" } }),
  });
  return `${res.status} ${await res.text()}`;
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(dispatch(env).then((r) => console.log("dispatch:", r)));
  },
  // No public trigger: anyone who found the URL could otherwise burn Actions minutes.
  async fetch() {
    return new Response("job-finder cron worker", { status: 200 });
  },
};
