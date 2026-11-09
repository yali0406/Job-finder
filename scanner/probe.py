"""One-off check of candidate job boards for companies whose board isn't known yet."""
import re
from scanner.common import get, in_israel
from scanner.sources.ats import FETCHERS

for slug in ["paloaltonetworks|wd5|panwexternalcareers", "paloaltonetworks|wd5|PANWExternalCareers", "panw|wd5|panwexternalcareers"]:
    jobs = FETCHERS["workday"](slug, "Palo Alto Networks")
    print(f"PROBE PANW {slug} | jobs={len(jobs) if jobs is not None else None} israel={sum(1 for j in jobs if in_israel(j.location)) if jobs else '-'}")
r = get("https://jobs.paloaltonetworks.com/en/")
print("PROBE PANW links", sorted(set(re.findall(r"https?://[\w.-]*myworkdayjobs\.com/[\w/-]*", r.text)))[:5])
for u in ["https://monday.com/careers/all-positions", "https://coralogix.com/careers/"]:
    t = get(u).text
    links = sorted(set(re.findall(r'href="([^"]*(?:position|job|career)[^"]*)"', t, re.I)))
    print(f"PROBE {u} links={len(links)} sample={links[:8]}")
    i = t.find("Tel Aviv")
    print(f"PROBE {u} telaviv_at={i} ctx={t[max(0,i-300):i+100]!r}")
