from scanner.sources import ats
for j in ats.FETCHERS["linkedin_links"]("https://www.geckos-games.com/", "Geckos Games") or []:
    print("J", j.title, "|", j.location, "|", len(j.description), flush=True)
