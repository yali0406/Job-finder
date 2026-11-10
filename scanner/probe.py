import json, re
from concurrent.futures import ThreadPoolExecutor
from scanner.common import get, in_israel
from scanner.sources import ats

cands = json.load(open("scanner/probe_cands.json"))

def work(c):
    a, s = c["ats"], c["slug"]
    if a == "comeet_uid":
        r = get(s, timeout=15, retries=1)
        t = r.text if r is not None else ""
        u = re.search(r"comeet[_-]?uid['\"]?\s*[:=]\s*['\"]([0-9A-F]{2}\.[0-9A-F]{3})", t, re.I)
        k = re.search(r"comeet[_-]?token['\"]?\s*[:=]\s*['\"]([0-9A-Fa-f]{8,})", t, re.I)
        if u and k:
            a, s = "comeet_api", f"{u[1]}|{k[1]}"
        elif re.search(r"/co/[\w-]+/[0-9A-F]{2}\.[0-9A-F]{3}", t):
            a = "comeet_site"
        else:
            return c, a, s, None, 0, []
    try:
        jobs = ats.FETCHERS[a](s, c["name"])
    except Exception as e:
        return c, a, s, f"ERR {e}", 0, []
    if jobs is None:
        return c, a, s, None, 0, []
    il = [j for j in jobs if in_israel(j.location)]
    return c, a, s, len(jobs), len(il), [j.title for j in (il or jobs)[:3]]

out = []
with ThreadPoolExecutor(8) as ex:
    for c, a, s, n, il, sample in ex.map(work, cands):
        print(f"V\t{c['name']}\t{c['section']}\t{a}\t{s}\t{n}\t{il}\t{sample}", flush=True)
