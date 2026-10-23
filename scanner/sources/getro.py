"""VC portfolio job boards powered by Getro (e.g. jobs.tlv.partners)."""
import json
import re

from ..common import Job, get, in_israel, log, post

API = "https://api.getro.com/api/v2/collections/{cid}/search/jobs"
MAX_PAGES = 30


def _next_data(html):
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    return json.loads(m.group(1)) if m else {}


def _find(obj, key):
    """Depth-first search for the first value under `key` in nested JSON."""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find(v, key)
            if r is not None:
                return r
    return None


def _to_job(j, board):
    org = j.get("organization") or {}
    locs = j.get("locations") or j.get("searchableLocations") or []
    if locs and isinstance(locs[0], dict):
        locs = [l.get("name", "") for l in locs]
    return Job(
        title=j.get("title", ""),
        company=org.get("name", ""),
        url=j.get("url") or f"{board}/companies/{org.get('slug','')}/jobs/{j.get('slug','')}",
        location=", ".join(l for l in locs if l),
        posted=str(j.get("createdAt") or j.get("created_at") or ""),
        source=f"vc:{board.split('//')[-1]}",
    )


def fetch_board(board):
    r = get(f"{board}/jobs")
    if not r or r.status_code != 200:
        log.warning("Getro board %s unreachable (%s)", board, r.status_code if r else "no response")
        return []
    data = _next_data(r.text)
    collection = _find(data, "collection") or {}
    cid = collection.get("id") if isinstance(collection, dict) else None
    log.info("Getro %s: next_data=%s collection_id=%s", board, bool(data), cid)

    raw = []
    if cid:
        for page in range(MAX_PAGES):
            resp = post(API.format(cid=cid), json={"hitsPerPage": 100, "page": page, "filters": {}, "query": ""})
            if not resp or resp.status_code != 200:
                log.warning("Getro API %s page %d: %s %s", board, page,
                            resp.status_code if resp else "no response", resp.text[:200] if resp else "")
                break
            hits = (resp.json().get("results") or {}).get("jobs") or resp.json().get("jobs") or []
            if not hits:
                break
            raw.extend(hits)
    if not raw:
        # Fall back to whatever the server-rendered page contains.
        raw = _find(data, "jobs") or []
        if isinstance(raw, dict):
            raw = raw.get("found") or raw.get("items") or []

    jobs = [_to_job(j, board) for j in raw if isinstance(j, dict)]
    jobs = [j for j in jobs if in_israel(j.location)]
    log.info("Getro %s: %d Israel jobs", board, len(jobs))
    return jobs


def fetch_boards(boards):
    out = []
    for b in boards:
        out.extend(fetch_board(b.rstrip("/")))
    return out
