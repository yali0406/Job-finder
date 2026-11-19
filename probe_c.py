"""Temporary: find job boards for a list of Israeli startups."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from scanner.common import get
from scanner.sources import ats

C = [("Sentra",["sentra.io"]),("Corma",["corma.io"]),("Ramon.Space",["ramon.space"]),("Daylight Security",["daylight.ai","daylightsecurity.com"]),
("Spines",["spines.com"]),("Edelbyte",["edelbyte.com","edelbyte.io"]),("Pluto Security",["pluto.security","plutosecurity.com"]),("Bites",["bites.com","getbites.com"]),
("Bay",["bay.co","bay.io"]),("Dreeze",["dreeze.com","dreeze.io"]),("Zenzap",["zenzap.co","zenzap.com"]),("Mave",["mave.io","mave.ai"]),
("Rein Security",["rein.security","reinsecurity.com"]),("Undecimal Bio",["undecimal.bio","undecimalbio.com"]),("Modelyo",["modelyo.com"]),
("High Lander",["highlander.io","high-lander.com"]),("Brava Security",["brava.security","bravasecurity.com"]),("BloomX",["bloomx.com","bloomx.io"]),
("Plurai",["plurai.ai"]),("Phantom GI",["phantomgi.com","phantom-gi.com"]),("Two Delta",["twodelta.ai","twodelta.com"])]

def domains(name, guesses):
    out = list(guesses)
    r = get("https://autocomplete.clearbit.com/v1/companies/suggest", params={"query": name}, retries=0)
    try:
        for x in (r.json() if r and r.status_code == 200 else [])[:3]:
            out.append(x["domain"] + " (cb:" + x["name"] + ")")
    except Exception:
        pass
    return out

def one(c):
    name, guesses = c
    res = {"name": name, "domains": domains(name, guesses)}
    for sl in ats.slug_candidates(name) + [g.split(".")[0] for g in guesses]:
        for at in ["comeet", "greenhouse", "ashby", "lever", "workable"]:
            if at == "comeet":
                continue
            try:
                j = ats.FETCHERS[at](sl, name)
            except Exception:
                j = None
            if j:
                res.update(ats=at, slug=sl, n=len(j), titles=[x.title for x in j[:6]]); return res
    for d in res["domains"]:
        dom = d.split(" ")[0]
        for u in (f"https://{dom}/careers", f"https://www.{dom}/careers", f"https://{dom}/jobs", f"https://{dom}/"):
            try:
                a, s, j = ats.detect_from_careers(u, name)
                if a:
                    res.update(ats=a, slug=s, n=len(j), url=u, titles=[x.title for x in j[:6]]); return res
                j = ats.FETCHERS["careers_page"](u, name)
                if j:
                    res.update(ats="careers_page", slug=u, n=len(j), titles=[x.title for x in j[:8]]); return res
                lj = ats.FETCHERS["linkedin_links"](u, name)
                if lj:
                    res.update(ats="linkedin_links", slug=u, n=len(lj), titles=[x.title for x in lj[:6]]); return res
            except Exception as e:
                res.setdefault("err", str(e)[:80])
    return res

with ThreadPoolExecutor(11) as ex:
    for f in as_completed([ex.submit(one, c) for c in C]):
        print("RESULT", json.dumps(f.result(), ensure_ascii=False), flush=True)
