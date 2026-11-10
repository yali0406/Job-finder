from scanner.common import get
for q in ["Geckos Games", "Pazu Games", "Bengigi", "Komodor", "Tipalti"]:
    for name, url, params in [
        ("clearbit","https://autocomplete.clearbit.com/v1/companies/suggest",{"query":q}),
        ("brandfetch","https://api.brandfetch.io/v2/search/"+q,{}),
        ("ddgapi","https://api.duckduckgo.com/",{"q":q,"format":"json","no_html":1}),
        ("wikidata","https://www.wikidata.org/w/api.php",{"action":"wbsearchentities","search":q,"language":"en","format":"json","limit":3}),
    ]:
        r=get(url, params=params, timeout=10, retries=0)
        print("S", name, q, r.status_code if r is not None else None, (r.text[:300].replace("\n"," ") if r is not None else ""), flush=True)
