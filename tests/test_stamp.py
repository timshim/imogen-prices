"""Tests for scripts/stamp.py, which sets prices.json's dates after the weekly check.

Each test builds a throwaway git repository with a committed baseline, writes what the check left
behind (prices.json, check-result.json, update-summary.md) and runs the script there.

Run from the repository root: python3 -m unittest discover -s tests
"""
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "stamp.py")

BASELINE = {
    "version": "2026-10-06",
    "currency": "USD",
    "updatedAt": "2026-10-06T06:00:00Z",
    "rates": {
        "google/nano-banana-2.image-1k": 0.067,
        "kling/credit": 0.14,
        "topaz.credit": 0.25,
    },
    "details": {},
    "pricingPages": {},
}
ALL = ["google", "kling", "topaz"]
STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


def dump(data):
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


class StampTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="imogen-prices-stamp-")
        self.repo = self._tmp.name
        self.git("init", "-q")
        with open(os.path.join(self.repo, "prices.json"), "w") as file:
            file.write(dump(BASELINE))
        self.git("add", "prices.json")
        self.git("commit", "-q", "-m", "baseline")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-c", "user.name=Price Tests", "-c", "user.email=tests@example.invalid",
                        "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *args],
                       cwd=self.repo, check=True, capture_output=True, text=True)

    def run_stamp(self, prices=None, verified=None, unverified=(), summary=None, env=None):
        if prices is not None:
            with open(os.path.join(self.repo, "prices.json"), "w") as file:
                file.write(dump(prices))
        if verified is not None:
            with open(os.path.join(self.repo, "check-result.json"), "w") as file:
                json.dump({"verified": list(verified), "unverified": list(unverified)}, file)
        if summary is not None:
            with open(os.path.join(self.repo, "update-summary.md"), "w") as file:
                file.write(summary)
        result = subprocess.run([sys.executable, "-I", SCRIPT], cwd=self.repo, capture_output=True, text=True,
                                env={**os.environ, **(env or {})})
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(os.path.join(self.repo, "prices.json")) as file:
            return json.load(file), result.stdout

    def test_every_provider_confirmed_moves_the_date(self):
        data, out = self.run_stamp(verified=ALL)
        self.assertRegex(data["updatedAt"], STAMP)
        self.assertGreater(data["updatedAt"], BASELINE["updatedAt"])
        self.assertEqual(data["version"], BASELINE["version"])
        self.assertIn("Every provider was confirmed", out)

    def test_an_unconfirmed_provider_keeps_the_dates_and_the_file(self):
        before = open(os.path.join(self.repo, "prices.json")).read()
        data, out = self.run_stamp(verified=["google", "topaz"], unverified=["kling"])
        self.assertEqual(data["updatedAt"], BASELINE["updatedAt"])
        self.assertEqual(open(os.path.join(self.repo, "prices.json")).read(), before)
        self.assertIn("kling", out)

    def test_a_provider_listed_as_both_counts_as_unconfirmed(self):
        data, _ = self.run_stamp(verified=ALL, unverified=["kling"])
        self.assertEqual(data["updatedAt"], BASELINE["updatedAt"])

    def test_a_missing_or_broken_result_confirms_nothing(self):
        data, _ = self.run_stamp()
        self.assertEqual(data["updatedAt"], BASELINE["updatedAt"])
        with open(os.path.join(self.repo, "check-result.json"), "w") as file:
            file.write("not json")
        data, _ = self.run_stamp()
        self.assertEqual(data["updatedAt"], BASELINE["updatedAt"])

    def test_a_changed_rate_moves_the_date_and_version_even_if_unconfirmed(self):
        prices = copy.deepcopy(BASELINE)
        prices["rates"]["kling/credit"] = 0.15
        data, _ = self.run_stamp(prices=prices, verified=["kling"], unverified=["google", "topaz"])
        self.assertRegex(data["updatedAt"], STAMP)
        self.assertGreater(data["updatedAt"], BASELINE["updatedAt"])
        self.assertEqual(data["version"], data["updatedAt"][:10])
        self.assertEqual(data["rates"]["kling/credit"], 0.15)

    def test_dates_the_check_set_itself_are_replaced(self):
        prices = copy.deepcopy(BASELINE)
        prices["updatedAt"], prices["version"] = "2026-10-07T12:00:00Z", "2026-10-07"
        data, _ = self.run_stamp(prices=prices, verified=["google"], unverified=["kling", "topaz"])
        self.assertEqual(data["updatedAt"], BASELINE["updatedAt"])
        self.assertEqual(data["version"], BASELINE["version"])

    def test_writes_the_job_summary(self):
        summary_path = os.path.join(self.repo, "job-summary.md")
        self.run_stamp(verified=["google"], unverified=["kling", "topaz"], summary="No price changes\n\nkling: page unreadable\n",
                       env={"GITHUB_STEP_SUMMARY": summary_path})
        with open(summary_path) as file:
            text = file.read()
        self.assertIn("weren't confirmed (kling, topaz)", text)
        self.assertIn("kling: page unreadable", text)


if __name__ == "__main__":
    unittest.main()
