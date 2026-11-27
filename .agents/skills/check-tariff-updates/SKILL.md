---
name: check-tariff-updates
description: >-
  Check for EV charging tariff updates in data/pt (or a prompt-defined sub-scope such as
  byoe, a specific provider like Tesla, or stale/expired plans), update prices, dates, and
  metadata according to src/tariffs/model.py, record source.last_checked when searched
  with no changes, maintain provider search tips in references/provider_memory.md, and
  ensure tariffs-validate passes for the scope.
---

# Check Tariff Updates

Use this skill when asked to check, verify, or update EV charging tariffs in `data/pt/` or a specific sub-scope (e.g., `byoe`, `tesla`, a single provider, or expired/stale plans).

Always use `uv` for Python commands (never raw `python` or `pip`).

## 1. Determine the Scope

Resolve the target YAML files from the user's prompt:
- **Full `data/pt` scope** (default when no sub-scope is specified): all `*.yaml` files in `data/pt/` and `data/pt/byoe_emsps/` (exclude `data/pt/byoe_fees/` unless regulated fees/TAR/IEC/EGME are explicitly requested).
- **`byoe` / CEME sub-scope**: `data/pt/byoe_emsps/*.yaml`.
- **Specific provider(s)** (e.g., `Tesla`, `Continente`, `Galp`): look up the exact filename in [provider_memory.md](./references/provider_memory.md) or list matching files directly with `Get-ChildItem -Recurse data/pt -Filter *<name>*.yaml` (avoid `rg`, which is not installed on Windows).
- **Stale or expired sub-scope**: run `uv run tariffs-validate data/pt` first to identify files with `[ERROR]` (lapsed `end_date`) or `[WARN]` (missing or >30-day `source.last_checked`).

## 2. Read the Provider Memory File

Before searching online, read [provider_memory.md](./references/provider_memory.md) to load known search tips, preferred URLs, how each provider typically publishes its prices (HTML, PDF, image, JS SPA, app-only), and dedicated CLI scripts for the providers in scope.

## 3. Check Each Provider in Scope

For each YAML file in scope:

1. **Special automation check**:
   - For `data/pt/tesla.yaml` (`Member` and `Non-Member` plans), run `uv run extract-supercharger-prices --update` (from `src/tariffs/supercharger/`) to fetch and update Supercharger prices, and still verify `MultiPass` / `source` metadata as needed.
2. **Verify from the primary source (never trust `search_web` summaries alone)**:
   - Read `provider_memory.md` and the target YAML file(s) in parallel.
   - Prefer `provider.source.urls` / `provider.source.url`; if absent, fall back to `provider.url` or `provider_memory.md`.
   - **`search_web` is only for discovery, NEVER for copying numbers**: `search_web` returns LLM-grounded summaries that frequently hallucinate prices, pull rates from domestic electricity tariffs, or surface stale cached PDFs (e.g. outdated EGME rates).
   - **Always inspect the primary document**:
     - Check the actual webpage HTML/DOM (many CEME landing pages display **no prices** on the page and instead link to a **PDF** or **PNG image** tariff table — always follow and read those linked PDFs/images!).
     - Use the `browser` subagent when a page is JS-rendered (empty HTML shell / SPA), requires interaction, or returns HTTP `403` to plain HTTP clients.
     - If you cannot directly read the primary page, PDF, image, or app, do **not** update prices from search snippets — treat it as unverifiable.
