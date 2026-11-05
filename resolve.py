"""Resolve the market: read Jaguar's full-year UK registrations from SMMT and write result.json.

Runs every day in January from .github/workflows/resolve.yml. It does nothing before 4 January 2028 or once
result.json holds a number. It writes a figure only when it is sure: the SMMT page must show December 2027
data, a year-to-date table by marque with a 2027 column, one Jaguar row, and a plausible market total.

Exit codes: 0 = resolved, or nothing to do yet; 2 = needs a person (the workflow opens an issue).

    python resolve.py                                            # what the workflow runs
    python resolve.py --dry-run --year 2026 --period "October 2026" --today 2028-01-05   # try the parser now
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URL = "https://www.smmt.co.uk/vehicle-data/car-registrations/"
MARQUE = "Jaguar"
YEAR = 2027
START = dt.date(2028, 1, 4)     # SMMT publishes December figures in the first week of January
GIVE_UP = dt.date(2028, 1, 20)  # after this, ask a person instead of waiting
ROOT = Path(__file__).resolve().parent
RESULT = ROOT / "result.json"
UA = "Mozilla/5.0 (compatible; jaguar-type01-market/1.0; +https://github.com/shavner/jaguar-type01-market)"


class NotYet(Exception):
    """The figure is not published yet (or the page could not be read today)."""


class Unclear(Exception):
    """The page has the right period but the figure can't be read with confidence."""


class Tables(HTMLParser):
    """Every <table> as a list of rows of cell texts, and the page's visible text."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.text = [], []
        self._row = self._cell = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "table":
            self.tables.append([])
        elif tag == "tr" and self.tables:
            self._row = []
            self.tables[-1].append(self._row)
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = max(0, self._skip - 1)
        elif tag in ("td", "th") and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr":
            self._row = None

    def handle_data(self, data):
        if self._skip:
            return
        self.text.append(data)
        if self._cell is not None:
            self._cell.append(data)


def number(s: str) -> int:
    s = s.replace(",", "").replace(" ", "").strip()
    if not re.fullmatch(r"\d+", s):
        raise ValueError(s)
    return int(s)


def read_figure(html: str, year: int = YEAR, period: str | None = None, marque: str = MARQUE) -> dict:
    """The marque's year-to-date registrations for `year`, from a page whose data is for `period`."""
    period = period or f"December {year}"
    p = Tables()
    p.feed(html)
    text = " ".join(" ".join(p.text).split())
    if not re.search(r"\b" + re.escape(period) + r"\b", text, re.I):
        raise NotYet(f"the page does not show {period} data yet")

    found = []
    for rows in p.tables:
        top = " ".join(" ".join(r) for r in rows[:2])
        if not re.search(r"year[\s-]*to[\s-]*date", top, re.I):
            continue  # the month table has the same columns; only the year-to-date one counts
        head = next((r for r in rows[:3] if r and r[0].strip().upper() == "MARQUE"), None)
        if not head or str(year) not in head:
            continue
        col = head.index(str(year))
        mine = [r for r in rows if r and r[0].strip().casefold() == marque.casefold()]
        total = [r for r in rows if r and "total" in r[0].casefold()]
        if len(mine) != 1 or len(mine[0]) <= col:
            raise Unclear(f"expected one {marque} row with a {year} column, found {len(mine)}")
        try:
            value = number(mine[0][col])
            market = number(total[0][col]) if total else None
        except ValueError as e:
            raise Unclear(f"not a whole number: {e}") from None
        found.append({"registrations": value, "market_total": market, "row": " | ".join(mine[0])})

    if not found:
        raise Unclear(f"no year-to-date table by marque with a {year} column")
    if len({f["registrations"] for f in found}) != 1:
        raise Unclear(f"tables disagree: {[f['registrations'] for f in found]}")
    f = found[0]
    if period.lower().startswith("december") and f["market_total"] is not None \
            and not 1_000_000 <= f["market_total"] <= 3_000_000:
        raise Unclear(f"implausible full-year market total {f['market_total']:,}")
    return f


def fetch(url: str = URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=YEAR)
    ap.add_argument("--period", help='default "December <year>"')
    ap.add_argument("--today", help="pretend today is this date (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="print, don't write result.json")
    ap.add_argument("--html", help="read this file instead of the SMMT page")
    a = ap.parse_args(argv)
    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()

    if json.loads(RESULT.read_text(encoding="utf-8")).get("registrations") is not None and not a.dry_run:
        print("Already resolved.")
        return 0
    if today < START:
        print(f"Too early: nothing to do before {START}.")
        return 0

    try:
        html = Path(a.html).read_text(encoding="utf-8") if a.html else fetch()
        f = read_figure(html, a.year, a.period)
    except Unclear as e:
        print(f"NEEDS A PERSON: the SMMT page shows the period but the figure is unclear: {e}")
        return 2
    except (NotYet, OSError) as e:
        if today >= GIVE_UP:
            print(f"NEEDS A PERSON: still no figure on {today}: {e}")
            return 2
        print(f"Not yet: {e}")
        return 0

    out = {"registrations": f["registrations"], "source": URL, "resolved_at": today.isoformat(),
           "how": "automatic", "evidence": f["row"], "market_total": f["market_total"]}
    print(json.dumps(out, indent=2))
    if not a.dry_run:
        RESULT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
