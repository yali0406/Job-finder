// Top menu shared by every page: links, who is signed in, sign out. Admin-only links appear for admins.
(async () => {
  const nav = document.getElementById("nav");
  if (!nav) return;
  const style = document.createElement("style");
  style.textContent = `
    #nav { position: sticky; top: 0; z-index: 10; background: var(--card); border-bottom: 1px solid var(--line); }
    #nav .in { max-width: 980px; margin: 0 auto; padding: 0 16px; display: flex; align-items: center; gap: 4px; min-height: 48px; flex-wrap: wrap; }
    #nav a { color: var(--muted); text-decoration: none; padding: 12px 10px; border-bottom: 2px solid transparent; font-weight: 600; font-size: 14px; }
    #nav a.on { color: var(--text); border-bottom-color: var(--accent); }
    #nav .who { margin-inline-start: auto; color: var(--muted); font-size: 13px; display: flex; gap: 10px; align-items: center; }
    #nav button { border: 1px solid var(--line); background: transparent; color: var(--muted); border-radius: 6px; padding: 3px 10px; cursor: pointer; font: inherit; font-size: 13px; }
    @media (max-width: 560px) { #nav .who span { display: none; } }`;
  document.head.appendChild(style);

  const r = await fetch("/api/me", { cache: "no-store" });
  if (r.status === 401) { location.href = "/login.html"; return; }
  const me = r.ok ? await r.json() : {};
  window.me = me;
  const here = location.pathname.replace(/\/$/, "/index.html");
  const links = [["/index.html", "משרות"], ["/profile.html", "פרופיל"]];
  if (me.role === "admin") links.push(["/admin.html", "ניהול"]);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  nav.innerHTML = `<div class="in">
    ${links.map(([href, label]) => `<a href="${href}" class="${here.endsWith(href) ? "on" : ""}">${label}</a>`).join("")}
    <div class="who"><span>${esc(me.name || me.email)}</span><button id="logout">יציאה</button></div>
  </div>`;
  document.getElementById("logout").onclick = async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    location.href = "/login.html";
  };
  document.dispatchEvent(new CustomEvent("me", { detail: me }));
})();
