"""LinkedIn public (logged-out) job search. No account is used, and requests are rate limited."""
import random
import re
import time

from bs4 import BeautifulSoup

from ..common import Job, get, log, strip_html

SEARCH = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
DETAIL = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{id}"


def _pause():
    time.sleep(random.uniform(2.5, 5.0))


def search(keywords, location="Israel", hours=24, pages=2):
    jobs = []
    for page in range(pages):
        r = get(SEARCH, params={
            "keywords": keywords, "location": location,
            "f_TPR": f"r{hours * 3600}", "start": page * 25,
        })
        _pause()
        if not r or r.status_code != 200:
            log.warning("LinkedIn search '%s' blocked or failed (%s)", keywords, r.status_code if r else "none")
            break
        soup = BeautifulSoup(r.text, "html.parser")
        cards = soup.select("li")
        if not cards:
            break
        for c in cards:
            title = c.select_one(".base-search-card__title")
            link = c.select_one("a.base-card__full-link") or c.select_one("a")
            if not title or not link:
                continue
            company = c.select_one(".base-search-card__subtitle")
            loc = c.select_one(".job-search-card__location")
            t = c.select_one("time")
            url = link.get("href", "").split("?")[0]
            m = re.search(r"-(\d+)$", url) or re.search(r"(\d{8,})", url)
            jobs.append(Job(
                title=title.get_text(strip=True),
                company=company.get_text(strip=True) if company else "",
                url=url,
                location=loc.get_text(strip=True) if loc else location,
                posted=t.get("datetime", "") if t else "",
                source="linkedin",
                extra={"li_id": m.group(1) if m else None},
            ))
    return jobs


def fetch_description(job: Job):
    li_id = job.extra.get("li_id")
    if not li_id:
        return
    r = get(DETAIL.format(id=li_id))
    _pause()
    if r and r.status_code == 200:
        soup = BeautifulSoup(r.text, "html.parser")
        body = soup.select_one(".show-more-less-html__markup") or soup
        job.description = strip_html(str(body))[:6000]


def fetch_queries(queries):
    out, seen = [], set()
    for q in queries:
        for j in search(q):
            if j.id not in seen:
                seen.add(j.id)
                out.append(j)
    log.info("LinkedIn: %d jobs", len(out))
    return out
