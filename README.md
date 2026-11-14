# Crossing the Aisle

Tracks how Democrats and Republicans in the U.S. Congress vote on every roll call, and when members cross
the aisle. Powers [crossingtheaisle.us](https://crossingtheaisle.us).

An independent project. Not affiliated with Congress, any government office, or any party or campaign.

## How it works

1. Every three hours a GitHub Action runs `pipeline/fetch.py`. It downloads any new roll call votes from the
   House Clerk and the Senate, re-checks the five most recent votes in each chamber for corrections, and
   refreshes the member roster.
2. `pipeline/test_pipeline.py` checks the data. If any check fails, nothing is published.
3. `pipeline/build.py` writes the site into `public/` and the Action commits it.
4. Cloudflare redeploys the site whenever `main` changes (`wrangler.jsonc`, deploy command `npx wrangler deploy`).

The pipeline is plain Python 3 with no dependencies.

## Definitions

- **Split vote:** most Democrats and most Republicans in a chamber voted opposite ways.
- **Sided with the other party:** on a split vote, the member voted Yea or Nay with the other party's majority.
  Missed votes and votes of Present do not count.
- **With party %:** share of a member's Yea/Nay votes that matched their own party's majority.
- Independents are counted with the party they caucus with.

## Layout

| Path | What it is |
| --- | --- |
| `data/votes/*.json` | One file per roll call: details plus every member's position |
| `data/members.json` | Member roster |
| `data/bills.json` | Bill titles, links and summaries |
| `data/last_verify.txt` | Result of the latest re-check against the official records |
| `data/last_error.txt` | Present only when the latest update failed |
| `site/` | The page itself |
| `public/` | Built site that Cloudflare serves |
| `pipeline/` | Fetch, check and build scripts |

## Running it yourself

```
python3 pipeline/fetch.py            # get new votes
python3 pipeline/test_pipeline.py    # run the checks
python3 pipeline/build.py            # rebuild public/
python3 -m http.server -d public     # preview at http://localhost:8000
```

Optional: set `CONGRESS_API_KEY` (free from api.congress.gov) to fill in bill summaries for new bills.

## Known limits

- Covers the 119th Congress (2025-2027) only. `CONGRESS` in `pipeline/common.py` must change for the 120th.
- "Find my rep" works by state, not by ZIP code or address.

See `NOTICE.md` for data sources and credits.
