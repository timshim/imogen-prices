# imogen-prices

The price list used by [Imogen](https://github.com/timshim/Imogen), a Mac app for generating and
managing AI images and video. Imogen downloads `prices.json` at most once a day, or when you click
**Refresh** in Settings → Pricing, and uses it to estimate and record what each generation costs.

- **`rates`:** US dollar prices, keyed by rate ID.
- **`details`:** what each rate is (label, unit, provider, model).
- **`pricingPages`:** each provider's official pricing page.
- **`updatedAt`:** when the prices were last checked. Imogen shows it as "Prices as of …".

Costs already recorded in a project never change when this list does.

## How it's kept current

A scheduled workflow (`.github/workflows/update-prices.yml`) runs every Monday:

1. Claude reads each provider's official pricing page and updates any rate whose published price
   changed. It only edits `prices.json`.
2. `scripts/validate.py` rejects malformed lists, added or removed rates, and implausible jumps.
3. The workflow commits the result.

You can also run it from the Actions tab (**Update prices → Run workflow**). It needs one
repository secret: `ANTHROPIC_API_KEY`, or `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`.

New rates (for new models) come from Imogen itself:
`Imogen.app/Contents/MacOS/Imogen --export-prices prices.json` writes the full list from the app's
built-in rates.
