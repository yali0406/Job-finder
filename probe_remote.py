"""Temporary: find careers pages of Israeli investment funds."""
import json
from concurrent.futures import ThreadPoolExecutor
from scanner.sources import ats

D = [("Lucid Capital","lucidcap.net",["/about/"]),("OurCrowd","ourcrowd.com",[]),("Pitango","pitango.com",[]),("Fortissimo","fortissimo.co.il",[]),
("FIMI","fimi.co.il",[]),("Qumra Capital","qumracapital.com",[]),("Aleph","aleph.vc",[]),("Vintage Investment Partners","vintage-ip.com",[]),
("JVP","jvpvc.com",[]),("TLV Partners","tlv.partners",[]),("Glilot Capital","glilotcapital.com",[]),("Entree Capital","entreecap.com",[]),
("iAngels","iangels.co",[]),("Sphera Funds","sphera-funds.com",[]),("Noked Capital","noked-capital.com",[]),("Kedma Capital","kedma.com",[]),
("More Investment House","more.co.il",[]),("Analyst IMS","analyst.co.il",[]),("Yelin Lapidot","yelin-lapidot.co.il",[]),("Meitav","meitav.co.il",[]),
("Altshuler Shaham","as-invest.co.il",[]),("IBI","ibi.co.il",[]),("Psagot","psagot.co.il",[]),("Gefen Capital","gefencapital.com",[]),
("Lool Ventures","lool.vc",[]),("Catalyst Investments","catalyst-fund.com",[]),("Ibex Investors","ibexinvestors.com",[]),("Grove Ventures","grove.vc",[]),
("Elron","elron.com",[]),("Value Base","valuebase.co.il",[]),("KCPS","kcps.co.il",[]),("Harel Finance","harel-finance.co.il",[]),
("Migdal Capital Markets","migdal-cm.co.il",[]),("Israel Growth Partners","igp.vc",[]),("Team8","team8.vc",[]),("Pico Venture Partners","pico.vc",[]),
("Mizrahi Tefahot Investment","mizrahi-tefahot.co.il",[]),("Blumberg Capital","blumberg.vc",[]),("83North","83north.com",[]),("Bessemer Israel","bvp.com",[])]

def one(c):
    name, dom, extra = c
    paths = extra + ["/careers", "/jobs", "/about", "/"]
    from scanner.common import get
    host = f"https://www.{dom}"
    r = get(host + "/", retries=0, timeout=10)
    if r is None or r.status_code >= 400:
        host = f"https://{dom}"
    for host in (host,):
        for p in paths:
            u = host + p
            try:
                a, s, jobs = ats.detect_from_careers(u, name)
                if a:
                    return name, u, a, s, len(jobs), [j.title for j in jobs[:5]]
                jobs = ats.FETCHERS["careers_page"](u, name)
                if jobs:
                    return name, u, "careers_page", u, len(jobs), [j.title for j in jobs[:6]]
            except Exception as e:
                pass
    return name, None, None, None, 0, []

from concurrent.futures import as_completed
with ThreadPoolExecutor(20) as ex:
    for f in as_completed([ex.submit(one, d) for d in D]):
        print("RESULT", json.dumps(f.result(), ensure_ascii=False), flush=True)
