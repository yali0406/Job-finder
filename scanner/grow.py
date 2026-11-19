"""Daily growth: add up to ~100+ new high-tech / fintech / gaming companies to the scan.

1. Candidates: job boards seen in the public Common Crawl index (Comeet, Greenhouse, Lever, Ashby,
   Workable; harvested once a week into growth/pool.json) plus company boards found in the VC
   portfolio boards (docs/data/discovered.json).
2. Each new candidate's board is fetched. It qualifies only with at least one opening in Israel,
   or a remote opening that can be done from Israel.
3. Claude sorts the qualifying companies into high-tech / fintech / gaming / other; "other"
   (retail, staffing agencies, NGOs, ...) is dropped.
4. The day's picks go to added_companies.json (scanned every run by main.py) and the day's list to
   growth/<date>.json, which the daily chat report reads.
"""
import json
import logging
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import yaml
from pydantic import BaseModel

from .common import get, in_israel, log, norm
from .discover import SKIP, _cc
from .sources import ats
from .sources.remote import eligible

ROOT = Path(__file__).resolve().parent.parent
GROWTH = ROOT / "growth"
POOL = GROWTH / "pool.json"
ADDED = ROOT / "added_companies.json"
DAILY_TARGET = int(os.environ.get("GROW_TARGET", "120"))
CHECKS_PER_DAY = int(os.environ.get("GROW_CHECKS", "4000"))
RECHECK_DAYS = 21  # a board with nothing relevant today may have openings in three weeks

# Common Crawl URL prefix -> (ats, regex turning a crawled URL into that ATS's slug)
HOSTS = {
    "www.comeet.com/jobs/": ("comeet", re.compile(r"comeet\.com/jobs/([\w.-]+)/([0-9A-F]{2}\.[0-9A-F]{3})", re.I), lambda m: f"{m[1].lower()}/{m[2].upper()}"),
    "apply.workable.com/": ("workable", re.compile(r"apply\.workable\.com/([\w-]+)", re.I), lambda m: m[1].lower()),
    "boards.greenhouse.io/": ("greenhouse", re.compile(r"greenhouse\.io/([\w-]+)", re.I), lambda m: m[1].lower()),
    "job-boards.greenhouse.io/": ("greenhouse", re.compile(r"greenhouse\.io/([\w-]+)", re.I), lambda m: m[1].lower()),
    "jobs.lever.co/": ("lever", re.compile(r"lever\.co/([\w-]+)", re.I), lambda m: m[1].lower()),
    "jobs.ashbyhq.com/": ("ashby", re.compile(r"ashbyhq\.com/([\w.%-]+)", re.I), lambda m: m[1]),
}
REMOTE_WORDS = re.compile(r"remote|anywhere|worldwide|distributed", re.I)


def _load(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def harvest():
    r = get("https://index.commoncrawl.org/collinfo.json", timeout=60)
    apis = [c["cdx-api"] for c in r.json()[:2]] if r is not None and r.status_code == 200 else []
    found = set()
    for api in apis:
        for prefix, (kind, rx, to_slug) in HOSTS.items():
            r = _cc(api, {"url": prefix + "*", "output": "json", "showNumPages": "true"})
            pages = r.json().get("pages", 0) if r else 0
            for p in range(pages):
                time.sleep(2)
                r = _cc(api, {"url": prefix + "*", "output": "json", "fl": "url", "page": p})
                if not r:
                    continue
                for m in rx.finditer(r.text):
                    slug = to_slug(m)
                    if slug.split("/")[0].lower() not in SKIP and not slug.lower().endswith((".js", ".css", ".png")):
                        found.add((kind, slug))
            log.info("Common Crawl %s %s: %d boards so far", api.split("/")[-1], prefix, len(found))
    return sorted(found)


def _known():
    """Boards and company names already in the scan, so nothing is added twice."""
    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text())
    boards, names = set(), set()
    entries = []
    for sec in ("companies", "gaming", "startups", "remote_companies"):
        entries += cfg.get(sec, []) or []
    entries += _load(ROOT / "discovered_boards.json", []) + _load(ADDED, [])
    for e in entries:
        if isinstance(e, str):
            names.add(norm(e))
            continue
        names.add(norm(e.get("name", "")))
        if e.get("slug"):
            boards.add((e.get("ats"), str(e["slug"]).lower()))
    for n, v in _load(ROOT / "docs" / "data" / "ats_cache.json", {}).items():
        names.add(norm(n))
        if v.get("ats"):
            boards.add((v["ats"], str(v["slug"]).lower()))
    for q in cfg.get("linkedin_queries", []) or []:
        names.add(norm(str(q)))
    names.discard("")
    return boards, names


