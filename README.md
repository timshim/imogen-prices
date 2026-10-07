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

1. Claude reads each provider's official pricing page and updates any rate whose published price
   changed. It only edits `prices.json`.
2. `scripts/validate.py` rejects malformed lists, added or removed rates, and implausible jumps.
3. The workflow commits the result and uploads it to imogenpro.com (`scripts/upload.sh`), then
   checks the site serves the new file.

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
run's validator rejects added or removed rates.
