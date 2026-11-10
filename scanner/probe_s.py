import time, re
from scanner.common import get
for q in ["Geckos Games careers", "Pazu Games careers", "Bengigi careers"]:
    for name, url, params in [("ddg","https://html.duckduckgo.com/html/",{"q":q}),("ddglite","https://lite.duckduckgo.com/lite/",{"q":q}),("bing","https://www.bing.com/search",{"q":q}),("brave","https://search.brave.com/search",{"q":q}),("startpage","https://www.startpage.com/do/search",{"query":q}),("mojeek","https://www.mojeek.com/search",{"q":q})]:
        t=time.time(); r=get(url, params=params, timeout=10, retries=0)
        links = re.findall(r'href="(https?://[^"]+)"', r.text) if r is not None else []
        links=[l for l in links if not re.search(name.replace("lite","")+r"|duckduckgo|bing|microsoft|brave|startpage|mojeek",l)]
        print("S", name, q, r.status_code if r is not None else None, round(time.time()-t,1), links[:4], flush=True)
