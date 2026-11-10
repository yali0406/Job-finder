import json, re
from scanner.common import get
r = get("https://index.commoncrawl.org/collinfo.json", timeout=30)
print("COLL", r.status_code if r is not None else None, flush=True)
cols = r.json()[:2] if r is not None and r.status_code == 200 else []
print("COLS", [c["id"] for c in cols], flush=True)
for c in cols[:1]:
    for host in ["boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com", "apply.workable.com"]:
        api = c["cdx-api"]
        r = get(api, params={"url": host + "/*", "output": "json", "showNumPages": "true"}, timeout=60)
        print("PAGES", host, r.status_code if r is not None else None, (r.text[:200] if r is not None else ""), flush=True)
        r = get(api, params={"url": host + "/*", "output": "json", "fl": "url", "page": 0}, timeout=120)
        if r is not None and r.status_code == 200:
            slugs = set()
            for line in r.text.splitlines():
                try: u = json.loads(line)["url"]
                except Exception: continue
                m = re.match(r"https?://[^/]+/([\w.-]+)", u)
                if m: slugs.add(m[1].lower())
            print("SLUGS", host, len(slugs), sorted(slugs)[:15], flush=True)
for name, url, params in [
    ("workable", "https://jobs.workable.com/api/v1/jobs", {"query": "data analyst", "location": "Israel"}),
    ("workable2", "https://jobs.workable.com/api/v1/jobs", {"query": "analyst", "location": "Tel Aviv"}),
    ("yc", "https://www.ycombinator.com/jobs/role/operations", {}),
    ("yc2", "https://www.workatastartup.com/jobs", {}),
]:
    r = get(url, params=params, timeout=30)
    print("API", name, r.status_code if r is not None else None, (r.text[:600].replace("\n", " ") if r is not None else ""), flush=True)
