"""One-off check of candidate job boards for companies whose board isn't known yet."""
import re
from scanner.common import get, in_israel
from scanner.sources.ats import FETCHERS

PAGES = ["https://monday.com/careers", "https://monday.com/careers/all-positions", "https://jobs.paloaltonetworks.com/en/",
         "https://jobs.paloaltonetworks.com/en/jobs/?location=Israel", "https://careers.cyberark.com/",
         "https://coralogix.com/careers/", "https://www.comeet.com/jobs/coralogix", "https://www.comeet.com/jobs/monday"]
for u in PAGES:
    r = get(u)
    txt = r.text if r is not None else ""
    hits = sorted(set(re.findall(r"(comeet\.(?:com|co)/jobs/[\w./-]{3,40}|[\w-]+\.myworkdayjobs\.com/[\w/-]{0,40}|greenhouse\.io/[\w-]+|"
                                 r"lever\.co/[\w-]+|ashbyhq\.com/[\w.-]+|phenom\w*|eightfold\w*|smartrecruiters\.com/[\w-]+|"
                                 r"api\.[\w.-]+/jobs[\w/?=-]*)", txt, re.I)))[:15]
    print(f"PROBE {u} | status={r.status_code if r is not None else None} len={len(txt)} | {hits}")

CANDS = [("Palo Alto Networks", "workday", "paloaltonetworks|wd1|PaloAltoNetworks"),
         ("Palo Alto Networks", "workday", "paloaltonetworks|wd5|PaloAltoNetworks"),
         ("CyberArk", "workday", "cyberark|wd1|CyberArk"), ("CyberArk", "workday", "cyberark|wd3|CyberArk"),
         ("Coralogix", "workable", "coralogix"), ("Coralogix", "smartrecruiters", "Coralogix"),
         ("monday.com", "workable", "monday"), ("monday.com", "smartrecruiters", "mondaycom")]
for name, ats, slug in CANDS:
    jobs = FETCHERS[ats](slug, name)
    print(f"PROBE {name} | {ats}/{slug} | jobs={len(jobs) if jobs is not None else None} "
          f"israel={sum(1 for j in jobs if in_israel(j.location)) if jobs else '-'}")
