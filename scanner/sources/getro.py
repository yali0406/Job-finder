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


EARLY_STAGES = {"pre_seed", "preseed", "seed", "series_a", "stealth", "early_stage", "angel"}


def _norm_stage(v) -> str:
    if isinstance(v, dict):
        v = v.get("name") or v.get("value") or ""
    return re.sub(r"[^a-z]+", "_", str(v or "").lower()).strip("_")


def _is_early(org: dict) -> bool:
    """Early only by the org's own stage field; exited, acquired and public companies never count."""
    stage = _norm_stage(org.get("stage"))
    if stage:
        return stage in EARLY_STAGES
    hc = org.get("head_count")
    # Head count only when it's a readable range like "11-50" (Getro sometimes sends a bucket number instead).
    return isinstance(hc, str) and bool(re.match(r"^(1|2|11)\s*-\s*(10|20|50)$", hc.strip()))


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
        extra={"getro_page": f"{board}/companies/{org['slug']}/jobs/{j['slug']}"
               if org.get("slug") and j.get("slug") else ""},
    )


def fetch_board(board):
    r = get(f"{board}/jobs")
    if not r or r.status_code != 200:
        log.warning("Getro board %s unreachable (%s)", board, r.status_code if r else "no response")
        return []
    data = _next_data(r.text)
    cid = None
    for key in ("collection", "network"):
        obj = _find(data, key)
        if isinstance(obj, dict) and obj.get("id"):
            cid = obj["id"]
            break
    page_props = (data.get("props") or {}).get("pageProps") or {}
    log.info("Getro %s: collection_id=%s pageProps keys=%s", board, cid, list(page_props)[:15])

    raw = []
    if cid:
        for page in range(MAX_PAGES):
            resp = post(API.format(cid=cid), json={"hitsPerPage": 100, "page": page,
                                                   "filters": {"searchable_locations": ["Israel"]}, "query": ""},
                        headers={"Origin": board, "Referer": f"{board}/jobs", "Accept": "application/json"})
            if not resp or resp.status_code != 200:
                log.warning("Getro API %s page %d: %s %s", board, page,
                            resp.status_code if resp else "no response", resp.text[:200] if resp else "")
                break
            hits = (resp.json().get("results") or {}).get("jobs") or resp.json().get("jobs") or []
            if not hits:
                break
            raw.extend(hits)
    if not raw:
        # Fall back to the server-rendered page, filtered to Israel (first page of results only).
        import base64
        flt = base64.b64encode(json.dumps({"searchable_locations": ["Israel"]}).encode()).decode()
        r2 = get(f"{board}/jobs", params={"filter": flt})
        data2 = _next_data(r2.text) if r2 and r2.status_code == 200 else data
        raw = _find(data2, "jobs") or []
        if isinstance(raw, dict):
            raw = raw.get("found") or raw.get("items") or []

    raw = [j for j in raw if isinstance(j, dict)]
    if raw:
        from collections import Counter
        orgs = [j.get("organization") or {} for j in raw]
        log.info("Getro %s org stages: %s", board, dict(Counter(_norm_stage(o.get("stage")) for o in orgs).most_common(12)))
        log.info("Getro %s org head counts: %s", board, dict(Counter(str(o.get("head_count")) for o in orgs).most_common(12)))
    jobs = []
    for j in raw:
        job = _to_job(j, board)
        if _is_early(j.get("organization") or {}):
            job.extra["broad"] = "early-stage startup"
        jobs.append(job)
    jobs = [j for j in jobs if in_israel(j.location)]
    log.info("Getro %s: %d Israel jobs", board, len(jobs))
    return jobs


def fetch_boards(boards):
    out = []
    for b in boards:
        out.extend(fetch_board(b.rstrip("/")))
    return out
