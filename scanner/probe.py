import re
from scanner.sources import ats
from scanner.common import get

C = {
 "Geckos Games": ["https://www.geckosgames.com/careers", "https://geckos.games/careers", "https://www.geckos.games/careers"],
 "FTX Games": ["https://www.ftxgames.com/careers"],
 "We Create Stuff": ["https://wecreatestuff.com/careers", "https://www.wecreatestuff.com/careers"],
 "Gavra Games": ["https://www.gavragames.com/careers", "https://gavragames.com/careers"],
 "TabTale": ["https://www.tabtale.com/careers"],
 "Pazu Games": ["https://www.pazugames.com/careers", "https://pazugames.com/careers"],
 "Bengigi": ["https://www.bengigi.com/careers", "https://bengigi.com/careers"],
 "Gliding Deer": ["https://www.glidingdeer.com/careers"],
 "Kooply": ["https://www.kooply.com/careers", "https://kooply.com/careers"],
 "EyeClick": ["https://www.eyeclick.com/careers"],
 "Diversion": ["https://www.diversion.dev/careers"],
 "Kinetix": ["https://www.kinetix.tech/careers"],
 "Sloyd": ["https://www.sloyd.ai/careers"],
 "Persona.ly": ["https://persona.ly/careers"],
 "Keewano": ["https://www.keewano.com/careers"],
 "Zengaming": ["https://www.zengaming.com/careers"],
 "CodeMonkey": ["https://www.codemonkey.com/careers"],
 "Tilting Point": ["https://www.tiltingpoint.com/careers"],
 "Duel": ["https://www.duel.com/careers"],
 "Mojiworks": ["https://www.mojiworks.com/careers"],
 "Imagine Games": ["https://www.imaginegames.com/careers"],
 "Gamebeat": ["https://www.gamebeat.com/careers"],
 "GameBoost": ["https://www.gameboost.com/careers"],
 "Jelly Button": ["https://www.jellybutton.com/careers"],
}
for name, urls in C.items():
    found = None
    for u in urls:
        r = get(u)
        st = r.status_code if r else None
        extra = ""
        if r is not None and st == 200:
            co = set(re.findall(r"/co/[\w-]+/[0-9A-F]{2}\.[0-9A-F]{3}", r.text))
            extra = f" comeet_site_links={len(co)}"
        a, s, jobs = ats.detect_from_careers(u, name) if st == 200 else (None, None, None)
        print(f"PAGE {name} {u} status={st}{extra} -> {a} {s} {len(jobs or [])}", flush=True)
        if a:
            found = (a, s, len(jobs)); break
    if not found:
        a, s, jobs = ats.detect(name)
        print(f"NAME {name} -> {a} {s} {len(jobs or [])}", flush=True)
