"""Run one scan: collect jobs from every source, keep relevant ones, score new ones, write docs/data/jobs.json."""
import argparse
import json
import re
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from .common import log
from .match import MAX_YEARS, Scorer, prefilter, required_years, STARTUP_OPEN_CATEGORY, STARTUP_OPEN_MIN_SCORE
from .notify import send_digest
from .sources import ats, getro, linkedin, remote, workable_search

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "docs" / "data"
JOBS_FILE = DATA / "jobs.json"
CACHE_FILE = DATA / "ats_cache.json"
REJECTED_FILE = DATA / "rejected.json"  # ids dropped after scoring (e.g. 3+ years), so they aren't re-scored
KEEP_DAYS = 30          # drop jobs not seen for this long
MAX_SCORE_PER_RUN = 300  # safety cap on Claude calls per run
RECHECK_PER_RUN = 200    # stored jobs re-read for a years requirement per run


def load_json(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


class _Collector(logging.Handler):
    """Keeps warnings so each run leaves a diagnostics file we can read from the repo."""
    def __init__(self):
        super().__init__(logging.INFO)
        self.lines = []

    def emit(self, record):
        self.lines.append(f"{record.levelname} {record.getMessage()}")


DIAG = _Collector()


def _safe(label, fn, *args):
    """Run one source; if it breaks, log it and carry on with the others."""
    try:
        return fn(*args) or []
    except Exception as e:
        log.warning("%s failed: %s", label, e)
        return []


def collect(cfg, with_linkedin: bool):
    jobs = []
    cache = load_json(CACHE_FILE, {})

    jobs += ats.fetch_companies(cfg.get("companies", []), cache)
    # Boards found by the weekly discovery run (scanner/discover.py) that have openings in Israel.
    jobs += ats.fetch_companies(load_json(ROOT / "discovered_boards.json", []), cache)
    try:
        jobs += workable_search.fetch()
    except Exception as e:  # a search hiccup shouldn't stop the scan
        log.warning("Workable search failed: %s", e)

    broad = ats.fetch_companies(cfg.get("gaming", []), cache)
    for j in broad:
        j.extra["broad"] = "gaming company"
    jobs += broad

    startups = ats.fetch_companies(cfg.get("startups", []), cache)
    for j in startups:
        j.extra["broad"] = "early-stage startup"
    jobs += startups

    for b in cfg.get("vc_boards", []):
        b = b if isinstance(b, dict) else {"url": b}
        # The 🐣 tag comes from each company's own stage and size, not from which VC board listed it.
        jobs += _safe(f"VC board {b['url']}", getro.fetch_board, b["url"].rstrip("/"))

    jobs += _safe("Remote companies", remote.fetch_all, cfg.get("remote_companies", []), cache)

    if with_linkedin:
        jobs += _safe("LinkedIn", linkedin.fetch_queries, cfg.get("linkedin_queries", []))
        jobs += _safe("LinkedIn remote", linkedin.fetch_remote_queries, cfg.get("linkedin_remote_queries", []))

    CACHE_FILE.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True))
    (CACHE_FILE.parent / "discovered.json").write_text(
        json.dumps({k: list(v) for k, v in sorted(getro.DISCOVERED.items())}, indent=1, ensure_ascii=False))
    return jobs


def _still_relevant(d):
    """Re-apply the title filter, so tightening the rules also cleans up older jobs."""
    from .common import Job
    stub = Job(title=d.get("title", ""), company=d.get("company", ""), url="", id=d["id"])
    if d.get("broad"):
        stub.extra["broad"] = d["broad"]
    return prefilter(stub) is not None


def _norm_company(s):
    s = re.sub(r"\(.*?\)", "", (s or "").lower())
    s = re.sub(r"\b(israel|ltd|inc|technologies|pharmaceuticals|group)\b", "", s)
    return re.sub(r"[^a-z0-9\u0590-\u05ff]+", "", s)


def _source_rank(d):
    src = d.get("source", "")
    return 2 if src == "linkedin" else 1 if src.startswith("vc:") else 0