def _name(kind, slug):
    try:
        if kind == "greenhouse":
            r = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}", retries=0)
            if r is not None and r.status_code == 200:
                return r.json().get("name") or None
        if kind == "workable":
            r = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}", retries=0)
            if r is not None and r.status_code == 200:
                return r.json().get("name") or None
        if kind == "comeet":
            r = get(f"https://www.comeet.com/jobs/{slug}", retries=0)
            if r is not None and r.status_code == 200:
                m = re.search(r'"company_name"\s*:\s*"([^"]+)"', r.text) or re.search(r"<title>\s*([^<|–-]+?)\s*(?:[|–-]|Careers|Jobs|</title>)", r.text)
                if m:
                    return m[1].strip()
    except ValueError:
        pass
    return None


def check(item):
    kind, slug, name = item
    try:
        jobs = ats.FETCHERS[kind](slug, name or slug) or []
    except Exception:
        return None
    il = [j for j in jobs if in_israel(j.location)]
    rem = [j for j in jobs if REMOTE_WORDS.search(j.location or "") and eligible(j.location) and not in_israel(j.location)]
    if not il and not rem:
        return None
    name = name or _name(kind, slug) or re.sub(r"[-_]+", " ", slug.split("/")[0]).title()
    return {"name": name, "ats": kind, "slug": slug, "israel_jobs": len(il), "remote_jobs": len(rem),
            "titles": [j.title for j in (il or rem)][:8]}


class Sectors(BaseModel):
    sectors: list[str]  # hightech / fintech / gaming / other (kept loose; anything else counts as other)


