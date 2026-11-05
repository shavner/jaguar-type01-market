"""Tests for resolve.py on pages shaped like SMMT's (made-up numbers).

    python test_resolve.py
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import resolve


def table(top, year, rows):
    cells = lambda r: "".join(f"<td><span>{c}</span></td>" for c in r)  # noqa: E731
    return (f"<table><tbody><tr><th></th><th colspan=4><strong>{top}</strong></th><th rowspan=2>% Change</th></tr>"
            f"<tr><th><strong>MARQUE</strong></th><th>{year}</th><th>&nbsp;% Market share</th><th>{year - 1}</th>"
            f"<th>% Market share</th></tr>" + "".join(f"<tr>{cells(r)}</tr>" for r in rows) + "</tbody></table>")


def page(period="December 2027", year=2027, jaguar="812", total="2,050,000", ytd=True):
    month = table("December", year, [["Abarth", "50", "0.0", "40", "0.0", "25.0"], ["Jaguar", "99", "0.1", "0", "0.0", "-"],
                                     ["Grand Total", "90,000", "100.0", "88,000", "100.0", "2.3"]])
    year_t = table("YEAR-TO-DATE" if ytd else "Something else", year,
                   [["Abarth", "718", "0.0", "273", "0.0", "163.0"], ["Jaguar", jaguar, "0.0", "8", "0.0", "-"],
                    ["Grand Total", total, "100.0", "1,990,000", "100.0", "3.0"]])
    return (f"<html><body><script>var x = 'December 2027';</script><h1>UK CAR REGISTRATIONS</h1>"
            f"<p>New car registrations data {period}</p>{month}{year_t}</body></html>")


class ReadFigure(unittest.TestCase):
    def test_reads_year_to_date_not_month(self):
        f = resolve.read_figure(page())
        self.assertEqual(f["registrations"], 812)
        self.assertEqual(f["market_total"], 2_050_000)

    def test_thousands_separator(self):
        self.assertEqual(resolve.read_figure(page(jaguar="1,726"))["registrations"], 1726)

    def test_not_published_yet(self):
        with self.assertRaises(resolve.NotYet):
            resolve.read_figure(page(period="November 2027"))

    def test_period_only_in_a_script_does_not_count(self):
        html = page(period="November 2027").replace("var x", "var y")
        with self.assertRaises(resolve.NotYet):
            resolve.read_figure(html)

    def test_unclear_cases(self):
        for html in (page(jaguar="n/a"), page(ytd=False), page(total="95,000"),
                     page().replace("<td><span>Jaguar</span></td><td><span>812", "<td><span>Jaguar</span></td><td><span>")):
            with self.assertRaises(resolve.Unclear, msg=html[-300:]):
                resolve.read_figure(html)

    def test_missing_row_is_unclear(self):
        with self.assertRaises(resolve.Unclear):
            resolve.read_figure(page().replace("Jaguar", "Jaguars"))


class Main(unittest.TestCase):
    def run_main(self, html, today, result=None):
        d = Path(tempfile.mkdtemp())
        (d / "page.html").write_text(html, encoding="utf-8")
        (d / "result.json").write_text(json.dumps(result or {"registrations": None}), encoding="utf-8")
        with mock.patch.object(resolve, "RESULT", d / "result.json"):
            code = resolve.main(["--html", str(d / "page.html"), "--today", today])
        return code, json.loads((d / "result.json").read_text(encoding="utf-8"))

    def test_writes_result(self):
        code, r = self.run_main(page(), "2028-01-06")
        self.assertEqual((code, r["registrations"], r["how"]), (0, 812, "automatic"))

    def test_too_early_does_nothing(self):
        self.assertEqual(self.run_main(page(), "2027-01-06"), (0, {"registrations": None}))

    def test_waits_then_asks_for_help(self):
        self.assertEqual(self.run_main(page(period="November 2027"), "2028-01-10")[0], 0)
        self.assertEqual(self.run_main(page(period="November 2027"), "2028-01-20")[0], 2)

    def test_unclear_asks_for_help_at_once(self):
        self.assertEqual(self.run_main(page(jaguar="?"), "2028-01-06"), (2, {"registrations": None}))

    def test_never_overwrites(self):
        done = {"registrations": 5, "how": "manual"}
        self.assertEqual(self.run_main(page(), "2028-01-06", done), (0, done))


class Bands(unittest.TestCase):
    def test_bands_cover_every_count(self):
        m = json.loads((Path(__file__).parent / "market.json").read_text(encoding="utf-8"))
        for q in m["questions"]:
            bands = q["bands"]
            self.assertEqual(len(bands), len(q["options"]))
            self.assertEqual(bands[0][0], 0)
            self.assertIsNone(bands[-1][1])
            for (_, hi), (lo, _) in zip(bands, bands[1:]):
                self.assertEqual(hi + 1, lo)


if __name__ == "__main__":
    unittest.main(verbosity=2)
