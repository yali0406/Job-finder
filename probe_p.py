"""Temporary: look at jobs.ppltx.co.il."""
import re
from scanner.common import get
for u in ["https://jobs.ppltx.co.il/", "https://jobs.ppltx.co.il/robots.txt", "https://jobs.ppltx.co.il/sitemap.xml"]:
    r = get(u, retries=0)
    if not r:
        print("RESULT", u, "none"); continue
    t = r.text
    print("RESULT", u, r.status_code, r.headers.get("content-type"), len(t))
    print("RESULT title", re.findall(r"<title>([^<]*)", t)[:1])
    print("RESULT scripts", re.findall(r'<script[^>]+src="([^"]+)"', t)[:15])
    print("RESULT links", list(dict.fromkeys(re.findall(r'href="([^"]+)"', t)))[:60])
    print("RESULT api", list(dict.fromkeys(re.findall(r'["\'](/?(?:api|wp-json|graphql|ajax)[^"\']{0,80})["\']', t)))[:20])
    print("RESULT next", "__NEXT_DATA__" in t, "wp-content" in t, "nuxt" in t.lower())
    print("RESULT head", re.sub(r"\s+", " ", t[:1500]))
    print("RESULT text", re.sub(r"\s+", " ", re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<[^>]+>", " ", t))[:1500])
