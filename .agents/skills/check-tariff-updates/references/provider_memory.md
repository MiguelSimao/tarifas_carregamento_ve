# Provider & Plan Search Memory

This file tracks provider-specific URLs, how each provider typically publishes its tariff data, and known quirks to speed up future tariff update checks.
Update this file whenever you discover a better URL, a PDF/image link, a JS-rendering or bot-protection quirk, an app-only price, or a plan-specific quirk.

> **Note**: How each provider delivers its tariff data (HTML table, PDF, image, JS widget, or app-only) reflects what was observed during checks and **may change over time**. Always verify directly from the primary page/document rather than relying on search summaries alone.

## General Tips

- **Preferred source field**: Always check `provider.source.urls` / `provider.source.url` first, then `provider.url`.
- **Never copy numbers from `search_web` alone**: `search_web` returns LLM summaries that can hallucinate prices, pull domestic tariffs, or cite outdated cached PDFs. Always read the actual webpage HTML/DOM, linked PDF, or image.
- **EGME vs. `activation_fee`**: Cross-check any *"Valor da Ativação"* against `egme_connection` (`0.1088 €`, historically `0.1572 €` or `~0.13 €` VAT-incl.) in `data/pt/byoe_fees/regulated_fees.yaml`. Only set `byoe.activation_fee > 0` for non-EGME per-session fees (or custom fees replacing EGME when `includes_egme: true`). One-time card signup fees go in `notes`, not `byoe.activation_fee`.
- **Validation command**: `uv run tariffs-validate <scope_path>` (warnings about missing/stale `source.last_checked` are non-fatal; lapsed `end_date` or schema errors fail validation).
- **Tesla Superchargers**: Use `uv run extract-supercharger-prices --update` (fetches from `suc-tracker.eu` and updates `Member` and `Non-Member` in `data/pt/tesla.yaml` while preserving YAML anchors).

---

## Standard Plans (`data/pt/*.yaml`)

| File | Provider | Plans | Known URL / Source | How Data Is Typically Provided & Quirks |
| :--- | :--- | :--- | :--- | :--- |
| `atlante.yaml` | Atlante | `Base`, `Atlante GO`, `AD-HOC` | `https://atlante.energy/pt-pt/tarifas-de-energia/` | **HTML page** (also verify ad-hoc/subscription details in `myAtlante` app). |
| `continente.yaml` | Continente | `Base`, `AD-HOC` | `https://feed.continente.pt/plug-charge` | **HTML page** (`provider.url`); check Continente Plug & Charge page for AC/DC tiered prices. |
| `dte.yaml` | DTE | `AD-HOC` | — | Missing `url` and `source.url`; search DTE EV charging Portugal. |
| `edp.yaml` | EDP | `EDP-UVE Flat` | — | Missing `url` and `source.url`; check EDP Mobilidade Elétrica / UVE partnership terms. |
| `electromaps.yaml` | Electromaps | `Base` | — | Missing `url` and `source.url`; check Electromaps Portugal pricing/app. |
| `electroverse.yaml` | Electroverse | `Base`, `Ionity Subscription`, `Powerdot Subscription` | `https://electroverse.com/` | Uses `provider.url`; check Octopus Electroverse subscriptions & Portugal pricing (often JS-rendered / app). |
| `elli.yaml` | Elli | `Base` | — | Missing `url` and `source.url`; check Elli Drive / Charging tariffs for PT. |
| `enable_mobility.yaml` | Enable Mobility | `AD-HOC` | `https://www.enable-mobility.com/` | **HTML / browser** (raw HTTP clients may hit SSL cert chain error; use browser). |
| `evio.yaml` | Evio | `EVIO BP`, `AD-HOC` | — | Missing `url` and `source.url`; check Evio / BP partnership and ad-hoc pricing (JS SPA / app). |
| `galp.yaml` | Galp | `AD-HOC` | — | Missing `url` and `source.url`; check Galp Electric ad-hoc rates. |
| `goldenergy.yaml` | Goldenergy | `Tudo Incluído`, `Tudo Incluído - Casa` | `https://goldenergy.pt/mobilidade-eletrica/` | **HTML page + linked PDF** (`tc_mobilidade_eletrica.pdf`); shares page with `byoe_emsps/goldenergy.yaml`. |
| `helexia.yaml` | Helexia | `AD-HOC` | — | Missing `url` and `source.url`; check Helexia Portugal charging tariffs. |
| `highgreenpower.yaml` | High Green Power OPC | `Base` | — | Missing `url` and `source.url`; check High Green Power OPC rates. |
| `iberdrola_bp.yaml` | Iberdrola/BP | `AD-HOC` | — | Missing `url` and `source.url`; check Iberdrola / BP Pulse Portugal ad-hoc rates. |
| `ionity.yaml` | Ionity | `IONITY Direct`, `IONITY App`, `IONITY Power`, `IONITY Motion`, `IONITY Power 365`, `IONITY Motion 365` | — | Missing `url` and `source.url`; check Ionity Portugal pricing page for subscriptions & direct rates (JS-rendered). |
| `moeve.yaml` | Moeve | `AD-HOC`, `App` | `https://pt.moeveglobal.com/pt/utilizacao/produtos-servicos/carregamento-eletrico` | **HTML + linked PDF**; formerly Cepsa (`pt.cepsa.com` redirects to `pt.moeveglobal.com`). |
| `powerdot.yaml` | Powerdot | `AD-HOC` | — | Missing `url` and `source.url`; check Powerdot Portugal ad-hoc rates. |
| `prio.yaml` | Prio | `AD-HOC` | — | Missing `url` and `source.url`; check Prio Electric ad-hoc rates. |
| `remo.yaml` | REMO | `AD-HOC` | — | Missing `url` and `source.url`; check REMO EV charging Portugal. |
| `telpark.yaml` | Telpark | `Base` | — | **App-only** (`com.delaware.empark`); prices derived from Telpark app. |
| `tesla.yaml` | Tesla | `Non-Member`, `Member`, `MultiPass` | — | **CLI script** (`uv run extract-supercharger-prices --update`) for `Member` & `Non-Member`; check `MultiPass` separately. Preserve `_supercharger_mapping` and `_templates` YAML anchors. |
| `wenea.yaml` | Wenea | `Wenea (Confirmar App)` | — | **App-only**; plan name notes "Confirmar App" — requires checking the Wenea app. |
| `zunder.yaml` | Zunder | `Base` | `https://www.zunder.com/pt-pt/utilizador-ve/#tarifas` | **HTML table** on `/pt-pt/utilizador-ve/#tarifas` (Portugal network `0.59 €/kWh`, VAT 23% incl.; Easy/Pro do not apply in PT). |

