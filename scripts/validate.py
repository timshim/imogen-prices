"""Checks prices.json before it's published: the shape the Imogen app reads, sane values,
and no rates added or removed (new rates only come from Imogen releases)."""
import json, subprocess, sys
from datetime import datetime

def load(text):
    data = json.loads(text)
    assert isinstance(data.get("version"), str) and data["version"], "version missing"
    assert data.get("currency") == "USD", "currency must be USD"
    datetime.fromisoformat(data["updatedAt"].replace("Z", "+00:00"))
    rates = data["rates"]
    assert isinstance(rates, dict) and rates, "rates missing"
    for key, value in rates.items():
        assert isinstance(value, (int, float)) and not isinstance(value, bool), f"{key} is not a number"
        assert 0 < value < 1000, f"{key} = {value} is out of range"
    return data

new = load(open("prices.json").read())
old = load(subprocess.run(["git", "show", "HEAD:prices.json"], capture_output=True, text=True, check=True).stdout)
assert set(new["rates"]) == set(old["rates"]), "rates were added or removed"
for key in new["rates"]:
    before, after = old["rates"][key], new["rates"][key]
    # A price moving more than 5x either way is almost certainly a unit mistake.
    assert after / before <= 5 and before / after <= 5, f"{key} changed {before} -> {after}; check the units"
changed = [k for k in new["rates"] if new["rates"][k] != old["rates"][k]]
print(f"OK: {len(new['rates'])} rates, {len(changed)} changed: {', '.join(changed) or 'none'}")