def classify(hits):
    """One sector per company. Without an API key every hit counts as high-tech."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return ["hightech"] * len(hits)
    import anthropic
    client = anthropic.Anthropic()
    out = []
    for i in range(0, len(hits), 25):
        batch = hits[i:i + 25]
        lines = "\n".join(f"{n + 1}. {h['name']} | open roles: {'; '.join(h['titles'])}" for n, h in enumerate(batch))
        try:
            resp = client.messages.parse(
                model=os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5"),
                max_tokens=1000,
                system=("Classify each company by what it does, judging from its name and open roles. "
                        "fintech = payments, banking, lending, insurance tech, trading, crypto, accounting software. "
                        "gaming = game studios, game publishers, iGaming/betting tech, game tools. "
                        "hightech = any other technology company (software, cyber, AI, data, cloud, hardware, "
                        "semiconductors, health tech, e-commerce tech, marketing tech). "
                        "other = not a technology company: staffing/recruiting agencies, retail, restaurants, "
                        "NGOs, schools, government, real estate, manufacturing without a tech product, or unclear. "
                        "Return exactly one label per company, in order, each one of: hightech, fintech, gaming, other."),
                messages=[{"role": "user", "content": lines}],
                output_format=Sectors,
            )
            labels = resp.parsed_output.sectors if resp.parsed_output else []
            labels = [re.sub(r"[^a-z]", "", str(l).lower()) for l in labels]
            labels = [l if l in ("hightech", "fintech", "gaming") else "other" for l in labels]
        except Exception as e:  # API error or an answer that doesn't fit the schema
            log.warning("Classification failed: %s", str(e)[:300])
            labels = []
        if len(labels) != len(batch):
            labels = ["other"] * len(batch)  # can't tell: leave them for a later day
        out += labels
    return out


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    GROWTH.mkdir(exist_ok=True)
    today = date.today().isoformat()
    pool = _load(POOL, {"harvested": None, "candidates": [], "checked": {}})

    harvested = pool.get("harvested")
    if not harvested or (date.today() - date.fromisoformat(harvested)).days >= 7:
        fresh = harvest()
        if fresh:
            pool["candidates"] = sorted({tuple(c) for c in pool["candidates"]} | set(fresh))
            pool["harvested"] = today
            POOL.write_text(json.dumps(pool, ensure_ascii=False))  # an hour of crawling; keep it even if a later step fails
    vc = [(v[0], v[1], n) for n, v in _load(ROOT / "docs" / "data" / "discovered.json", {}).items()]

    boards, names = _known()
    checked = pool.setdefault("checked", {})

    def due(kind, slug):
        last = checked.get(f"{kind}:{slug.lower()}")
        return not last or (date.today() - date.fromisoformat(last)).days >= RECHECK_DAYS

    todo, seen = [], set()
    # VC portfolio companies first (known tech companies with Israeli ties), then the crawl pool.
    for kind, slug, name in vc + [(c[0], c[1], None) for c in pool["candidates"]]:
        key = (kind, slug.lower())
        if kind not in ats.FETCHERS or key in boards or key in seen or (name and norm(name) in names) or not due(kind, slug):
            continue
        seen.add(key)
        todo.append((kind, slug, name))
    todo = todo[:CHECKS_PER_DAY]
    log.info("Checking %d candidate boards", len(todo))

    with ThreadPoolExecutor(16) as ex:
        results = list(ex.map(check, todo))
    for kind, slug, _ in todo:
        checked[f"{kind}:{slug.lower()}"] = today
    # Qualifying boards not classified on an earlier day (more than the daily target) come first.
    hits, used = [], set(names)
    for h in pool.get("pending", []) + [r for r in results if r]:
        if (h["ats"], h["slug"].lower()) in boards:
            continue
        if h and norm(h["name"]) not in used:
            used.add(norm(h["name"]))
            hits.append(h)
    # Israeli openings first, then remote-only companies
    hits.sort(key=lambda h: (-min(h["israel_jobs"], 20), -h["remote_jobs"], h["name"].lower()))
    log.info("%d boards qualify; classifying", len(hits))

    picked, i = [], 0
    while i < len(hits) and len(picked) < DAILY_TARGET:
        chunk = hits[i:i + 50]
        i += len(chunk)
        for h, s in zip(chunk, classify(chunk)):
            if s != "other":
                picked.append({**h, "sector": s})
    pool["pending"] = picked[DAILY_TARGET:] + hits[i:]  # tomorrow's head start
    for p in pool["pending"]:
        p.pop("sector", None)
    picked = picked[:DAILY_TARGET]

    added = _load(ADDED, [])
    for p in picked:
        added.append({"name": p["name"], "ats": p["ats"], "slug": p["slug"], "sector": p["sector"],
                      "remote_only": p["israel_jobs"] == 0, "added": today})
        # a company counted today is not checked again tomorrow
        checked[f"{p['ats']}:{p['slug'].lower()}"] = "9999-12-31"
    ADDED.write_text(json.dumps(added, indent=1, ensure_ascii=False))
    POOL.write_text(json.dumps(pool, ensure_ascii=False))
    (GROWTH / f"{today}.json").write_text(json.dumps({
        "date": today, "checked": len(todo), "qualified": len(hits), "added": picked,
        "pending": len(pool["pending"]),
        "pool_left": sum(1 for c in pool["candidates"] if due(c[0], c[1]) and (c[0], c[1].lower()) not in boards),
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, indent=1, ensure_ascii=False))
    log.info("Added %d companies", len(picked))


if __name__ == "__main__":
    main()
