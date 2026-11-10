"""Workable's own job search across every company that uses Workable (jobs.workable.com), limited to Israel."""
from ..common import Job, get, log, strip_html


def fetch(locations=("Israel",), max_pages=20):
    jobs, seen = [], set()
    for loc in locations:
        token = None
        for _ in range(max_pages):
            params = {"location": loc}
            if token:
                params["pageToken"] = token
            r = get("https://jobs.workable.com/api/v1/jobs", params=params)
            if not r or r.status_code != 200:
                log.warning("Workable search unreachable (%s)", r.status_code if r else "none")
                break
            d = r.json()
            for x in d.get("jobs", []):
                if x.get("id") in seen:
                    continue
                seen.add(x.get("id"))
                l = x.get("location") or {}
                desc = " ".join(strip_html(x.get(k) or "") for k in ("description", "requirementsSection"))
                jobs.append(Job(title=x.get("title", ""), company=(x.get("company") or {}).get("title", ""),
                                url=x.get("url", ""),
                                location=", ".join(v for v in [l.get("city"), l.get("countryName")] if v) or ", ".join(x.get("locations") or []),
                                description=desc[:20000], posted=x.get("created", ""), source="workable"))
            token = d.get("nextPageToken")
            if not token:
                break
    log.info("Workable search: %d jobs in Israel", len(jobs))
    return jobs
