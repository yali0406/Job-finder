"""One-off check of candidate job boards for remote-first companies."""
import re
from scanner.sources.ats import FETCHERS
from scanner.sources.remote import eligible

C = {
 "Automattic": [("greenhouse","automatticcareers"),("greenhouse","automattic"),("ashby","automattic")],
 "Doist": [("greenhouse","doist"),("ashby","doist"),("lever","doist")],
 "Deel": [("ashby","deel"),("greenhouse","deel"),("lever","deel")],
 "Wikimedia Foundation": [("greenhouse","wikimedia"),("lever","wikimedia")],
 "DuckDuckGo": [("ashby","duck-duck-go"),("ashby","duckduckgo"),("greenhouse","duckduckgo")],
 "Toggl": [("greenhouse","toggl"),("ashby","toggl"),("workable","toggl")],
 "Hotjar": [("greenhouse","hotjar"),("greenhouse","contentsquare")],
 "Sourcegraph": [("ashby","sourcegraph"),("greenhouse","sourcegraph91")],
 "Kraken": [("ashby","kraken.com"),("lever","kraken")],
 "HashiCorp": [("greenhouse","hashicorp")],
 "Chainlink Labs": [("ashby","chainlink-labs"),("greenhouse","chainlinklabs"),("lever","chainlink")],
 "Consensys": [("greenhouse","consensys"),("lever","consensys")],
 "Ledger": [("lever","ledger"),("greenhouse","ledger"),("ashby","ledger")],
 "Circle": [("greenhouse","circle"),("ashby","circle")],
 "OKX": [("lever","okx"),("ashby","okx"),("greenhouse","okx")],
 "Binance": [("lever","binance"),("ashby","binance")],
 "Crypto.com": [("lever","crypto"),("greenhouse","cryptocom")],
 "Coinbase": [("greenhouse","coinbase")],
 "Bybit": [("lever","bybit"),("ashby","bybit")],
 "Polygon Labs": [("greenhouse","polygontechnology"),("ashby","polygon-labs")],
 "Uniswap Labs": [("ashby","uniswap"),("greenhouse","uniswaplabs")],
 "Alchemy": [("ashby","alchemy"),("greenhouse","alchemy")],
 "Phantom": [("ashby","phantom"),("greenhouse","phantom")],
 "Nethermind": [("ashby","nethermind"),("greenhouse","nethermind")],
 "Ethereum Foundation": [("ashby","ethereum-foundation"),("lever","ethereumfoundation")],
 "Mattermost": [("lever","mattermost"),("greenhouse","mattermost")],
 "Ghost": [("ashby","ghost"),("greenhouse","ghost")],
 "Loom": [("greenhouse","loom")],
 "Turing": [("greenhouse","turing"),("lever","turing")],
 "Andela": [("greenhouse","andela"),("lever","andela")],
 "Toptal": [("lever","toptal")],
 "X-Team": [("lever","x-team"),("greenhouse","xteam")],
 "Revolut": [("lever","revolut"),("greenhouse","revolut")],
 "Pipedrive": [("greenhouse","pipedrive"),("lever","pipedrive")],
 "Wise": [("greenhouse","transferwise"),("lever","wise")],
 "Hostinger": [("lever","hostinger"),("greenhouse","hostinger"),("workable","hostinger")],
 "Contentful": [("greenhouse","contentful")],
 "Typeform": [("greenhouse","typeform"),("lever","typeform")],
 "Factorial": [("greenhouse","factorial"),("lever","factorial")],
 "n8n": [("ashby","n8n")],
 "Hugging Face": [("ashby","huggingface"),("workable","huggingface")],
 "Mistral AI": [("lever","mistral"),("ashby","mistral")],
 "Remote Technology": [("greenhouse","remote")],
 "Paddle": [("ashby","paddle"),("greenhouse","paddle")],
 "Plaid": [("lever","plaid")],
 "Brex": [("greenhouse","brex")],
 "Ramp": [("ashby","ramp")],
 "Airwallex": [("ashby","airwallex"),("greenhouse","airwallex")],
 "Rapyd Global": [("greenhouse","rapyd")],
 "Payhawk": [("greenhouse","payhawk"),("lever","payhawk")],
 "Pleo": [("ashby","pleo"),("greenhouse","pleo")],
 "Ebanx": [("lever","ebanx"),("greenhouse","ebanx")],
 "Thunes": [("lever","thunes"),("greenhouse","thunes")],
 "Nium": [("lever","nium"),("greenhouse","nium")],
 "Checkout.com": [("greenhouse","checkoutcom"),("greenhouse","checkout")],
 "Mollie": [("greenhouse","mollie"),("ashby","mollie")],
 "Adyen": [("greenhouse","adyen")],
 "SumUp": [("greenhouse","sumup")],
 "Rippling": [("ashby","rippling")],
 "GitHub": [("greenhouse","github")],
 "Canva": [("lever","canva"),("greenhouse","canva")],
 "Miro": [("greenhouse","miro"),("greenhouse","realtimeboardglobal")],
 "Hubstaff": [("lever","hubstaff"),("workable","hubstaff")],
 "Teamwork": [("greenhouse","teamwork"),("workable","teamwork")],
 "1Password": [("ashby","1password"),("lever","1password")],
 "Tailscale": [("greenhouse","tailscale"),("ashby","tailscale")],
 "Cloudflare": [("greenhouse","cloudflare")],
 "Datadog": [("greenhouse","datadog")],
}
for name, cands in C.items():
    best = None
    for ats, slug in cands:
        try:
            jobs = FETCHERS[ats](slug, name)
        except Exception:
            jobs = None
        if jobs:
            rem = [j for j in jobs if re.search(r"remote|anywhere|worldwide|distributed", j.location or "", re.I) and eligible(j.location)]
            best = (ats, slug, len(jobs), len(rem))
            break
    print(f"PROBE {name} | {best}")
