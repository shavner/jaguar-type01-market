# Jaguar Type 01 market

A class forecast, made in Fall 2026, of how many new Jaguars will be registered in the UK in 2027. The page
shows every team's bet now and fills in the answer and the winners by itself in January 2028, when SMMT
publishes the full-year figures.

Page: https://shavner.github.io/jaguar-type01-market/

## Files

| File | What it is |
|---|---|
| `index.html` | The page. Reads `market.json` and `result.json`. |
| `market.json` | The question and every team's bets, downloaded from the market desk after class. Frozen: its commit history is the proof that no bet changed. |
| `result.json` | `{"registrations": null}` until the answer is known. |
| `reveal.ics` | Calendar invite for 10 January 2028, linked from the page. |
| `resolve.py` | Reads Jaguar's 2027 year-to-date registrations from SMMT's car registrations page and writes `result.json`. Standard library only. |
| `test_resolve.py` | `python test_resolve.py` |
| `.github/workflows/resolve.yml` | Runs `resolve.py` daily in January; commits the result and republishes the page, or opens an issue. |
| `.github/workflows/keepalive.yml` | Monthly heartbeat commit, so GitHub doesn't switch off the January job (it disables scheduled jobs after 60 days without activity). |
| `.github/workflows/pages.yml` | Publishes the page on every push. |

## After class (once)

1. On the market desk's instructor page, press **Close betting**, then **Download bets**. It saves `market.json`.
2. Replace `market.json` here with it, commit and push. The page now shows the class forecast and every team's bet.
   Don't change `market.json` after that.

## January 2028

Nothing to do if it works. `resolve.py` writes a figure only when the SMMT page shows December 2027 data and a
year-to-date table by marque with exactly one Jaguar row; anything less certain and it waits, then asks.

If GitHub emails you an issue titled **Resolve the Type 01 market by hand**, look up the figure, edit
`result.json` on GitHub as the issue shows, and commit. The page republishes itself.

To check the parser against today's SMMT page:

```bash
python resolve.py --dry-run --year 2026 --period "October 2026" --today 2028-01-05
```

(use the month the page currently shows).
