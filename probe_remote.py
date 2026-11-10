"""Temporary: test Lucid Capital's careers page."""
from scanner.sources import ats
j = ats.FETCHERS["careers_page"]("https://www.lucidcap.net/about/", "Lucid Capital")
print("RESULT", None if j is None else [(x.title, x.url, x.location) for x in j])
