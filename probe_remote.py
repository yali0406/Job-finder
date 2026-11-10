"""Temporary: see which hiring system each careers page uses."""
import json, re
from concurrent.futures import ThreadPoolExecutor
import yaml
from scanner.common import get

cfg = yaml.safe_load(open("sources.yaml"))
C = [(e["name"], e["careers"]) for e in cfg["remote_companies"] if isinstance(e, dict) and e.get("careers")]
RX = re.compile(r"https?://[a-z0-9.-]*(myworkdayjobs|icims|phenom|eightfold|smartrecruiters|greenhouse|lever\.co|ashbyhq|workable|jobvite|bamboohr|recruitee|teamtailor|pinpointhq|rippling|dover|applytojob|paylocity|ultipro|ukg|successfactors|oraclecloud|taleo|avature|breezy|comeet|personio|gem\.com|welcomekit|homerun|workday|jobs\.|careers\.)[^\s\"'<>)]*", re.I)

def one(c):
    name, url = c
    out = {"name": name, "url": url}
    for u in [url, url.replace("https://", "https://www.") if "www." not in url else url.replace("www.", "")]:
        r = get(u, retries=0)
        if r is not None and r.status_code == 200:
            out["final"] = r.url
            out["status"] = 200
            links = []
            for m in RX.finditer(r.text):
                l = m.group(0)[:140]
                if l not in links:
                    links.append(l)
            out["links"] = links[:12]
            out["size"] = len(r.text)
            break
        out["status"] = r.status_code if r is not None else None
    return out

with ThreadPoolExecutor(10) as ex:
    for r in ex.map(one, C):
        print("RESULT", json.dumps(r))
