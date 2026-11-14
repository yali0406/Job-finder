"""Temporary: find the job boards of remote-hiring companies in Europe."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from scanner.sources import ats

C = [("ElevenLabs","elevenlabs.io",["elevenlabs"]),("Samsara","samsara.com",["samsara"]),("ClickHouse","clickhouse.com",["clickhouse"]),
("Neo4j","neo4j.com",["neo4j"]),("Typeform","typeform.com",["typeform"]),("Algolia","algolia.com",["algolia"]),("Alan","alan.com",["alan"]),
("Pennylane","pennylane.com",["pennylane"]),("Temporal Technologies","temporal.io",["temporal","temporaltechnologies"]),("n8n","n8n.io",["n8n"]),
("Twilio","twilio.com",["twilio"]),("JetBrains","jetbrains.com",["jetbrains"]),("Dropbox","dropbox.com",["dropbox"]),("Databricks","databricks.com",["databricks"]),
("Sanity","sanity.io",["sanity","sanityio"]),("Snyk","snyk.io",["snyk"]),("Celonis","celonis.com",["celonis"]),("InfluxData","influxdata.com",["influxdata"]),
("Redis","redis.io",["redis","redislabs"]),("Linear","linear.app",["linear"]),("Synthesia","synthesia.io",["synthesia"]),("Customer.io","customer.io",["customerio","customer.io"]),
("GitBook","gitbook.com",["gitbook"]),("Poolside","poolside.ai",["poolside"]),("PlanetScale","planetscale.com",["planetscale"]),("CircleCI","circleci.com",["circleci"])]

def one(c):
    name, dom, slugs = c
    for sl in slugs:
        for at in ["greenhouse", "ashby", "lever", "lever_eu", "workable", "smartrecruiters"]:
            try:
                j = ats.FETCHERS[at](sl, name)
            except Exception:
                j = None
            if j:
                return name, at, sl, len(j), sum(1 for x in j if "remote" in (x.location or "").lower())
    for u in (f"https://{dom}/careers", f"https://www.{dom}/careers"):
        try:
            a, s, j = ats.detect_from_careers(u, name)
        except Exception:
            a = None
        if a:
            return name, a, s, len(j), sum(1 for x in j if "remote" in (x.location or "").lower())
    return name, None, None, 0, 0

with ThreadPoolExecutor(13) as ex:
    for f in as_completed([ex.submit(one, c) for c in C]):
        print("RESULT", json.dumps(f.result()), flush=True)
