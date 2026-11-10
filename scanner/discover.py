"""Weekly discovery of companies hiring in Israel, straight from the job-board systems.

Same idea as searching Google for site:boards.greenhouse.io "Tel Aviv": the public Common Crawl index
lists the job boards it has seen on Greenhouse, Ashby and Lever; each one is checked for openings in
Israel, and the boards that have any are saved to discovered_boards.json and scanned every run.
"""
import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

from .common import get, in_israel, log
from .sources import ats

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "discovered_boards.json"  # outside docs/data, which each scan run rewrites
HOSTS = {
    "greenhouse": ["boards.greenhouse.io", "job-boards.greenhouse.io", "boards.eu.greenhouse.io", "job-boards.eu.greenhouse.io"],
    "ashby": ["jobs.ashbyhq.com"],
    "lever": ["jobs.lever.co"],
}
SKIP = {"embed", "v1", "api", "jobs", "careers", "static", "assets", "favicon.ico", "robots.txt", "sitemap.xml", "search"}


def _cc(api, params):
    for i in range(6):
        r = get(api, params=params, timeout=180, retries=0)
        if r is not None and r.status_code == 200:
            return r
        time.sleep(10 * (i + 1))
    return None


def harvest():
    r = get("https://index.commoncrawl.org/collinfo.json", timeout=60)
    apis = [c["cdx-api"] for c in r.json()[:2]] if r is not None and r.status_code == 200 else []
    found = {}
    for api in apis:
        for kind, hosts in HOSTS.items():
            for host in hosts:
                r = _cc(api, {"url": host + "/*", "output": "json", "showNumPages": "true"})
                pages = r.json().get("pages", 0) if r else 0
                for p in range(pages):
                    time.sleep(3)
                    r = _cc(api, {"url": host + "/*", "output": "json", "fl": "url", "page": p})
                    if not r:
                        continue
                    for m in re.finditer(r'"url": "https?://[^/]+/([\w.%-]+)', r.text):
                        slug = m[1]
                        if slug.lower() not in SKIP and not slug.lower().endswith((".js", ".css", ".png")):
                            found.setdefault((kind, slug.lower() if kind != "ashby" else slug), True)
                log.info("Common Crawl %s %s: %d boards so far", api.split("/")[-1], host, len(found))
                time.sleep(5)
    return list(found)


def _name(kind, slug):
    if kind == "greenhouse":
        r = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}", retries=0)
        if r is not None and r.status_code == 200:
            return r.json().get("name") or slug
    return re.sub(r"[-_]+", " ", slug).title()


def check(item):
    kind, slug = item
    try:
        jobs = ats.FETCHERS[kind](slug, slug)
    except Exception:
        return None
    il = [j for j in jobs or [] if in_israel(j.location)]
    if not il:
        return None
    return {"name": _name(kind, slug), "ats": kind, "slug": slug, "israel_jobs": len(il)}


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text())
    known = set()
    for sec in ("companies", "gaming", "startups", "remote_companies"):
        for e in cfg.get(sec, []):
            if isinstance(e, dict) and e.get("slug"):
                known.add((e["ats"], str(e["slug"]).lower()))
    cache = json.loads((ROOT / "docs" / "data" / "ats_cache.json").read_text())
    known |= {(v["ats"], str(v["slug"]).lower()) for v in cache.values() if v.get("ats")}
    boards, seen = [], set(known)
    for b in harvest():  # Ashby slugs keep their case, so the same board can appear twice
        if (b[0], b[1].lower()) not in seen:
            seen.add((b[0], b[1].lower()))
            boards.append(b)
    log.info("Checking %d boards for openings in Israel", len(boards))
    with ThreadPoolExecutor(16) as ex:
        hits = [h for h in ex.map(check, boards) if h]
    hits.sort(key=lambda h: (-h["israel_jobs"], h["name"].lower()))
    OUT.write_text(json.dumps(hits, indent=1, ensure_ascii=False))
    log.info("Found %d boards with openings in Israel", len(hits))


if __name__ == "__main__":
    main()
