"""Run one scan: collect jobs from every source, keep relevant ones, score new ones, write docs/data/jobs.json."""
import argparse
import json
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import yaml

from .common import log
from .match import MAX_YEARS, Scorer, prefilter, required_years
from .sources import ats, getro, linkedin

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


def collect(cfg, with_linkedin: bool):
    jobs = []
    cache = load_json(CACHE_FILE, {})

    jobs += ats.fetch_companies(cfg.get("companies", []), cache)

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
        jobs += getro.fetch_board(b["url"].rstrip("/"))

    if with_linkedin:
        li = linkedin.fetch_queries(cfg.get("linkedin_queries", []))
        jobs += li

    CACHE_FILE.write_text(json.dumps(cache, indent=1, ensure_ascii=False, sort_keys=True))
    return jobs


def _still_relevant(d):
    """Re-apply the title filter, so tightening the rules also cleans up older jobs."""
    from .common import Job
    stub = Job(title=d.get("title", ""), company=d.get("company", ""), url="", id=d["id"])
    if d.get("broad"):
        stub.extra["broad"] = d["broad"]
    return prefilter(stub) is not None


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
    il_hour = (now + timedelta(hours=3)).hour  # close enough to Israel time for scheduling
    with_li = args.linkedin == "yes" or (args.linkedin == "auto" and il_hour % 3 == 0)

    DATA.mkdir(parents=True, exist_ok=True)
    existing = {j["id"]: j for j in load_json(JOBS_FILE, {"jobs": []})["jobs"]}

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
    scorer = Scorer(profile)
    new_count = scored = 0
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
        if j.extra.get("years_required", 0) >= MAX_YEARS:
            rejected[j.id] = {"title": j.title, "company": j.company, "reason": f"{j.extra['years_required']}+ years", "at": now_s}
            continue
        d = j.to_dict()
        d["first_seen"] = now_s
        d["last_seen"] = now_s
        d["broad"] = j.extra.get("broad", "")
        d["years_checked"] = True
        existing[j.id] = d
        new_count += 1

    # Jobs from sources we didn't scan this run (e.g. LinkedIn off-hours) keep their last_seen.
    cutoff = (now - timedelta(days=KEEP_DAYS)).isoformat()
    jobs = [j for j in existing.values() if j.get("last_seen", "") >= cutoff and _still_relevant(j)]
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
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"new_jobs={new_count}\n")


if __name__ == "__main__":
    main()
