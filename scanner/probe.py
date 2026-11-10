import json, re, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from scanner.common import get
from scanner.sources import ats

BAD = re.compile(r"linkedin|glassdoor|indeed|facebook|twitter|x\.com|instagram|youtube|wikipedia|crunchbase|"
                 r"comparably|builtin|ziprecruiter|alljobs|drushim|jobmaster|startupnationcentral|dealroom|"
                 r"tracxn|pitchbook|zoominfo|bloomberg|reuters|calcalist|globes|geektime|themarker|ynet|"
                 r"wellfound|angel\.co|simplyhired|careerbuilder|monster|jooble|ambitionbox|levels\.fyi|"
                 r"rocketreach|owler|cbinsights|craft\.co|duckduckgo|bing\.com|microsoft\.com/en-us/bing|"
                 r"jobify|jobs\.dev|secrettelaviv|nisha|gotfriends|ethosia|hunterhrms|getro|comeet\.com/jobs/?$", re.I)

ATS_RX = [
 ("comeet", r"comeet\.(?:com|co)/jobs/([\w.-]+)/([0-9A-F]{2}\.[0-9A-F]{3})"),
 ("comeet_uid", r"comeet[_-]?uid['\"]?\s*[:=]\s*['\"]([0-9A-F]{2}\.[0-9A-F]{3})"),
 ("comeet_site", r"/co/[\w-]+/[0-9A-F]{2}\.[0-9A-F]{3}[\w.-]*/[\w-]+/all"),
 ("greenhouse", r"(?:boards|job-boards)(?:-api)?\.(?:eu\.)?greenhouse\.io/(?:embed/job_board(?:/js)?\?for=)?([\w-]+)"),
 ("lever", r"jobs\.(?:eu\.)?lever\.co/([\w-]+)"),
 ("ashby", r"jobs\.ashbyhq\.com/([\w.%-]+)"),
 ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([\w-]+)"),
 ("workable", r"apply\.workable\.com/([\w-]+)"),
 ("workday", r"([\w-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([\w-]+)"),
 ("bamboohr", r"([\w-]+)\.bamboohr\.com/(?:careers|jobs)"),
 ("breezy", r"([\w-]+)\.breezy\.hr"),
 ("recruitee", r"([\w-]+)\.recruitee\.com"),
 ("teamtailor", r"([\w-]+)\.teamtailor\.com"),
 ("hibob", r"([\w-]+)\.careers\.hibob\.com"),
 ("jobvite", r"jobs\.jobvite\.com/([\w-]+)"),
 ("icims", r"([\w-]+)\.icims\.com"),
 ("personio", r"([\w-]+)\.jobs\.personio\.(?:de|com)"),
 ("pinpoint", r"([\w-]+)\.pinpointhq\.com"),
 ("rippling", r"ats\.rippling\.com/([\w-]+)"),
 ("successfactors", r"(career\d*\.successfactors\.(?:com|eu)[^\"' ]*company=[\w-]+)"),
 ("oracle", r"([\w-]+\.fa\.[\w.-]+\.oraclecloud\.com/hcmUI/CandidateExperience[^\"' ]*)"),
 ("eightfold", r"([\w-]+)\.eightfold\.ai"),
 ("phenom", r"(jobs\.[\w-]+\.com|careers\.[\w-]+\.com)/[\w/-]*job"),
 ("niloo", r"([\w-]+)\.niloosoft\.com|hunterhrms|adamtotal|\.smartjob\."),
]
JOBWORD = re.compile(r"\b(engineer|analyst|manager|developer|specialist|representative|designer|lead|director|"
                     r"associate|coordinator|executive|scientist|architect|consultant|administrator|intern|student|"
                     r"operations|devops|sre|product|marketing|sales|support|success|accountant|controller|recruiter)\b|"
                     r"מפתח|מנהל|אנליסט|רכז|נציג|מהנדס|סטודנט|דרוש", re.I)

