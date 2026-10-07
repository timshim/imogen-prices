"""Sets prices.json's `updatedAt` and `version` after the weekly check, from what the check
reports in check-result.json, rather than trusting the model with the dates:

- If any rate changed, `updatedAt` becomes now and `version` today, so the app applies the list.
- If no rate changed but every provider with rates was confirmed against its official sources,
  `updatedAt` becomes now: the prices are as of today.
- Otherwise both keep their committed values, so "Prices as of …" never claims a check that
  didn't happen.

In GitHub Actions it also adds the decision and update-summary.md to the job summary.

Run from the repository root after the check: python3 scripts/stamp.py
"""
import json
import os
import re
import subprocess
from datetime import datetime, timezone


def provider(rate_id):
    return re.split(r"[/.]", rate_id, maxsplit=1)[0]


def confirmed_providers():
    try:
        with open("check-result.json") as file:
            result = json.load(file)
        verified = {p for p in result.get("verified", []) if isinstance(p, str)}
        unverified = {p for p in result.get("unverified", []) if isinstance(p, str)}
        return verified - unverified
    except (OSError, ValueError, AttributeError):
        return set()


def main(now=None):
    now = now or datetime.now(timezone.utc)
    with open("prices.json") as file:
        text = file.read()
    new = json.loads(text)
    old = json.loads(subprocess.run(["git", "show", "HEAD:prices.json"], capture_output=True, text=True, check=True).stdout)

    # The dates are this script's to set.
    new["updatedAt"], new["version"] = old["updatedAt"], old["version"]
    changed = sorted(key for key in new["rates"] if new["rates"][key] != old["rates"].get(key))
    providers = sorted({provider(key) for key in new["rates"]})
    unconfirmed = sorted(set(providers) - confirmed_providers())

    stamp = now.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    if changed:
        new["updatedAt"], new["version"] = stamp, now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        decision = f"{len(changed)} rate(s) changed, so updatedAt is now {stamp} and version {new['version']}."
    elif not unconfirmed:
        new["updatedAt"] = stamp
        decision = f"Every provider was confirmed, so updatedAt is now {stamp}."
    else:
        decision = f"No rate changed and {len(unconfirmed)} provider(s) weren't confirmed ({', '.join(unconfirmed)}), so the dates stay as they were."

    updated = json.dumps(new, indent=2, sort_keys=True) + "\n"
    if updated != text:
        with open("prices.json", "w") as file:
            file.write(updated)
    print(decision)

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open("update-summary.md") as file:
                summary = file.read()
        except OSError:
            summary = "(The check didn't write update-summary.md.)"
        with open(summary_path, "a") as file:
            file.write(f"## Price check\n\n{decision}\n\n{summary}\n")


if __name__ == "__main__":
    main()
