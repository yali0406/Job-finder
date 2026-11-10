import re
from scanner.common import get
r = get("https://www.geckos-games.com/")
t = r.text
print("G", r.status_code, len(t), flush=True)
i = t.lower().find("career")
while i != -1 and i < len(t):
    print("CTX", re.sub(r"\s+", " ", t[max(0, i-300):i+1500])[:1800], flush=True)
    i = t.lower().find("career", i + 1500)
for m in re.finditer(r'(?:href|src)="([^"]+)"', t):
    u = m.group(1)
    if re.search(r"job|career|linkedin|comeet|greenhouse|lever|ashby|workable|apply|position", u, re.I):
        print("LINK", u[:200], flush=True)
