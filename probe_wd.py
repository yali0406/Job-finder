"""Temporary: see what Workday answers now."""
import re
from scanner.common import session
u = "https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
r = session.post(u, json={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "Israel"}, timeout=25)
t = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", r.text)
print("RESULT", re.sub(r"\s+", " ", t)[:800])