---

## BYOE eMSP Plans (`data/pt/byoe_emsps/*.yaml`)

| File | Provider | Plans | Known `source.urls` | How Data Is Typically Provided (May Change) | Search Tips & Quirks |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `acp_electric.yaml` | ACP Electric | `CEME Base`, `CEME Sócio` | `https://www.acp.pt/veiculos/eletricos/app-e-cartao-acp-electric/para-socios-e-nao-socios` | **HTML page** (redirects from `/eletricos/...`; Sócio rate also on `/poupanca-no-carregamento`). | Custom `0.15 €` activation fee replaces EGME (`includes_egme: true`). Verify both sócio and non-sócio rates. |
| `atlante.yaml` | Atlante | `CEME` | `https://atlante.energy/pt-pt/tarifas-de-energia/` | **HTML page** (lists `0.12 €/kWh` CEME base rate directly in text). | Also lists all-inclusive (`0.55 €`) and Atlante GO (`0.49 €`) plans on same page (`data/pt/atlante.yaml`). |
| `bluecharge.yaml` | BlueCharge | `CEME (Diário)`, `CEME (Semanal)` | `https://www.bluecharge.pt/` | **Linked PNG image** (`wp-content/uploads/.../tarifario.png`) + Condições Gerais PDF; no prices in HTML text. | Site has previously suspended new card issuance; inspect the linked `tarifario.png` image directly (or client area if removed). |
| `charge2go.yaml` | Charge2Go | `CEME (Diário)`, `CEME (Semanal)` | `https://charge2go.pt/tarifarios/` | **HTML / PDF / JS widget** (main page shows EGME `0.1088` and links `Condicoes_Gerais_Contrato_Charge2Go_*.pdf`; kWh rates may require browser rendering or client/signup flow). | Ecochoice group brand; verify `fora_vazio`/`vazio` with browser if absent from static HTML. |
| `chargemap.yaml` | Chargemap | `CEME` | `https://pt.chargemap.com/` | **Dynamic / App-only** (`chargemap.com/pt-pt/` has no static CEME rate table). | Currently `publish: false` (note: clients not applying 10% additional CPO price increase). |
| `edp.yaml` | EDP | `CEME`, `CEME Bi-horário`, `CEME Casa`, `CEME Casa Bi-horário`, `CEME Casa + UVE`, `CEME Casa + UVE Bi-horário`, `CEME UVE`, `CEME UVE Bi-horário` | `https://www.edp.pt/particulares/servicos/mobilidade-eletrica/carregar-fora-de-casa/` | **HTML page + interactive/JS sections** (static HTML only surfaces one headline figure; full Base/Bi-horário/Casa/UVE matrix needs browser inspection). | Check all 8 variants (1H/2H, Casa -20%, UVE -10%, Casa+UVE -30%; `EDPC` excluded on discounted plans). |
| `enable_mobility.yaml` | Enable Mobility | `CEME` | `https://www.enable-mobility.com/` | **HTML page via browser** (raw Python HTTP clients hit SSL verification error). | Mainland PT (`0.12 €/kWh`) differs from Autonomous Regions RAA/RAM (`0.15 €/kWh`); check both. |
| `evaz.yaml` | eVaz | `CEME Move Base (Diário)`, `CEME Move Base (Semanal)`, `CEME Move Volt / Home (Diário)`, `CEME Move Volt / Home (Semanal)` | `https://www.evaz.energy/solutions/plans/mobility/` | **HTML page** (rates appear directly in HTML text). | Indexed monthly to OMIE; check Base vs. Volt/Home (-5%) and daily/weekly cycles. |
| `evio.yaml` | Evio | `CEME` | `https://ceme.go-evio.com/pt/site-ceme` | **JS-rendered SPA** (static HTML is ~600B shell; requires `browser` subagent). | Custom `0.15 €` session fee replaces EGME (`includes_egme: true`). |
| `evpower.yaml` | EVPower | `CEME` | `https://signup.evpower.pt/` | **Signup HTML page / App** (`signup.evpower.pt` surfaces headline rate in HTML; detailed TOU rates may require signup flow/app). | Check `signup.evpower.pt` with browser to see full 2H `fora_vazio`/`vazio` breakdown. |
| `ezu.yaml` | EZU / AB Energia | `CEME Cartão`, `CEME App` | `https://www.ezu.pt/ceme` | **JS-rendered SPA + Mobile App** (static HTML is ~3KB shell; requires `browser` subagent or `AB Energia \| EZU` app). | `CEME App` promo (`end_date: "2026-08-31"`) set to `publish: false` after lapsing; re-check if new promo launched. |
| `factorenergia.yaml` | FactorEnergia | `CEME (Diário)`, `CEME (Semanal)` | `https://www.factorenergia.pt/cartao-mobilidade-eletrica/` | **Linked PDF only** (`wp-content/uploads/.../Tabela-precos-vecard-*.pdf` labeled `preçário`). **No prices on the HTML page.** | Always open the linked `Tabela-precos-vecard-*.pdf` (2H Bi-Horária with TAR included, `diario` & `semanal`; never trust search snippets showing 3H domestic rates). |
| `galp.yaml` | Galp | `CEME Base/App/Casa (Diário/Semanal)` | `https://www.galp.com/pt/pt/particulares/estrada/cartao-galpelectric-info` | **Linked PDF** (`galp-electric-tabela-precos-descontos-*.pdf` labeled `Consulte o tarifário do cartão Galp Electric`); landing page only shows headline discounts. | PDF gives reference `fora_vazio`/`vazio` (with TAR), `+ 0.1088 €` EGME (`includes_egme: false`), and effective date. Also check App/Casa % discounts on page (`GLPP` has higher discount). |
| `goldenergy.yaml` | Goldenergy | `CEME Base`, `CEME Casa` | `https://goldenergy.pt/mobilidade-eletrica/` | **HTML table + linked PDF** (`tc_mobilidade_eletrica.pdf`). | Check both CEME Base/Casa (`includes_tar: true`) and standard `Tudo Incluído` plans (`data/pt/goldenergy.yaml`). |
| `iberdrola.yaml` | Iberdrola | `CEME Base`, `CEME Casa` | `https://www.iberdrola.pt/casa/mobilidade-eletrica/carregar-fora-casa` | **Bot-protected HTML/PDF (`403` to scripts)** — use `browser` subagent. | Check CEME Base and Cliente Eletricidade Casa (-20%). |
| `meo_energia.yaml` | MEO Energia | `CEME M4e/M5e`, `CEME M2e/M3e`, `CEME Colaboradores` | `https://www.meoenergia.pt/mobilidade-eletrica` | **JS-rendered / interactive HTML** (static fetch gets minimal text; use `browser` subagent). | Check bundle tiers (M4e/M5e, M2e/M3e, Colaboradores) and note dynamic 15-min OMIE tariff option. |
| `miio.yaml` | Miio | `CEME Base (Diário)`, `CEME Base (Semanal)`, `CEME One (Diário)`, `CEME One (Semanal)` | `https://www.miio.com/pt/prices/charging` | **HTML page** (prices & Miio One discount displayed directly on page). | Verify whether `includes_egme` / `includes_tar` changed alongside `fora_vazio`/`vazio` and Miio One subscription cost. |
| `mobismart.yaml` | Mobismart | `CEME Active`, `CEME Pré-Pago` | `https://mobismart.pt/pedir-cartao/` | **Linked PDF only** (`/precos/EVCE-Tabela-precos-CEME-energia_PT.pdf` labeled `tabela de preços`). **No prices on the HTML page.** | PDF lists `Plano PÓS-PAGO (12 meses)` (`CEME Active`, 5 € **one-time** activation fee — keep `byoe.activation_fee: 0.0`!) and `Plano PRÉ-PAGO`. |
| `moeve.yaml` | Moeve | `CEME App GOW`, `CEME App GOW Deco`, `CEME Cartão` | `https://pt.moeveglobal.com/pt/utilizacao/produtos-servicos/carregamento-eletrico` | **Linked PDF** (`condicoes-comerciais-*.pdf` labeled `Condições Comerciais CEME`); `pt.cepsa.com` redirects to `pt.moeveglobal.com`. | Check `BT`/`MT` rates in PDF, `0.08 €` activation fee (`includes_egme: true`), and App GOW / Deco cashback (`-0.02` / `-0.04 €/kWh`). |
| `okeana.yaml` | Okeana | `CEME` | `https://okeana.pt/` | **Bot-protected (`403` to scripts)** — use `browser` subagent; CEME rates may not be publicly listed. | If rates remain private/unlisted even in browser, leave `source.last_checked` unset and note blocker. |
| `prio.yaml` | Prio | `CEME (kWh)` | `https://www.prio.pt/pt/mobilidade-eletrica/informacao-faturacao-uve_427.html` | **Linked PDF** (`https://www.prio.pt/downloads/file422_pt.pdf` labeled `Consultar Tarifas Kwh`); HTML page has only general info. | Open `file422_pt.pdf` directly; Prio has historically priced `fora_vazio` lower than `vazio` (`includes_tar: false`). |
| `repsol.yaml` | Repsol | `CEME`, `CEME Motor e Luz`, `CEME Motor, Luz e Calor` | `https://www.repsol.pt/particulares/estrada/mobilidade-eletrica/precos-carregamento-eletrico/` | **HTML pages + FAQ** (`/precos-carregamento-eletrico/`, `/cartao-mobilidade-eletrica/`, `/beneficios/plano-motor*`). | `Valor da Ativação` (`0.1088 €`) is **EGME** (`includes_egme: false`, `activation_fee: 0.0`). Physical cards discontinued 2025-05-12 (`APP` only). My Repsol cashback (10%/15%/20% on `REPS`, halved to 5%/7.5%/10% on other `MOBIE` CPOs) applies to `TOTAL` invoice. |
| `via_verde.yaml` | Via Verde | `CEME EcoChoice` | `https://www.viaverde.pt/particulares/via-verde/servicos/via-verde-electric` | **HTML page** (redirects from `/onde-e-como-usar/...`; flat `0.148 €/kWh` in HTML text). | `APP` only; EcoChoice partner (`includes_tar: false`). |
| `zunder.yaml` | Zunder | `CEME` | `https://www.zunder.com/pt-pt/utilizador-ve/#tarifas` | **HTML table** under `Roaming: carregar fora da rede Zunder -> Portugal` on `/pt-pt/utilizador-ve/#tarifas` (not on `/pt-pt/` homepage). | Splits CEME rate by `BT`/`MT` (no flat rate published) while explicitly listing `TAR`, `IEC`, and `EGME (0.13 €)` separately under `Impostos` (`includes_tar: false`). Also check `data/pt/zunder.yaml` on the same page. |
