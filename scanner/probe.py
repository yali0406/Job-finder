"""One-off check of candidate job boards for companies whose board isn't known yet."""
import re
from scanner.common import get, in_israel
from scanner.sources.ats import FETCHERS

t = get("https://coralogix.com/careers/").text
print("PROBE coralogix uid", sorted(set(re.findall(r"(?:company[-_]?uid|companyUid|company_uid)[\"':= ]+([0-9A-F]{2}\.[0-9A-F]{3})", t, re.I))),
      sorted(set(re.findall(r"comeet[^\"']{0,80}", t)))[:6])
for m in sorted(set(re.findall(r"([0-9A-F]{2}\.[0-9A-F]{3})", t)))[:40]:
    jobs = FETCHERS["comeet"](f"coralogix/{m}", "Coralogix")
    if jobs:
        print(f"PROBE coralogix comeet coralogix/{m} jobs={len(jobs)} israel={sum(1 for j in jobs if in_israel(j.location))}")
        break
t = get("https://monday.com/careers/all-positions").text
print("PROBE monday apis", sorted(set(re.findall(r"https?://[\w.-]+/[\w/.-]*(?:job|position|career)[\w/.-]*", t, re.I)))[:12])
