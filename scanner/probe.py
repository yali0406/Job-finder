import json, re, time
from scanner.common import get
r = get("https://jobs.workable.com/api/v1/jobs", params={"query": "analyst", "location": "Israel"}, timeout=30)
d = r.json()
print("WKEYS", list(d.keys()), flush=True)
print("WJOB", json.dumps({k: (v if not isinstance(v, str) else v[:80]) for k, v in d["jobs"][0].items()})[:1500], flush=True)
print("WTOTAL", d.get("totalSize"), len(d["jobs"]), d.get("nextPageToken"), flush=True)
r = get("https://jobs.workable.com/api/v1/jobs", params={"query": "", "location": "Israel"}, timeout=30)
print("WALL", r.json().get("totalSize"), r.json().get("nextPageToken"), flush=True)
api = "https://index.commoncrawl.org/CC-MAIN-2026-43-index"
def cc(params):
    for i in range(6):
        r = get(api, params=params, timeout=180, retries=0)
        if r is not None and r.status_code == 200:
            return r
        time.sleep(10 * (i + 1))
    return None
for host in ["boards.greenhouse.io", "job-boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com", "apply.workable.com"]:
    r = cc({"url": host + "/*", "output": "json", "showNumPages": "true"})
    pages = r.json()["pages"] if r else 0
    slugs = set()
    for p in range(pages):
        time.sleep(3)
        r = cc({"url": host + "/*", "output": "json", "fl": "url", "page": p})
        if not r: continue
        for line in r.text.splitlines():
            m = re.search(r'"url": "https?://[^/]+/([\w.-]+)', line)
            if m: slugs.add(m[1].lower())
    print("SLUGS", host, pages, len(slugs), flush=True)
    time.sleep(5)
