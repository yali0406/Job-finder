"""Temporary: test the ppltx fetcher."""
from scanner.sources import ats
from scanner.common import in_israel
j = ats.FETCHERS["ppltx"]("https://jobs.ppltx.co.il", "ppltx")
print("RESULT", None if j is None else len(j))
for x in j or []:
    print("RESULT", x.title, "|", x.location, "|", x.url, "|", in_israel(x.location))
if j:
    ats.fetch_description(j[2]) if hasattr(ats, "fetch_description") else None
    print("RESULT desc", len(j[2].description or ""), repr((j[2].description or "")[:1800]))