3. **Compare against the current YAML & apply BYOE modeling rules**:
   - **Prefer lowest complexity + boolean flags**: Under Portugal's EV charging composition rule (`final = energy + TAR + IEC + EGME + VAT + CPO`), always prefer entering the **simplest / lowest-complexity base rates** published without TAR/VAT/IEC/EGME (e.g., flat `all_day` or single `fora_vazio`/`vazio`) and set the flags (`includes_tar`, `includes_egme`, `includes_iec`, `includes_vat`) so `tariffs-compile` expands regulated fees cleanly. Only use `rates_by_voltage` (`BT`/`MT`) or `includes_tar: true` when no simpler/non-TAR rate is published.
   - **Check `includes_tar` carefully on voltage-split rates**: Splitting by `BT`/`MT` often means `TAR` is included (`includes_tar: true`), so verify the page's inclusions/exclusions text and sanity-check the magnitude against [regulated_fees.yaml](../../../data/pt/byoe_fees/regulated_fees.yaml) (e.g., PT 2026 BT Cheias TAR alone is `0.1192 €/kWh`) rather than guessing.
   - **Distinguish `activation_fee` vs. EGME vs. one-time card fees**:
     - `byoe.activation_fee` is strictly a **per-charging-session** flat fee (`unit: flat`).
     - Providers frequently label the regulated EGME connection fee (`0.1088 €/session` in [regulated_fees.yaml](../../../data/pt/byoe_fees/regulated_fees.yaml); historically `0.1572 €` or `~0.13 €` VAT-incl.) as *"Valor da Ativação"* or *"Taxa de ativação por carregamento"*. If the stated per-session fee IS the regulated EGME fee, set `includes_egme: false` and `activation_fee: 0.0` (never put `0.1088` or stale `0.1572` into `activation_fee`, or it will be double-counted). Only set `includes_egme: true` + `activation_fee: <fee>` when the provider replaces EGME with their own custom session fee (e.g., `0.15 €` or `0.08 €`), or `includes_egme: false` + `activation_fee: <extra>` if there is genuinely an extra per-session fee on top of EGME.
     - Never put a **one-time** card issuance or contract activation fee (e.g., *"Custo de ativação: 5 €"* once on signup) into `byoe.activation_fee`; record it in `plan.notes` / `source.notes` instead.
   - **Check bundles, cashback, network conditions, and payment methods**:
     - Check for multi-energy, loyalty, or partnership plans (`ENERGY_AT_HOME`, `LOYALTY_PROGRAM`, `PARTNERSHIP`) and whether **cashback / discounts** depend on conditions or **network / CPO** (e.g., own CPO network like `REPS` or `GLPP` vs. rest of `MOBIE` using `excluded_cpos`), and whether cashback applies to `CEME` energy only or `TOTAL` invoice (`applies_to: TOTAL`, `cashback: true`).
     - Check whether `payment_methods` changed (e.g., physical `RFID_CARD` discontinued in favor of `APP` only).
   - **Prices, rates & dates**: check `price`, `tiers` (`min`, `max`, `price`, `unit`, `start_after`), `byoe` rates (`all_day`, `vazio`, `cheias`, `fora_vazio`, `ponta`, `rates_by_voltage`), `activation_fee`, `opc_commission_pct`, `cost`/`months`, `discount`, `start_date`, `end_date` (verify lapsed `end_date` values — extended, replaced, or discontinued with `publish: false`), `schedule` (`1H`/`2H`/`3H`), `cycle` (`diario`/`semanal`), `regions`, `notes`, `publish`, `included_cpos`/`excluded_cpos`.
4. **Update `source` metadata accurately**:
   - Use today's ISO date (`YYYY-MM-DD`).
   - Prefer `source.urls` (list) when both a webpage and a direct tariff PDF/subpage are used (keep the main landing/pricing page first for legacy CSV compatibility).
   - **If you actually verified the primary source and found NO data updates**: add or update `source.last_checked: "YYYY-MM-DD"`. Do **not** modify `source.last_updated`.
   - **If you found and applied data updates**: update `source.last_updated: "YYYY-MM-DD"` AND set `source.last_checked: "YYYY-MM-DD"`.
   - **If you could NOT verify a primary source** (e.g., blocked, offline, or app-only without access): do **not** set `source.last_checked`; instead note the blocker in `source.notes` (if appropriate) and in [provider_memory.md](./references/provider_memory.md).
   - If `source` does not exist on the `Provider`, create it. Do not use the deprecated `Provider.updated_at` field.

## 4. Respect the Schema (`src/tariffs/model.py`)

When editing YAML files, strictly follow [model.py](../../../src/tariffs/model.py) (and [regulated_fees.py](../../../src/tariffs/regulated_fees.py)):
- `Tariff` must define either `price` or `tiers` (never both), unless `byoe: true`.
- `ByoeConfig` cannot mix top-level rates (`all_day`, `vazio`, `cheias`, `fora_vazio`, `ponta`) with `rates_by_voltage` / `rates`.
- `schedule: 2H` forbids `ponta`; `schedule: 1H` uses `all_day`.
- `Source` uses `url` or `urls`, `last_checked`, `last_updated`, `notes` (ISO `YYYY-MM-DD` strings).
- Preserve existing YAML comments, formatting, and anchors (such as `_templates` in `data/pt/tesla.yaml`).

## 5. Update the Memory File

After checking each provider in scope, update [provider_memory.md](./references/provider_memory.md) with:
- How the provider typically presents its tariff data (e.g., HTML table on page, linked PDF, PNG image, JS-rendered SPA, bot-protected/403 requiring browser, app/login only) — noting that this may change over time
- Exact pricing page URL or PDF/image link if different from `provider.url`
- Plan-specific naming quirks, cashback/bundle tiers, EGME/activation-fee labeling quirks, or VAT/TAR inclusion notes

## 6. Validate the Scope

Run validation on all files in scope (or the specific file/directory):

```bash
uv run tariffs-validate <path-or-directory>
```

For example:
- `uv run tariffs-validate data/pt/byoe_emsps`
- `uv run tariffs-validate data/pt/tesla.yaml`
- `uv run tariffs-validate data/pt`

Validation **must pass** (exit code `0`, no `[ERROR]`) for all plans in the scope. If you modified tariff data across `data/pt`, also consider running `uv run tariffs-compile` and `uv run pytest` if requested or if compilation artifacts should stay in sync.
