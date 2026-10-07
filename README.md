# imogen-prices

The price list used by [Imogen Pro](https://imogenpro.com), a Mac app for generating and managing
AI images and video. The app downloads it from `https://imogenpro.com/catalog/prices.json` at most
once a day, or when you click **Refresh** in Settings → Pricing, and uses it to estimate and record
what each generation costs. This repo is the list's source; the workflow publishes it to the site.

- **`rates`:** US dollar prices, keyed by rate ID.
- **`details`:** what each rate is (label, unit, provider, model).
- **`pricingPages`:** each provider's official pricing page.
- **`updatedAt`:** when the prices were last checked. Imogen Pro shows it as "Prices as of …", and
  only applies a list whose `updatedAt` is later than the one it has.

Costs already recorded in a project never change when this list does.

## How it's kept current

A scheduled workflow (`.github/workflows/update-prices.yml`) runs every Monday:

1. `scripts/fetch_sources.py` downloads each provider's official pricing pages, listed in
   `sources.json`, and saves them as text. These are plain downloads without JavaScript, so a
   page belongs in `sources.json` only if its prices are in the HTML.
2. Claude reads those pages and updates any rate whose published price changed. It writes
   `check-result.json`, listing which providers it confirmed, and a summary of what it changed
   or couldn't confirm.
3. `scripts/stamp.py` sets the dates. A changed rate moves `updatedAt` to now and `version` to
   today. With no changes, `updatedAt` only moves when every provider was confirmed, so
   "Prices as of …" in the app never claims a check that didn't happen.
4. `scripts/validate.py` rejects malformed lists, added or removed rates, and implausible jumps.
5. The workflow commits the result and uploads it to imogenpro.com (`scripts/upload.sh`), then
   checks the site serves the new file. The run's summary in the Actions tab shows what was
   changed and what couldn't be confirmed.

A hand edit to `prices.json` pushed to `main` is validated and uploaded the same way. You can also
run the weekly check from the Actions tab (**Update prices → Run workflow**).

Repository secrets:

- `ANTHROPIC_API_KEY`, or `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`, for the weekly check.
- `CATALOG_DEPLOY_KEY`: the private SSH key of the server's `catalog` user. On the server it's
  restricted to `rrsync -wo /var/www/imogenpro.com/catalog/`, so it can only write files into the
  catalog folder: no shell, no reading, nothing outside that folder.

New rates (for new models) come from Imogen Pro itself:
`"/Applications/Imogen Pro.app/Contents/MacOS/Imogen Pro" --export-prices -` prints the full list
from the app's built-in rates. Add the new rate IDs and their `details` here by hand: the weekly
run's validator rejects added or removed rates. If the provider is new, add its pricing pages to
`sources.json` too.

Tests: `python3 -m unittest discover -s tests`.
