"""Temporary: see what Workday answers now."""
import requests
from scanner.common import session
u = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
body = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "Israel"}
for label, s, h in [("session", session, {}), ("session+accept", session, {"Accept": "application/json"}),
                    ("plain", requests, {"Accept": "application/json", "Content-Type": "application/json"}),
                    ("plain+origin", requests, {"Accept": "application/json", "Origin": "https://nvidia.wd5.myworkdayjobs.com",
                     "Referer": "https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite"})]:
    try:
        r = s.post(u, json=body, headers=h, timeout=25)
        print("RESULT", label, r.status_code, r.headers.get("content-type"), repr(r.text[:300]))
    except Exception as e:
        print("RESULT", label, "ERR", e)
r = session.get("https://nvidia.wd5.myworkdayjobs.com/NVIDIAExternalCareerSite", timeout=25)
print("RESULT page", r.status_code, repr(r.text[:300]))