def search(q):
    out = []
    r = get("https://html.duckduckgo.com/html/", params={"q": q}, timeout=20, retries=1)
    if r is not None and r.status_code == 200:
        for m in re.finditer(r'class="result__a" href="([^"]+)"', r.text):
            u = m.group(1)
            mm = re.search(r"uddg=([^&]+)", u)
            out.append(urllib.parse.unquote(mm.group(1)) if mm else u)
    if not out:
        r = get("https://www.bing.com/search", params={"q": q}, timeout=20, retries=1)
        if r is not None and r.status_code == 200:
            out = re.findall(r'<h2[^>]*><a[^>]+href="(https?://[^"]+)"', r.text)
    return out[:8]

def analyze(html, base):
    hits = []
    for name, rx in ATS_RX:
        for m in re.finditer(rx, html, re.I):
            hits.append((name, m.group(0)[:160]))
            break
    jobs = set()
    for m in re.finditer(r'<a[^>]+href="([^"#]+)"[^>]*>([\s\S]{2,200}?)</a>', html, re.I):
        txt = re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
        if 4 < len(txt) < 90 and JOBWORD.search(txt) and not re.search(r"blog|news|read more|learn more|webinar|case stud|podcast|press|product tour|pricing", txt, re.I):
            jobs.add((txt, urllib.parse.urljoin(base, m.group(1))))
    return hits, sorted(jobs)[:40]

def explore(url):
    r = get(url, timeout=20, retries=1)
    if r is None or r.status_code != 200:
        return {"url": url, "status": r.status_code if r is not None else None}
    hits, jobs = analyze(r.text, r.url)
    res = {"url": r.url, "status": 200, "ats": hits, "joblinks": jobs}
    if not hits:
        subs = []
        for m in re.finditer(r'(?:href|src)="([^"#]+)"', r.text):
            u = urllib.parse.urljoin(r.url, m.group(1))
            if re.search(r"career|jobs|positions|join|open-roles|openings|vacanc|דרושים|משרות|iframe", u, re.I) and u != r.url and u not in subs:
                subs.append(u)
        for u in subs[:4]:
            r2 = get(u, timeout=20, retries=0)
            if r2 is not None and r2.status_code == 200:
                h2, j2 = analyze(r2.text, r2.url)
                if h2 or len(j2) > len(res["joblinks"]):
                    res.update({"sub": r2.url, "ats": h2, "joblinks": j2})
                    if h2: break
    return res

miss = json.load(open("scanner/probe_miss.json"))
results = {}
# phase 1: searches (sequential, polite)
for sec, name, careers in miss:
    q = f"{name} careers jobs"
    urls = search(q)
    results[name] = {"section": sec, "given": careers, "search": urls}
    time.sleep(1.2)
print("searched", sum(1 for v in results.values() if v["search"]), "of", len(results), flush=True)

def work(name):
    v = results[name]
    cands = ([v["given"]] if v["given"] else []) + [u for u in v["search"] if not BAD.search(u)][:3]
    # ATS urls directly in search results
    direct = [u for u in v["search"] if any(re.search(rx, u, re.I) for _, rx in ATS_RX)]
    v["direct"] = direct
    v["pages"] = [explore(u) for u in cands]
    return name

with ThreadPoolExecutor(8) as ex:
    for n in ex.map(work, list(results)):
        pass
# comeet slug test
for s in ("superplay/28.003", "anything/28.003"):
    r = get(f"https://www.comeet.com/jobs/{s}")
    print("COMEET", s, r.status_code if r is not None else None, "COMPANY_POSITIONS_DATA" in (r.text if r is not None else ""), flush=True)
json.dump(results, open("probe_out.json", "w"), ensure_ascii=False, indent=1)
found = [n for n, v in results.items() if v["direct"] or any(p.get("ats") for p in v["pages"]) or any(len(p.get("joblinks", [])) >= 3 for p in v["pages"])]
print("FOUND", len(found), flush=True)
