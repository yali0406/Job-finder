"""Temporary: find the job boards of a list of remote-hiring companies."""
import json
from concurrent.futures import ThreadPoolExecutor
from scanner.sources import ats

C = [
 ("Workiva", "https://www.workiva.com/careers", []),
 ("Quest Software", "https://careers.quest.com/", ["quest"]),
 ("Appcues", "https://www.appcues.com/careers", []),
 ("Quantum", "https://www.quantum.com/en/company/careers/", ["quantumcorp", "quantum-corporation"]),
 ("Abnormal Security", "https://abnormalsecurity.com/careers", ["abnormalsecurity", "abnormal"]),
 ("DealHub", "https://dealhub.io/careers/", ["dealhubio", "dealhub"]),
 ("Symetra", "https://www.symetra.com/about-us/careers", []),
 ("Renaissance", "https://www.renaissance.com/careers/", ["renaissancelearning", "renaissance"]),
 ("Awesome Motive", "https://awesomemotive.com/careers/", ["awesomemotive"]),
 ("Beekeeper", "https://www.beekeeper.io/careers/", []),
 ("Jenius Bank", "https://www.jeniusbank.com/careers", ["jeniusbank"]),
 ("UserGems", "https://www.usergems.com/careers", []),
 ("Constructor", "https://constructor.com/careers", ["constructor", "constructorio", "constructor.io"]),
 ("Cengage Group", "https://www.cengagegroup.com/careers/", ["cengage"]),
 ("Atlassian", "https://www.atlassian.com/company/careers/all-jobs", []),
 ("LogicGate", "https://www.logicgate.com/careers/", []),
 ("Bold", "https://www.bold.com/careers/", ["bold", "boldcom", "bold-limited"]),
 ("McGraw Hill", "https://careers.mheducation.com/", ["mcgrawhill", "mheducation"]),
 ("Workera", "https://workera.ai/careers", []),
 ("Upstart", "https://www.upstart.com/careers", []),
 ("Arkency", "https://arkency.com/join-our-team/", []),
 ("VGS", "https://www.verygoodsecurity.com/careers", ["verygoodsecurity", "vgs"]),
 ("Kemecon", "http://kemecon.com", []),
 ("DocuSign", "https://careers.docusign.com/", []),
 ("Contra", "https://contra.com/careers", []),
 ("Cash App", "https://block.xyz/careers", ["block", "squareup", "cashapp"]),
 ("Shopify", "https://www.shopify.com/careers", []),
 ("Funded.club", "https://funded.club", ["fundedclub"]),
 ("Rec Room", "https://recroom.com/careers", ["recroom", "rec-room"]),
 ("Goinstacare", "https://goinstacare.com", ["instacare"]),
 ("Patreon", "https://www.patreon.com/careers", []),
 ("Hims & Hers", "https://www.hims.com/careers", ["himshers", "hims", "himsandhers"]),
 ("Intrado", "https://www.intrado.com/careers", []),
 ("Doist", "https://doist.com/careers/", []),
 ("Uplers", "https://www.uplers.com/careers/", []),
 ("Faire", "https://www.faire.com/careers", ["faire"]),
 ("Angel One", "https://www.angelone.in/careers", ["angelone"]),
 ("Upwork", "https://www.upwork.com/careers", []),
 ("MissionWired", "https://missionwired.com/careers/", []),
 ("Sorcero", "https://www.sorcero.com/careers", []),
 ("Census", "https://www.getcensus.com/careers", ["census", "getcensus"]),
 ("DigitalOcean", "https://www.digitalocean.com/careers", ["digitalocean98", "digitalocean"]),
]

def one(c):
    name, careers, slugs = c
    try:
        a, s, jobs = ats.detect(name, careers)
        if not a:
            for slug in slugs:
                for at in ats.AUTODETECT_ORDER:
                    j = ats.FETCHERS[at](slug, name)
                    if j:
                        a, s, jobs = at, slug, j
                        break
                if a:
                    break
        return name, a, s, len(jobs or []), sum(1 for j in jobs or [] if "remote" in (j.location or "").lower())
    except Exception as e:
        return name, None, None, 0, str(e)

with ThreadPoolExecutor(12) as ex:
    for r in ex.map(one, C):
        print("RESULT", json.dumps(r))
