"""Company career pages hosted on public ATS (applicant tracking system) APIs.

Each company in sources.yaml is matched to an ATS + slug once (auto-detect), and the
result is cached in docs/data/ats_cache.json so later runs only hit the right endpoint.
"""
import json
import re
from datetime import datetime, timezone, timedelta

from ..common import Job, get, in_israel, log, strip_html


def _greenhouse(slug, company):
    r = get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
    if not r or r.status_code != 200:
        return None
    return [
        Job(
            title=j.get("title", ""),
            company=company,
            url=j.get("absolute_url", ""),
            location=(j.get("location") or {}).get("name", ""),
            description=strip_html(_unescape(j.get("content", ""))),
            posted=j.get("updated_at", ""),
            source="greenhouse",
        )
        for j in r.json().get("jobs", [])
    ]


def _lever(slug, company):
    r = get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
    if not r or r.status_code != 200 or not isinstance(r.json(), list):
        return None
    jobs = []
    for j in r.json():
        cats = j.get("categories") or {}
        loc = ", ".join(x for x in (cats.get("allLocations") or [cats.get("location")]) if x)
        posted = ""
        if j.get("createdAt"):
            posted = datetime.fromtimestamp(j["createdAt"] / 1000, timezone.utc).isoformat()
        jobs.append(Job(
            title=j.get("text", ""),
            company=company,
            url=j.get("hostedUrl", ""),
            location=loc,
            description=j.get("descriptionPlain", "") + "\n" + "\n".join(
                f"{l.get('text','')}: {strip_html(l.get('content',''))}" for l in j.get("lists", [])
            ),
            posted=posted,
            source="lever",
        ))
    return jobs


def _ashby(slug, company):
    r = get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
    if not r or r.status_code != 200:
        return None
    jobs = []
    for j in r.json().get("jobs", []):
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", [])]
        jobs.append(Job(
            title=j.get("title", ""),
            company=company,
            url=j.get("jobUrl", ""),
            location=", ".join(l for l in locs if l),
            description=j.get("descriptionPlain", ""),
            posted=j.get("publishedAt", ""),
            source="ashby",
        ))
    return jobs


def _smartrecruiters(slug, company):
    r = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", params={"country": "il", "limit": 100})
    if not r or r.status_code != 200:
        return None
    data = r.json()
    if data.get("totalFound", 0) == 0 and not data.get("content"):
        # SmartRecruiters returns 200 + empty list for unknown companies; treat as "not found"
        # unless the company exists with jobs elsewhere.
        probe = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", params={"limit": 1})
        if not probe or probe.status_code != 200 or not probe.json().get("content"):
            return None
    jobs = []
    for j in data.get("content", []):
        loc = j.get("location") or {}
        jobs.append(Job(
            title=j.get("name", ""),
            company=company,
            url=f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
            location=", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
            posted=j.get("releasedDate", ""),
            source="smartrecruiters",
        ))
    return jobs


def _workable(slug, company):
    r = get(f"https://apply.workable.com/api/v1/widget/accounts/{slug}")
    if not r or r.status_code != 200:
        return None
    jobs = []
    for j in r.json().get("jobs", []):
        jobs.append(Job(
            title=j.get("title", ""),
            company=company,
            url=j.get("url") or j.get("shortlink", ""),
            location=", ".join(x for x in [j.get("city"), j.get("country")] if x),
            posted=j.get("published_on", ""),
            source="workable",
        ))
    return jobs


def _comeet(slug, company):
    """slug format: '<company-slug>/<uid>', e.g. 'monday/41.00B' (from the company's comeet.com/jobs URL)."""
    if "/" not in slug:
        return None
    r = get(f"https://www.comeet.com/jobs/{slug}")
    if not r or r.status_code != 200:
        return None
    m = re.search(r"COMPANY_POSITIONS_DATA\s*=\s*(\[.*?\]);", r.text, re.S)
    if not m:
        return None
    jobs = []
    for j in json.loads(m.group(1)):
        loc = j.get("location") or {}
        details = " ".join(strip_html(d.get("value") or "") for d in j.get("details") or [])
        jobs.append(Job(
            title=j.get("name", ""),
            company=company,
            url=j.get("url_comeet_hosted_page") or j.get("url_active_page", ""),
            location=", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
            description=details,
            posted=j.get("time_updated", ""),
            source="comeet",
        ))
    return jobs


FETCHERS = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "ashby": _ashby,
    "smartrecruiters": _smartrecruiters,
    "workable": _workable,
    "comeet": _comeet,
}
AUTODETECT_ORDER = ["greenhouse", "lever", "ashby", "workable", "smartrecruiters"]


def _unescape(s):
    import html
    return html.unescape(s or "")


def slug_candidates(name: str):
    base = re.sub(r"\s*(israel|ltd|inc)\b\.?", "", name, flags=re.I).strip()
    base = base.split("/")[0].strip()
    low = base.lower()
    cands = [
        re.sub(r"[^a-z0-9]", "", low),
        re.sub(r"[^a-z0-9]+", "-", low).strip("-"),
        re.sub(r"[^a-z0-9]", "", low.replace(".com", "")),
    ]
    out = []
    for c in cands:
        if c and c not in out:
            out.append(c)
    return out


def detect(name: str):
    for ats in AUTODETECT_ORDER:
        for slug in slug_candidates(name):
            jobs = FETCHERS[ats](slug, name)
            if jobs:  # non-empty list => company found with open jobs
                return ats, slug, jobs
    return None, None, []


def fetch_companies(companies, cache: dict, israel_only=True):
    """companies: list of str or {name, ats, slug}. cache: mutated in place."""
    now = datetime.now(timezone.utc)
    all_jobs = []
    for entry in companies:
        if isinstance(entry, str):
            entry = {"name": entry}
        name = entry["name"]
        ats, slug = entry.get("ats"), entry.get("slug")
        cached = cache.get(name, {})
        if not ats and cached.get("ats"):
            ats, slug = cached["ats"], cached["slug"]

        jobs = None
        if ats:
            jobs = FETCHERS[ats](slug, name)
            if jobs is None:
                log.warning("%s: %s/%s stopped responding", name, ats, slug)
        else:
            # Retry unknown companies at most once a week.
            last = cached.get("checked")
            if last and now - datetime.fromisoformat(last) < timedelta(days=7):
                continue
            ats, slug, jobs = detect(name)
            cache[name] = {"ats": ats, "slug": slug, "checked": now.isoformat()}
            if ats:
                log.info("%s: detected %s/%s", name, ats, slug)

        jobs = jobs or []
        if israel_only:
            jobs = [j for j in jobs if in_israel(j.location)]
        all_jobs.extend(jobs)
    return all_jobs
