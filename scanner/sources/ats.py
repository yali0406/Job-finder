"""Company career pages hosted on public ATS (applicant tracking system) APIs.

Each company in sources.yaml is matched to an ATS + slug once (auto-detect), and the
result is cached in docs/data/ats_cache.json so later runs only hit the right endpoint.
"""
import json
import re

import requests
from datetime import datetime, timezone, timedelta

from ..common import ISRAEL_HINTS as ISRAEL_IN_TEXT, Job, get, in_israel, log, post, strip_html


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


def _lever(slug, company, host="api.lever.co"):
    r = get(f"https://{host}/v0/postings/{slug}", params={"mode": "json"})
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


def _lever_eu(slug, company):
    return _lever(slug, company, host="api.eu.lever.co")


def _workday(slug, company):
    """slug format: 'tenant|wdN|site', e.g. 'nvidia|wd5|NVIDIAExternalCareerSite'."""
    try:
        tenant, wd, site = slug.split("|")
    except ValueError:
        return None
    base = f"https://{tenant}.{wd}.myworkdayjobs.com"
    jobs = []
    for offset in range(0, 400, 20):
        r = post(f"{base}/wday/cxs/{tenant}/{site}/jobs",
                 json={"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": "Israel"})
        if not r or r.status_code != 200:
            return jobs or None
        posts = r.json().get("jobPostings") or []
        for j in posts:
            jobs.append(Job(
                title=j.get("title", ""),
                company=company,
                url=f"{base}/en-US/{site}{j.get('externalPath', '')}",
                location=j.get("locationsText", ""),
                posted=j.get("postedOn", ""),
                source="workday",
                extra={"detail": f"{base}/wday/cxs/{tenant}/{site}{j.get('externalPath', '')}"},
            ))
        if len(posts) < 20:
            break
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
    content = list(data.get("content", []))
    # big employers (e.g. Check Point) have more than one page; without paging, jobs past the first
    # 100 would flicker in and out between runs and get dropped as "closed"
    while len(content) < min(data.get("totalFound", 0), 1000):
        more = get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings",
                   params={"country": "il", "limit": 100, "offset": len(content)})
        page = more.json().get("content", []) if more and more.status_code == 200 else []
        if not page:
            break
        content += page
    jobs = []
    for j in content:
        loc = j.get("location") or {}
        jobs.append(Job(
            title=j.get("name", ""),
            company=company,
            url=f"https://jobs.smartrecruiters.com/{slug}/{j.get('id')}",
            location=", ".join(x for x in [loc.get("city"), loc.get("country")] if x),
            posted=j.get("releasedDate", ""),
            source="smartrecruiters",
            extra={"detail": f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{j.get('id')}"},
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
    m = re.search(r"COMPANY_POSITIONS_DATA\s*=\s*", r.text)
    if not m:
        return None
    try:
        positions, _ = json.JSONDecoder().raw_decode(r.text, m.end())
    except json.JSONDecodeError:
        return None
    jobs = []
    for j in positions:
        loc = j.get("location") or {}
        details = " ".join(strip_html(d.get("value") or "") for d in j.get("details") or [])
        jobs.append(Job(
            title=j.get("name", ""),
            company=company,
            url=j.get("url_comeet_hosted_page") or j.get("url_active_page", ""),
            location=", ".join(x for x in [loc.get("city"), "Israel" if loc.get("country") == "IL" else loc.get("country")] if x),
            description=details,
            posted=j.get("time_updated", ""),
            source="comeet",
        ))
    return jobs


def _comeet_site(slug, company):
    """Companies that embed Comeet on their own careers page (e.g. Coralogix): slug is that page's URL;
    each position is a link like /careers/co/<location>/<uid>/<title-slug>/all/."""
    r = get(slug)
    if not r or r.status_code != 200:
        return None
    jobs, seen = [], set()
    for m in re.finditer(r'href="([^"]*/co/([\w-]+)/([0-9A-F]{2}\.[0-9A-F]{3}[\w.-]*)/([\w-]+)/all/?)"', r.text):
        url, loc, uid, title = m.groups()
        if uid in seen:
            continue
        seen.add(uid)
        jobs.append(Job(title=title.replace("-", " ").title(), company=company,
                        url=url if url.startswith("http") else requests.compat.urljoin(slug, url),
                        location=loc.replace("-", " ").title(), source="comeet"))
    return jobs


def _comeet_api(slug, company):
    """Companies whose careers page embeds Comeet's widget: slug is '<uid>|<token>' taken from that page
    (the widget's public careers API; the token is published in the page itself)."""
    uid, _, token = slug.partition("|")
    r = get(f"https://www.comeet.co/careers-api/2.0/company/{uid}/positions",
            params={"token": token, "details": "true"})
    if not r or r.status_code != 200:
        return None
    try:
        rows = r.json()
    except ValueError:
        return None
    jobs = []
    for x in rows if isinstance(rows, list) else []:
        loc = x.get("location") or {}
        details = " ".join(strip_html(d.get("value") or "") for d in x.get("details") or [])
        jobs.append(Job(title=x.get("name", ""), company=company,
                        url=x.get("url_active_page") or x.get("url_comeet_hosted_page") or "",
                        location=", ".join(v for v in [loc.get("city"), "Israel" if loc.get("country") == "IL" else loc.get("country")] if v) or loc.get("name") or "",
                        description=details, posted=x.get("time_updated", ""), source="comeet"))
    return jobs


def _bamboohr(slug, company):
    r = get(f"https://{slug}.bamboohr.com/careers/list", headers={"Accept": "application/json"})
    if not r or r.status_code != 200:
        return None
    try:
        rows = r.json().get("result", [])
    except ValueError:
        return None
    jobs = []
    for x in rows:
        loc = x.get("location") or {}
        jobs.append(Job(title=x.get("jobOpeningName", ""), company=company,
                        url=f"https://{slug}.bamboohr.com/careers/{x.get('id')}",
                        location=", ".join(v for v in [loc.get("city"), loc.get("state"), loc.get("country")] if v) or "Israel",
                        source="bamboohr"))
    return jobs


def _breezy(slug, company):
    r = get(f"https://{slug}.breezy.hr/json")
    if not r or r.status_code != 200:
        return None
    try:
        rows = r.json()
    except ValueError:
        return None
    return [Job(title=x.get("name", ""), company=company, url=x.get("url", ""),
                location=((x.get("location") or {}).get("name") or "Israel"), source="breezy")
            for x in rows if isinstance(x, dict)]


def _recruitee(slug, company):
    r = get(f"https://{slug}.recruitee.com/api/offers/")
    if not r or r.status_code != 200:
        return None
    try:
        rows = r.json().get("offers", [])
    except ValueError:
        return None
    return [Job(title=x.get("title", ""), company=company, url=x.get("careers_url", ""),
                location=x.get("location") or x.get("country") or "Israel",
                description=strip_html(x.get("description") or ""), source="recruitee")
            for x in rows]


# Links that lead to a single job posting, on a company's own careers page.
_JOB_HREF = re.compile(r"job|career|position|opening|vacanc|apply|/role|/co/|comeet|greenhouse|lever\.co|ashbyhq|"
                       r"workable|bamboohr|breezy|recruitee|teamtailor|hibob|jobvite|icims|personio|pinpoint|"
                       r"rippling|smartrecruiters|myworkdayjobs|משר|דרוש", re.I)
_JOB_TITLE = re.compile(r"\b(engineer|analyst|manager|developer|specialist|representative|designer|lead|director|"
                        r"associate|coordinator|executive|scientist|architect|consultant|administrator|intern|"
                        r"student|officer|devops|sre|accountant|controller|recruiter|writer|artist|producer|"
                        r"researcher|technician|agent|partner|owner|head|vp|bdr|sdr|pmo)\b|"
                        r"מפתח|מנהל|אנליסט|רכז|נציג|מהנדס|סטודנט|דרוש|ראש צוות|מתאם|יועץ", re.I)
_NOT_JOB = re.compile(r"blog|news|read more|learn more|webinar|case stud|podcast|press|tour|pricing|contact|"
                      r"talk to|book a|request|sign ?up|log ?in|privacy|terms|cookie|about us|our team|"
                      r"meet the|all jobs|view all|open positions|see all|careers?$|join us", re.I)


def _careers_page(slug, company):
    """Generic reader for a company's own careers page that lists jobs as plain links
    (no job-board system we know). slug is the careers page URL. Descriptions are read
    from each job's page later, only for jobs that pass the title pre-filter."""
    r = get(slug)
    if not r or r.status_code != 200:
        return None
    jobs, seen = [], set()
    for m in re.finditer(r'<a\b[^>]*href="([^"#]+)"[^>]*>([\s\S]{2,300}?)</a>', r.text, re.I):
        href, inner = m.groups()
        text = re.sub(r"\s+", " ", strip_html(inner)).strip()
        parts = [re.sub(r"\s+", " ", p).strip() for p in re.split(r"<[^>]+>", inner)]
        title = next((p for p in parts if _JOB_TITLE.search(p)), text)[:120]
        if not (4 < len(title) < 100) or len(title.split()) < 2:
            continue
        if not _JOB_TITLE.search(title) or _NOT_JOB.search(title):
            continue
        url = requests.compat.urljoin(r.url, _unescape(href))
        if url.rstrip("/") == r.url.rstrip("/") or not _JOB_HREF.search(url):
            continue
        if url in seen or re.search(r"linkedin\.|indeed\.|glassdoor\.|facebook\.", url):
            continue
        seen.add(url)
        loc = ""
        lm = ISRAEL_IN_TEXT.search(text)
        jobs.append(Job(title=title, company=company, url=url,
                        location=lm.group(0) if lm else "Israel", source="careers_page"))
    return jobs


FETCHERS = {
    "greenhouse": _greenhouse,
    "lever": _lever,
    "ashby": _ashby,
    "smartrecruiters": _smartrecruiters,
    "workable": _workable,
    "comeet": _comeet,
    "lever_eu": _lever_eu,
    "workday": _workday,
    "comeet_site": _comeet_site,
    "bamboohr": _bamboohr,
    "breezy": _breezy,
    "recruitee": _recruitee,
    "careers_page": _careers_page,
    "comeet_api": _comeet_api,
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


# ATS links as they appear on a company's own careers page -> (ats, slug).
CAREERS_LINKS = [
    ("comeet", re.compile(r"comeet\.(?:com|co)/jobs/([\w.-]+)/([0-9A-F]{2}\.[0-9A-F]{3})", re.I), lambda m: f"{m[1]}/{m[2]}"),
    ("greenhouse", re.compile(r"(?:boards|job-boards)(?:-api)?\.(?:eu\.)?greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([\w-]+)", re.I), lambda m: m[1]),
    ("lever_eu", re.compile(r"jobs\.eu\.lever\.co/([\w-]+)", re.I), lambda m: m[1]),
    ("lever", re.compile(r"jobs\.lever\.co/([\w-]+)", re.I), lambda m: m[1]),
    ("ashby", re.compile(r"jobs\.ashbyhq\.com/([\w.%-]+)", re.I), lambda m: m[1]),
    ("smartrecruiters", re.compile(r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)", re.I), lambda m: m[1]),
    ("workable", re.compile(r"apply\.workable\.com/([\w-]+)", re.I), lambda m: m[1]),
]


def detect_from_careers(url: str, name: str):
    """Read the company's careers page and follow the first job-board link that answers."""
    r = get(url)
    if not r or r.status_code != 200:
        log.info("%s: careers page %s unreachable (%s)", name, url, r.status_code if r else "no response")
        return None, None, None
    seen = set()
    for ats, rx, to_slug in CAREERS_LINKS:
        for m in rx.finditer(r.text):
            slug = to_slug(m)
            if (ats, slug) in seen or slug.lower() in ("embed", "js", "v1"):
                continue
            seen.add((ats, slug))
            jobs = FETCHERS[ats](slug, name)
            if jobs is not None:
                return ats, slug, jobs
    log.info("%s: no known job board linked from %s", name, url)
    return None, None, None


def detect(name: str, careers: str | None = None):
    if careers:
        ats, slug, jobs = detect_from_careers(careers, name)
        if ats:
            return ats, slug, jobs
    for ats in AUTODETECT_ORDER:
        for slug in slug_candidates(name):
            jobs = FETCHERS[ats](slug, name)
            if jobs:  # non-empty list => company found with open jobs
                return ats, slug, jobs
    return None, None, []


# Looking up an unknown company's job board tries many URLs and can take ~30s, so cap how many
# lookups one run does; the rest wait for the next run (otherwise a big batch of new companies
# pushes the run past its time limit before anything is saved).
MAX_DETECT_PER_RUN = 25
_detected_this_run = 0


def fetch_companies(companies, cache: dict, israel_only=True):
    """companies: list of str or {name, ats, slug} or {name, careers}. cache: mutated in place."""
    global _detected_this_run
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
            # A newly added careers page is tried right away.
            last = cached.get("checked")
            new_page = entry.get("careers") and cached.get("careers") != entry.get("careers")
            if last and not new_page and now - datetime.fromisoformat(last) < timedelta(days=7):
                continue
            if _detected_this_run >= MAX_DETECT_PER_RUN:
                continue
            _detected_this_run += 1
            ats, slug, jobs = detect(name, entry.get("careers"))
            cache[name] = {"ats": ats, "slug": slug, "checked": now.isoformat(), "careers": entry.get("careers")}
            if ats:
                log.info("%s: detected %s/%s", name, ats, slug)

        jobs = jobs or []
        if israel_only:
            jobs = [j for j in jobs if in_israel(j.location)]
        all_jobs.extend(jobs)
    return all_jobs


def fetch_description(job: Job):
    """For sources whose list endpoint has no description, fetch it for jobs we're about to score."""
    if job.description:
        return
    url = job.extra.get("detail")
    if not url:
        # No API for details (Comeet, VC boards): read the public job page itself.
        if job.url:
            r = get(job.url)
            if r and r.status_code == 200 and "html" in r.headers.get("content-type", ""):
                job.description = (_embedded_details(r.text) or strip_html(r.text))[:8000]
        if len(job.description or "") < 300 and job.extra.get("getro_page"):
            # Many company career sites render client-side; the VC board keeps its own copy of the text.
            r = get(job.extra["getro_page"])
            if r and r.status_code == 200:
                desc = _getro_description(r.text)
                if desc:
                    job.description = desc[:8000]
        return
    r = get(url)
    if not r or r.status_code != 200:
        return
    data = r.json()
    if job.source == "smartrecruiters":
        sections = (data.get("jobAd") or {}).get("sections") or {}
        job.description = strip_html(" ".join((v or {}).get("text", "") for v in sections.values()))
    elif job.source == "workday":
        job.description = strip_html((data.get("jobPostingInfo") or {}).get("jobDescription", ""))


def _getro_description(html: str) -> str:
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return ""
    best = ""

    def walk(o):
        nonlocal best
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("description", "descriptionHtml", "description_html") and isinstance(v, str) and len(v) > len(best):
                    best = v
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    try:
        walk(json.loads(m.group(1)))
    except json.JSONDecodeError:
        return ""
    return strip_html(best)


def _embedded_details(html: str) -> str:
    """Comeet pages render client-side; the description sits in a JSON "details" array in a script."""
    texts = []
    for m in re.finditer(r'"details"\s*:\s*(?=\[)', html):
        try:
            arr, _ = json.JSONDecoder().raw_decode(html, m.end())
        except json.JSONDecodeError:
            continue
        for d in arr if isinstance(arr, list) else []:
            if isinstance(d, dict) and d.get("value"):
                texts.append(f"{d.get('name', '')}: {strip_html(d['value'])}")
        if texts:
            break
    return "\n".join(texts)
