"""Fully remote jobs at companies abroad that can be done from Israel.

Sources: public remote-job board APIs, plus the job boards of remote-first companies.
A job is kept only when its location rules allow working from Israel (worldwide, EMEA, Israel,
or a UTC+2/+3 time zone); jobs limited to the US, Europe-only and so on are dropped.
"""
import re
import xml.etree.ElementTree as ET

from ..common import Job, get, log, strip_html
from . import ats

ELIGIBLE = re.compile(
    r"worldwide|anywhere|global|\bemea\b|israel|middle east|"
    r"utc\s*[+]?\s*[23]\b|gmt\s*[+]?\s*[23]\b|cet|eet|europe.*(middle east|africa)",
    re.I,
)
def eligible(location: str) -> bool:
    loc = (location or "").strip()
    if not loc or re.fullmatch(r"remote", loc, re.I):
        return True  # no restriction stated; Claude reads the description and scores eligibility
    if ELIGIBLE.search(loc):
        return True
    return False


def _job(title, company, url, location, source, description="", posted=""):
    j = Job(title=title or "", company=company or "", url=url or "", location=location or "Remote",
            source=source, description=strip_html(description or "")[:20000], posted=str(posted or ""))
    j.extra["remote"] = True
    return j


def remotive():
    r = get("https://remotive.com/api/remote-jobs")
    if not r or r.status_code != 200:
        log.warning("Remotive unreachable (%s)", r.status_code if r else "none")
        return []
    return [_job(x.get("title"), x.get("company_name"), x.get("url"), x.get("candidate_required_location"),
                 "remote:remotive", x.get("description"), x.get("publication_date"))
            for x in r.json().get("jobs", [])]


def remoteok():
    r = get("https://remoteok.com/api")
    if not r or r.status_code != 200:
        log.warning("RemoteOK unreachable (%s)", r.status_code if r else "none")
        return []
    return [_job(x.get("position"), x.get("company"), x.get("url"), x.get("location"),
                 "remote:remoteok", x.get("description"), x.get("date"))
            for x in r.json() if isinstance(x, dict) and x.get("position")]


def himalayas(pages=15):
    out = []
    for p in range(pages):
        r = get("https://himalayas.app/jobs/api", params={"limit": 20, "offset": p * 20})
        if not r or r.status_code != 200:
            if p == 0:
                log.warning("Himalayas unreachable (%s)", r.status_code if r else "none")
            break
        jobs = r.json().get("jobs", [])
        if not jobs:
            break
        for x in jobs:
            locs = x.get("locationRestrictions") or []
            loc = ", ".join(l if isinstance(l, str) else l.get("name", "") for l in locs) or "Worldwide"
            out.append(_job(x.get("title"), x.get("companyName"), x.get("applicationLink") or x.get("guid"),
                            loc, "remote:himalayas", x.get("description"), x.get("pubDate")))
    return out


def jobicy():
    out = []
    for geo in ("israel", "emea"):
        r = get("https://jobicy.com/api/v2/remote-jobs", params={"count": 50, "geo": geo})
        if not r or r.status_code != 200:
            continue
        for x in r.json().get("jobs", []):
            out.append(_job(x.get("jobTitle"), x.get("companyName"), x.get("url"), x.get("jobGeo") or geo,
                            "remote:jobicy", x.get("jobDescription"), x.get("pubDate")))
    if not out:
        log.warning("Jobicy returned nothing")
    return out


def weworkremotely():
    r = get("https://weworkremotely.com/remote-jobs.rss")
    if not r or r.status_code != 200:
        log.warning("We Work Remotely unreachable (%s)", r.status_code if r else "none")
        return []
    out = []
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return []
    for it in root.iter("item"):
        t = it.findtext("title") or ""
        company, _, title = t.partition(": ")
        out.append(_job(title or t, company, it.findtext("link"), it.findtext("region") or "",
                        "remote:weworkremotely", it.findtext("description"), it.findtext("pubDate")))
    return out


def remote_first_companies(companies, cache):
    jobs = ats.fetch_companies(companies, cache, israel_only=False)
    out = []
    for j in jobs:
        loc = j.location or ""
        if not re.search(r"remote|anywhere|worldwide|distributed", loc, re.I):
            continue
        j.extra["remote"] = True
        out.append(j)
    return out


def fetch_all(companies, cache):
    jobs = []
    for fn in (remotive, remoteok, himalayas, jobicy, weworkremotely):
        try:
            got = fn()
        except Exception as e:  # one broken board shouldn't stop the scan
            log.warning("%s failed: %s", fn.__name__, e)
            got = []
        log.info("Remote board %s: %d jobs", fn.__name__, len(got))
        jobs += got
    jobs += remote_first_companies(companies, cache)
    kept = [j for j in jobs if eligible(j.location)]
    log.info("Remote: %d collected, %d open to Israel", len(jobs), len(kept))
    return kept
