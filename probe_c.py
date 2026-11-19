"""Temporary: find job boards of remote companies."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from scanner.sources import ats
C = [("Kit",["kit","convertkit"],"kit.com"),("Ashby",["ashby"],"ashbyhq.com"),("Close",["close","closeio","close.io"],"close.com"),
("Brave Software",["brave","bravesoftware"],"brave.com"),("Trail of Bits",["trailofbits","trail-of-bits"],"trailofbits.com"),
("MailerLite",["mailerlite"],"mailerlite.com"),("RevenueCat",["revenuecat"],"revenuecat.com"),("Cloudbeds",["cloudbeds"],"cloudbeds.com"),
("SafetyWing",["safetywing"],"safetywing.com"),("BairesDev",["bairesdev"],"bairesdev.com"),("Xapo Bank",["xapo","xapobank"],"xapobank.com"),("Deltek",["deltek"],"deltek.com")]
def one(c):
    name, slugs, dom = c
    for sl in slugs:
        for at in ["greenhouse","ashby","lever","lever_eu","workable","smartrecruiters","recruitee","breezy","bamboohr"]:
            try: j = ats.FETCHERS[at](sl, name)
            except Exception: j = None
            if j: return name, at, sl, len(j), sum("remote" in (x.location or "").lower() for x in j)
    for u in (f"https://{dom}/careers", f"https://www.{dom}/careers", f"https://{dom}/jobs", f"https://www.{dom}/jobs"):
        try:
            a, s, j = ats.detect_from_careers(u, name)
            if a: return name, a, s, len(j), sum("remote" in (x.location or "").lower() for x in j)
        except Exception: pass
    return name, None, None, 0, 0
with ThreadPoolExecutor(12) as ex:
    for f in as_completed([ex.submit(one, c) for c in C]):
        print("RESULT", json.dumps(f.result()), flush=True)
