"""Temporary: find the job boards of a list of remote-hiring companies."""
import json
from concurrent.futures import ThreadPoolExecutor
from scanner.sources import ats

C = [("Wealthsimple","wealthsimple.com",[]),("Zero Hash","zerohash.com",["zerohash"]),("Affirm","affirm.com",[]),("Marqeta","marqeta.com",[]),
("Flex","flex.one",["flex","getflex","flexone"]),("Horizon3.ai","horizon3.ai",["horizon3ai","horizon3"]),("Second Front","secondfront.com",["secondfrontsystems","secondfront"]),
("Fieldguide","fieldguide.com",["fieldguide"]),("1Password","1password.com",["1password"]),("Vanta","vanta.com",[]),("Chainguard","chainguard.dev",["chainguard"]),
("Tailscale","tailscale.com",[]),("Deepgram","deepgram.com",[]),("Pantheon","pantheon.io",["pantheon","pantheonplatform","pantheonsystems"]),("Fleetio","fleetio.com",[]),
("Runway","runway.com",["runway","runwayfinancial"]),("Render","render.com",["render"]),("Reddit","reddit.com",["reddit"]),("Engine","engine.com",["engine","enginetravel"]),
("Carrot Fertility","get-carrot.com",["carrot","carrotfertility"]),("Maven Clinic","mavenclinic.com",["mavenclinic"]),("Rightway","rightwayhealthcare.com",["rightway","rightwayhealthcare"]),
("Arcadia","arcadia.io",["arcadia","arcadiasolutions"]),("Thatch","thatch.com",["thatch"]),("NetDocuments","netdocuments.com",["netdocuments"]),("Spellbook","spellbook.com",["spellbook","rallylegal"]),
("Mitratech","mitratech.com",["mitratech"]),("Nava PBC","navapbc.com",["navapbc","nava"]),("Atticus","atticus.com",["atticus"]),("Oddball","oddball.io",["oddball"])]

def one(c):
    name, dom, slugs = c
    res = None
    try:
        for careers in (f"https://{dom}/careers", f"https://www.{dom}/careers", f"https://{dom}/jobs"):
            a, s, jobs = ats.detect_from_careers(careers, name)
            if a:
                res = (a, s, jobs, careers); break
        if not res:
            for slug in slugs or [None]:
                cands = [slug] if slug else ats.slug_candidates(name)
                for sl in cands:
                    for at in ats.AUTODETECT_ORDER:
                        j = ats.FETCHERS[at](sl, name)
                        if j:
                            res = (at, sl, j, None); break
                    if res: break
                if res: break
        if not res:
            a, s, jobs = ats.detect(name)
            if a: res = (a, s, jobs, None)
        if not res:
            return name, None, None, 0, 0
        a, s, jobs, cu = res
        return name, a, s, len(jobs or []), sum(1 for j in jobs or [] if "remote" in (j.location or "").lower())
    except Exception as e:
        return name, None, None, 0, str(e)

with ThreadPoolExecutor(12) as ex:
    for r in ex.map(one, C):
        print("RESULT", json.dumps(r))