def _dedupe(jobs):
    """One card per company + title: keep the company's own board over VC boards over LinkedIn,
    and list every location the copies had."""
    groups = {}
    for d in jobs:
        key = (_norm_company(d.get("company")), re.sub(r"[^a-z0-9\u0590-\u05ff]+", " ", (d.get("title") or "").lower()).strip())
        groups.setdefault(key, []).append(d)
    # The same posting can come under two names (e.g. Veriti's job on the Check Point board after the
    # acquisition): same title and the same job number in both links means one job.
    by_num = {}
    for key, copies in list(groups.items()):
        for d in copies:
            m = max(re.findall(r"\d{6,}", d.get("url") or ""), key=len, default="")
            if not m:
                continue
            k2 = (key[1], m[-7:])
            if k2 in by_num and by_num[k2] != key and by_num[k2] in groups:
                groups[by_num[k2]].extend(groups.pop(key))
                break
            by_num.setdefault(k2, key)
    out = []
    for copies in groups.values():
        copies.sort(key=lambda d: (_source_rank(d), -(d.get("score") or 0)))
        best = copies[0]
        locs = []
        for d in copies:
            for loc in (d.get("location") or "").split(" · "):
                if loc and loc not in locs:
                    locs.append(loc)
        best["location"] = " · ".join(locs)
        best["first_seen"] = min(d.get("first_seen", "") or best.get("first_seen", "") for d in copies)
        out.append(best)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--linkedin", choices=["auto", "yes", "no"], default="auto",
                    help="auto = only on runs where the Israel-time hour is divisible by 3")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    log.addHandler(DIAG)

    cfg = yaml.safe_load((ROOT / "sources.yaml").read_text())
    # The profile holds personal details, so it comes from a secret (CANDIDATE_PROFILE) and is never committed.
    profile = os.environ.get("CANDIDATE_PROFILE") or (ROOT / "profile.md").read_text()
    now = datetime.now(timezone.utc)
    # LinkedIn every run (Actions minutes are free on the public repo); "no" skips it for quick manual runs
    with_li = args.linkedin != "no"

    DATA.mkdir(parents=True, exist_ok=True)
    existing = {}
    for j in load_json(JOBS_FILE, {"jobs": []})["jobs"]:
        # if a bad merge ever left two copies of a job, keep the most recently scored one
        old = existing.get(j["id"])
        if not old or (j.get("first_seen", ""), j.get("last_seen", "")) > (old.get("first_seen", ""), old.get("last_seen", "")):
            existing[j["id"]] = j

    found = collect(cfg, with_li)
    log.info("Collected %d jobs in Israel", len(found))

    relevant, seen_ids = [], set()
    for j in found:
        if j.id in seen_ids:
            continue
        seen_ids.add(j.id)
        cat = prefilter(j)
        if cat:
            j.category = cat
            relevant.append(j)
    log.info("%d pass the title filter", len(relevant))

    rejected = load_json(REJECTED_FILE, {})
    direct_companies = {j.company.lower() for j in found if not j.source.startswith("vc:") and j.source != "linkedin"}
    scorer = Scorer(profile)
    new_count = scored = 0
    new_jobs = []
    now_s = now.isoformat(timespec="seconds")
    rechecked = 0
    for j in relevant:
        old = existing.get(j.id)
        if old:
            old["last_seen"] = now_s
            old["url"] = j.url or old["url"]
            old["broad"] = j.extra.get("broad", "")  # the early-stage rule may have changed since it was stored
            if not old.get("years_checked") and j.source != "linkedin" and rechecked < RECHECK_PER_RUN:
                # Jobs stored before descriptions were read everywhere: check the years requirement once.
                rechecked += 1
                ats.fetch_description(j)
                need = required_years(j.description)
                if need >= MAX_YEARS:
                    rejected[j.id] = {"title": j.title, "company": j.company, "reason": f"{need}+ years (recheck)", "at": now_s}
                    del existing[j.id]
                    log.info("Recheck dropped %s at %s: %d+ years", j.title, j.company, need)
                    continue
                old["years_checked"] = True
            continue
        if j.id in rejected:
            continue
        if j.source.startswith("vc:") and j.company.lower() in direct_companies:
            continue  # the company's own board has it (or it's closed); see below
        if scored >= MAX_SCORE_PER_RUN:
            continue  # picked up next run
        if j.source == "linkedin" and not j.description:
            linkedin.fetch_description(j)
        else:
            ats.fetch_description(j)
        if not j.description:
            log.info("No description for %s job: %s", j.source, j.url)
        scorer.score(j)
        scored += 1
        if j.category == STARTUP_OPEN_CATEGORY and (j.score or 0) < STARTUP_OPEN_MIN_SCORE:
            rejected[j.id] = {"title": j.title, "company": j.company, "reason": f"startup role, weak fit ({j.score})", "at": now_s}
            continue
        if j.extra.get("years_required", 0) >= MAX_YEARS:
            rejected[j.id] = {"title": j.title, "company": j.company, "reason": f"{j.extra['years_required']}+ years", "at": now_s}
            continue
        d = j.to_dict()
        d["first_seen"] = now_s
        d["last_seen"] = now_s
        d["broad"] = j.extra.get("broad", "")
        d["remote"] = bool(j.extra.get("remote"))
        d["years_checked"] = True
        existing[j.id] = d
        new_count += 1
        new_jobs.append(d)

    # Jobs from sources we didn't scan this run (e.g. LinkedIn off-hours) keep their last_seen.
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    # A stored job whose company's source answered this run but no longer passing the filter (closed, or
    # its company lost the 🐣 tag that let a "foot in the door" title in) is dropped.
    scanned = {(j.source, j.company) for j in found}
    jobs = [j for j in existing.values() if j.get("last_seen", "") >= cutoff and _still_relevant(j)
            and not ((j.get("source"), j.get("company")) in scanned and j.get("last_seen") != now_s)]
    # When a company's own job board answered this run, it is the source of truth: copies from VC
    # boards are either duplicates or stale (the VC board still lists closed jobs).
    direct = {j.company.lower() for j in found if not j.source.startswith("vc:") and j.source != "linkedin"}
    # LinkedIn only shows jobs posted in the last day, so its copies aren't stale; they are kept even
    # for companies scanned directly (a job may be on LinkedIn only), and true duplicates merge below.
    jobs = [j for j in jobs if not (j.get("source", "").startswith("vc:") and (j.get("company") or "").lower() in direct)]
    jobs = _dedupe(jobs)
    # Remember the copies dropped above as seen, so the next run doesn't score them again as "new".
    kept = {j["id"] for j in jobs}
    for d in existing.values():
        if d["id"] not in kept and d.get("first_seen") == now_s:
            rejected[d["id"]] = {"title": d.get("title"), "company": d.get("company"),
                                 "reason": "duplicate of another listing", "at": now_s}
    for j in jobs:
        j.pop("description", None)  # keep the published file small
    jobs.sort(key=lambda j: (j.get("first_seen", ""), j.get("score") or 0), reverse=True)

    REJECTED_FILE.write_text(json.dumps(
        {k: v for k, v in rejected.items() if v.get("at", "") >= cutoff}, ensure_ascii=False, indent=1))
    JOBS_FILE.write_text(json.dumps({
        "updated": now_s,
        "linkedin_scanned": with_li,
        "new_this_run": new_count,
        "jobs": jobs,
    }, ensure_ascii=False, indent=1))
    log.info("New: %d, total kept: %d", new_count, len(jobs))
    from collections import Counter
    (DATA / "diagnostics.json").write_text(json.dumps({
        "run": now_s,
        "collected_by_source": Counter(j.source for j in found),
        "relevant_by_source": Counter(j.source for j in relevant),
        "log": DIAG.lines[-300:],
    }, ensure_ascii=False, indent=1))
    send_digest([j for j in new_jobs if j in jobs], os.environ.get("SITE_URL", ""))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"new_jobs={new_count}\n")


if __name__ == "__main__":
    main()
