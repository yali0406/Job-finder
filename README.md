# Job finder

Personal job scanner. Every hour (07:00-23:00 Israel time) a GitHub Action collects jobs from
company career pages (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Comeet), Israeli VC
portfolio job boards (Getro) and LinkedIn's public job search (every 3 hours), keeps the relevant
ones, scores new ones against the candidate profile with Claude, and publishes `docs/` to Cloudflare Pages.

- `sources.yaml`: companies, gaming companies, VC boards, LinkedIn queries
- `scanner/match.py`: title filter + scoring
- `docs/index.html`: the site; "new" = found since your previous visit (stored in your browser)

## Setup
1. Repository secrets: `ANTHROPIC_API_KEY`, `CANDIDATE_PROFILE` (contents of a local `profile.md`, which is gitignored).
2. Cloudflare: create a Pages project named `job-finder` (Direct Upload, not connected to git),
   an API token with "Cloudflare Pages: Edit", and add secrets `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.
   Optional: protect the site with Cloudflare Access (Zero Trust, free) so only your email can open it.
3. Actions → "scan jobs" → Run workflow, for the first run.

Local run: `pip install -r requirements.txt && python -m scanner.main --linkedin no`
