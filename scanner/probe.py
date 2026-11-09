"""One-off check of candidate job boards (ats, slug) for companies whose board isn't known yet."""
import logging
from scanner.common import in_israel
from scanner.sources.ats import FETCHERS, detect_from_careers

CANDIDATES = {
    "monday.com": [("greenhouse", "mondaycom"), ("comeet", "monday/41.00B"), ("ashby", "monday"), ("lever", "monday")],
    "Palo Alto Networks": [("workday", "paloaltonetworks|wd5|External"), ("workday", "paloaltonetworks|wd1|External"), ("greenhouse", "paloaltonetworks")],
    "CyberArk": [("workday", "cyberark|wd5|CyberArk"), ("workday", "cyberark|wd1|External"), ("greenhouse", "cyberark")],
    "Aidoc": [("greenhouse", "aidoc"), ("comeet", "aidoc/E5.00D"), ("ashby", "aidoc"), ("lever", "aidoc")],
    "SentinelOne": [("greenhouse", "sentinelone"), ("greenhouse", "sentinellabs"), ("lever", "sentinelone"), ("ashby", "sentinelone")],
    "Imperva": [("workday", "thales|wd3|Careers"), ("greenhouse", "imperva")],
    "Coralogix": [("greenhouse", "coralogix"), ("ashby", "coralogix"), ("lever", "coralogix")],
    "Echo": [("ashby", "echo"), ("greenhouse", "echo"), ("ashby", "echohq"), ("ashby", "echo-security")],
}
CAREERS = {
    "monday.com": "https://monday.com/careers",
    "Palo Alto Networks": "https://jobs.paloaltonetworks.com/en/",
    "CyberArk": "https://www.cyberark.com/careers/",
    "Aidoc": "https://www.aidoc.com/careers/",
    "SentinelOne": "https://www.sentinelone.com/jobs/",
    "Imperva": "https://www.imperva.com/careers/",
    "Coralogix": "https://coralogix.com/careers/",
    "Echo": "https://www.echo.ai/careers",
}

logging.basicConfig(level=logging.INFO)
for name, cands in CANDIDATES.items():
    for ats, slug in cands:
        try:
            jobs = FETCHERS[ats](slug, name)
        except Exception as e:
            jobs = f"error {e}"
        n = len(jobs) if isinstance(jobs, list) else jobs
        il = sum(1 for j in jobs if in_israel(j.location)) if isinstance(jobs, list) else "-"
        print(f"PROBE {name} | {ats}/{slug} | jobs={n} israel={il}")
    ats, slug, jobs = detect_from_careers(CAREERS[name], name)
    print(f"PROBE {name} | careers page -> {ats}/{slug} | jobs={len(jobs or [])}")
