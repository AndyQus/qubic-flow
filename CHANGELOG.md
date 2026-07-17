# Changelog

All notable changes to QubicFlow are documented here.

---

## [0.2.15] — 2026-07-17

### Added
- **Qubic Home Node support (`HOME_NODE`)** — new node type for your own Qubic archive node on the local network (e.g. Raspberry Pi or Umbrel, default URL `http://umbrel.local:8080`). It speaks the standard RPC interface (incl. `getEventLogs`) and serves from its own permanent archive, so wallets keep syncing even when public infrastructure is down. A healthy Home Node is **preferred over all public nodes** for live sync and historical queries (selection chain: HOME_NODE → BOB → RPC; ONLINE preferred over DEGRADED, then priority). **Private LAN addresses (`10.*`, `192.168.*`, `172.*`) are allowed for this node type only** — for `RPC`/`BOB_NODE` the SSRF protection still blocks them, link-local (`169.254.*`) and localhost stay blocked for every type. TLS certificate verification is skipped for LAN node types (http / self-signed certificates). Selectable on the Nodes page with its own hint text

---

## [0.2.14] — 2026-07-15

### Fixed
- **Balance History: owner ledgers and MyLedgerCSV showed UTC times** — the per-owner ledger and the flat transaction list returned timestamps without timezone information, so the browser displayed the raw UTC time (e.g. 9:00 instead of 11:00 local). The API now tags these timestamps as UTC and the browser converts them to the user's local timezone — all Balance History views (hourly/daily/weekly) behave the same as the Ledger overview
- **Balance History: Transfer sheet no longer shows pre-series history** — the Transfer view and the Excel `Transfer` sheet listed every internal transfer ever synced, including transfers from long before Balance History was enabled. They now only include transfers after the first capture (baseline) of the respective series — the same rule the per-owner ledgers already use. The API endpoint takes the series (`GET /balance-history/transfers?kind=hourly|daily|weekly`); without any captures the sheet is empty

### Changed
- **Excel exports written in the server's local timezone** — date cells in the generated .xlsx files (Ledger, Bestand, owner ledgers, Transfer, MyLedgerCSV) were written in UTC; they now use the server timezone, configurable via the `TZ` environment variable (e.g. `TZ=Europe/Berlin`; docker-compose passes `TZ` through, default remains UTC). The app UI always converts to the browser's local timezone independently of this setting

---

## [0.2.13] — 2026-07-14

### Added
- **Balance History (Bestandsverlauf)** — automatic balance capture of all active wallets in three series: **hourly** (on the hour), **daily** (12:00 UTC) and **weekly** at the epoch transition (Wednesday from 12:00 UTC; the job polls `/v1/tick-info` until the RPC actually reports the new epoch, up to 2 h, then captures anyway with a warning). Every record stores the balance, the **delta versus the previous capture** of the same series, incoming/outgoing amounts of the interval (from the RPC cumulative totals), tick, epoch, EUR/USD rate and the converted values. Each series can be toggled on the new Balance History settings tab — **disabled by default in production** (users enable what they need; in development mode, `APP_ENV=development`, all three are pre-enabled for testing); the hourly series has a configurable retention (default: unlimited)
- **New Statistics tab "Balance History"** — shows all sheets of the generated Excel files rendered live from the database: the Ledger overview (one row per capture, one column per wallet grouped by owner, price per 1 bn QUBIC in €/$, totals row), per-owner ledgers, internal transfers and the flat transaction list. Includes a **"Capture now" button** (same capture function as the scheduler, manually triggered — for testing), inline **editing of every row** (why/information/notes and even captured values — edited cells are marked and the original measured value is kept internally as audit trail) and **manual records** for things the app cannot know (e.g. corrections); manual records can be deleted again
- **Excel export in the user's ledger layout** — three .xlsx files (hourly/daily/weekly), each a full clone of the template structure: `Ledger` (with previous-year/current-year/total header block and per-owner EUR formulas), one `Ledger<Owner>` sheet per owner, `Transfer` (internal transfers, −source/+destination) and `MyLedgerCSV`. Wallet columns and owner sheets are built **dynamically from the local database** — new wallets and owners appear automatically; no personal data ships with the app. The affected series' file is regenerated **in the background** after every capture **and every edit** (atomic writes — a file open in Excel is skipped and rewritten on the next run) and can be downloaded any time from the Balance History tab (`GET /balance-history/export/{kind}`)
- **Per-owner ledgers & MyLedgerCSV driven by the network balance** — the ledger sheets no longer read the locally synced SC events. Instead, every capture of a series yields one events row computed as **balance delta versus the previous capture minus the known TX of the interval** (balance 100 → 200 with one TX of 50 ⇒ events row 50) — the API balance is the source of truth. Regular transfers (TX) stay individual rows dated with the transaction's own timestamp. Rows start with the first capture of the series (reset a series to start fresh). Wallet columns show the publicId (first 5 chars in the app, full id in the Excel header)
- **Retry on unreachable nodes** — if RPC and BOB are both unavailable at the daily/weekly slot, the capture retries every 10 minutes (up to 6 attempts) instead of losing the row; a slot that is still missed is bridged automatically by the delta chain (the next capture carries the full change of the outage period)
- **"Bestand" (Balances) sheet with consistency check** — every generated Excel file and the Balance History tab now include a balances view: the absolute QUBIC balance of every wallet per capture (as reported by the network, incl. tick), with a total column and its €/$ value. In the app, each cell is checked for consistency — the balance delta versus the previous capture must match the captured in-/outflows of the interval, mismatches are flagged with ⚠ (the hourly reconciliation job still auto-corrects drift against the network)
- **Dedicated "Balance History" settings tab with built-in guide** — series toggles, Excel auto export, hourly retention and file regeneration now live on their own settings tab, together with a short in-app documentation of how capture, editing, Excel generation and reset work (maintained alongside the feature)
- **Per-series reset** — each series (hourly/daily/weekly) can be reset individually on the Balance History settings tab (`DELETE /balance-history/series/{kind}`): after a confirmation prompt, all captures of that series (including manual records and comments) are deleted and its Excel file is regenerated empty — the other series stay untouched. Useful to clear test data before going live

### Fixed
- **RPC rate limit fully enforced (100 requests/min)** — the epoch and timestamp backfill jobs called `rpc.qubic.org` directly and bypassed the global rate limiter; they now share the same 100/min budget as all other RPC calls (balance snapshots, sync, archiver queries), so combined load can no longer exceed the API limit

---

## [0.2.12] — 2026-07-05

### Added
- **Live QX prices for token holdings** — the Tokens & Assets table on the wallet detail page now shows the current price (last QX trade, in QU per share) plus the resulting value in QU and in EUR/USD (today's rate). Prices come from the official Qubic QX API (`qxinfo.qubic.org`, the same source QXBoard uses) and are cached for 10 minutes; assets without trades show a dash. Configurable via `QX_API_URL`
- **Token/Shares portfolio view** — new "QUBIC | Tokens/Shares" switch on the Wallets → Portfolio tab. The token view mirrors the familiar owner grouping: summary bar with total token value, number of token types and **total value including QUBIC**; owner cards with token chips and totals; per-owner drilldown with one card per wallet listing every token (units, price, value in QU and EUR/USD) plus the wallet's combined total. Data comes from a new batch endpoint (`GET /wallets/assets-summary`) with a 5-minute server-side cache so the RPC node is not hit per wallet on every page view
- **Share vs. token classification** — assets issued by the QX smart contract itself (QX, QEARN, QVAULT, QSWAP, …) are now labelled "Share", assets issued by any other project (CFB, QFT, community tokens, …) are labelled "Token", shown as a colored badge (amber/sky) everywhere assets are listed
- Token/share lists (wallet detail page, portfolio owner cards, portfolio drilldown) are now sorted alphabetically by name

### Fixed
- **Portfolio Token/Shares totals** — the "total value" shown for an owner or wallet could be smaller than the token value alone if the QUBIC price (loaded separately) hadn't arrived yet. The total is now only shown once both components are known, instead of silently treating a missing QUBIC price as zero
- **Negative QUBIC balances** — regular wallet-to-wallet transfers (the TX sync path) never updated the tracked balance counter, only transfers touching a smart-contract/token address did. Wallets with heavy smart-contract activity (e.g. QX) could drift arbitrarily, even negative, dragging the portfolio total below the token-only value. TX-synced transfers now update the balance the same way SC events do, and the hourly reconciliation job now corrects the stored balance to the live RPC value on mismatch instead of only logging a warning and re-syncing history that didn't address the drift

---

## [0.2.11] — 2026-07-04

### Added
- **🇩🇰 Danish tax model** — new country profile DK with mandatory FIFO and separate reporting of gains and deductible losses (no netting, per Danish Spekulationsbeskatning). The Settings UI locks the cost-basis method to FIFO when DK is selected. (Community request)
- **Portfolio value chart** — "Portfolio value over time" line chart (balance × daily rate) on Statistics → Overview, with the QU balance on a second axis; respects the wallet/function filter (`GET /stats/portfolio-history`)
- **Koinly & Blockpit CSV export** — two new export formats for PRIVATE wallets, available on the Tax page (`GET /export/koinly`, `GET /export/blockpit`)
- **Webhook notifications** — optional notifications for new incoming transfers with generic JSON, Discord, or ntfy format, minimum-amount filter, TX/SC-event type filter (checkboxes decide which kind triggers a push) and test button; every message carries the full record with the event type on the first line; configured under Settings → Data → Notifications. Only live events are reported, never historical imports
- **Token & asset holdings** — the wallet detail page now shows live token/asset balances (e.g. QX shares) from the RPC assets endpoint, enriched with names from the assets registry (`GET /wallets/{id}/assets`)
- **Timestamp backfill job** — 6-hourly job resolves events stored without a usable timestamp (old BOB imports showing 1970-01-01) via the archiver tick-data endpoint and fills the EUR/USD rate in the same pass

### Fixed
- **Tax report: income events no longer double-taxed** — QU received as income (dividends, rewards) now enter the lot queue at their market value at receipt instead of zero cost basis; previously the full proceeds were taxed again on disposal
- **Tax report: year-end holdings** — disposals in later years no longer reduce the reported year-end holdings of the selected tax year
- **Tax report: honest report currency** — countries whose local currency has no tracked rate (CH, GB, DK, SE, NO, …) are now calculated **and labelled** in EUR instead of silently showing EUR numbers under the local currency name; the effective currency and method are exposed in `meta`
- **Price cache** — incomplete CoinGecko responses (only one of EUR/USD present) are no longer cached as 0.0, which permanently poisoned cost-basis calculations for that date; the missing rate is retried by the backfill job

---

## [0.2.7] — 2026-07-01

### Fixed
- **Copy numeric values as displayed** — double-clicking a numeric field (rate, amount, value) now copies exactly what is shown in the UI. Small values are no longer copied in scientific notation (e.g. `3.5555508908043315e-7`); they are copied as the rounded, locale-aware decimal (`0,0000003556` in German, `0.0000003556` in English), matching the on-screen precision.

---

## [0.2.5] — 2026-06-25

### Changed
- **Tick-based BOB-node selection** — the live-sync source is no longer chosen by priority alone. Among all active ONLINE/DEGRADED BOB nodes, the one with the **highest tick** is used (priority is only a tiebreaker). A stalled or lagging primary BOB node no longer blocks live sync.
- **Stall detection** — if even the best BOB node lags more than `MAX_BOB_LAG` (1000) ticks behind the RPC network tip, QubicFlow falls back to RPC for live sync and logs a warning in the Logs tab.

### Added
- **Active sync node in header** — the connection pill (top right) now shows which node is actually feeding live sync, by label or — if no label is set — by host. Updates live via a new `sync.node` WebSocket event when the elected node changes.

### Notes
- No data-loss risk from node switching: incremental sync always resumes from the persisted `last_tick`, with RPC backfill and gap recording covering any range a node could not serve.

---

## [0.2.3] — 2026-05-26

### Changed
- **Supporter Ranks** — Diamond Node description updated to "The backbone of the network"; rank descriptions aligned across EN/DE
- **Supporter Ranks explanation** — `tiers_note` now explicitly states that rank is determined by total QU donated (cumulative)
- **Top 50 supporters label** — updated to reflect rank-based sorting
- **Debug scenarios** — corrected QU thresholds for Avenger (50M), Guardian (100M), added Diamond Node scenario (500M), Legend corrected to 1B

---

## [0.2.0] — 2026-05-08

### Added
- **Node Notes** — free-text notes field on each node (stored in DB via Alembic migration 013)
- **BOB-Node full integration** — JSON-RPC 2.0 client (`qubic_getTransfers`, `qubic_getLogs`) with REST fallback; BOB serves as live event source, RPC as history source
- **Node diagnostics** — `POST /nodes/diagnose` runs connectivity + sync checks and writes results to the log buffer
- **Manual sync** — `POST /nodes/sync-now` triggers an immediate full wallet sync from the UI
- **Event type filter** — TX / EVENT / ALL filter buttons in the events table; filter is applied server-side so pagination stays correct
- **source_type filter** — `GET /events` and `GET /events/count` accept `source_type` query parameter

### Changed
- **BOB-Node health checks** — now correctly set `tick`, `health_status`, `response_time_ms`, and `fail_count` after every check (indentation bug fixed)
- **Transfer filter** — only events that involve the synced wallet are persisted; unfiltered network-wide BOB/RPC data is silently dropped
- **Sync engine** — BOB gap handling, `valid_for_tick` tracking, improved chunking and retry logic

### Fixed
- **`_run_diagnose` DB session** — now opens its own `SessionLocal()` instead of reusing the request session (prevented `DetachedInstanceError` after response end)
- **`_fetch_raw` on RPCClient** — `isinstance(BOBClient)` guard prevents `AttributeError` when event source is RPC
- **Duplicate sync/diagnose runs** — `_sync_running` / `_diagnose_running` flags return HTTP 429 on concurrent calls

### Security
- **SSRF protection** — `NodeCreate.url` validator blocks `localhost`, `127.x`, `10.x`, `192.168.x`, `169.254.x`, `172.x`, and non-http(s) schemes
- **node_type enum** — `node_type` field now validated as `Literal["RPC", "BOB_NODE"]`; arbitrary strings rejected with HTTP 422
- **notes max_length** — `notes` field capped at 2000 characters

### Tests
- 46 new tests covering all 7 code-review/security-audit fixes (`test_review_fixes.py`)
- `test_bob_client.py` updated to match new `_rpc`/`_http_get` interface (was patching removed `_request` method)
- `test_sync_engine_logic.py` — updated `test_neither_owned_sets_is_internal_0` to reflect intentional wallet-filter behaviour

---

## [0.1.16] — 2026-05-08

### Added
- **Privacy eye — extended coverage** — the hide/show toggle in the header now masks all financial values across the entire app: QUBIC volumes, event/TX counts in Dashboard panels (StatsPanel), epoch totals and wallet panels in Statistics, all tax amounts (gains, income, holdings, disposals) in Tax, and opening-position prices in WalletDetail
- **Privacy eye — tax input fields** — personal and business data fields on the Tax page (name, tax ID, address, company name, company tax number, VAT ID, registration number, company address) are masked as password fields when privacy mode is active
- **Dashboard search** — full-text search field in the Dashboard events table with 350 ms debounce; clears with ✕ button
- **Dashboard pagination** — configurable page size (10 / 25 / 50 / 100 / 250 / 500 / 1000) with persistent `localStorage` setting; entry count shown inline

### Changed
- **Ledger import** — "Import from Qubic Ledger" section in Settings → Data is now visible in production (was previously restricted to debug/dev mode only)
- **Settings → Data tab** — "Import from Qubic Ledger" moved to last position, after "Re-fetch data"

---

## [0.1.14] — 2026-04-30

### Added
- **Log error badge** — red dot appears on the "Nodes" nav item and the "Logs" tab whenever an ERROR is found in the last 50 log entries; tooltip explains the reason
- **Automatic error check** — `GET /nodes/logs/error-check` lightweight endpoint polled every 60 seconds from App.vue; returns only `{has_error: bool}`, no full log transfer
- **Log paging** — 50 entries per page with `« ‹ n/total › »` navigation; only shown when more than one page exists
- **Log level filter** — ALL / ERROR / WARNING / INFO buttons above the log table; switching resets to page 1
- **Log count + Refresh** — entry count and Refresh button placed inline with the filter buttons on the right side
- **Mobile log view** — compact cards on small screens instead of a table

### Changed
- **Log buffer** — increased from 500 to 1000 entries
- **Error check window** — checks last 50 log entries (previously 20)

### Fixed
- **Event dedup within batch** — API sometimes returns the same event twice with different `log_type` in one batch; added `seen_ids` set to skip intra-batch duplicates and prevent `UNIQUE constraint` errors

---

## [0.1.13] — 2026-04-30

### Added
- **Nodes page: Tabs** — Nodes page now has two tabs ("Nodes" / "Logs") matching the Wallets page style
- **Logs tab** — in-memory ring buffer (last 500 entries) captures health check results, sync errors and warnings per service; shown in a table with timestamp, level (colour-coded), source and message; Refresh button reloads on demand
- **Per-node health check button** — each node row in the table (desktop & mobile) now has a dedicated refresh icon button that triggers an immediate health check for that single node; icon spins while running
- **Docker daily restart** — new `restarter` sidecar service in `docker-compose.yml` restarts the backend container automatically every night at 03:00 UTC, preventing connection hangs on Raspberry Pi after network interruptions

### Fixed
- **Logs route ordering** — `GET /nodes/logs` was declared after `{node_id}` routes causing FastAPI to never match it; moved to top of router
- **Log level** — `logging.getLogger("app")` level was not explicitly set, suppressing INFO messages; now set to INFO in lifespan startup
- **Log capture** — added direct `log_buffer.add()` calls in `health_monitor` and `sync_engine` as reliable fallback independent of the Python logging handler chain

---

## [0.1.12] — 2026-04-29

### Added
- **Donor rank system** — 5 tiers based on total QU donated: ⚡ Quantum Spark (1M), 🗡️ Qubic Knight (10M), ⚔️ Crypto Avenger (25M), 🛡️ Block Guardian (50M), 👑 Chain Legend (100M+)
- **Rank-aware thank-you banners** — desktop header and mobile banner now show rank name (e.g. "Danke für deine Unterstützung lieber Block Guardian!")
- **Support page rank list** — donation tiers displayed with icon, colored name, description, and threshold; rank column added to Top 50 supporters table
- **"Zahlung erkannt für \<Rang\>"** — payment detection title on Support page dynamically shows the donor's rank
- **Top 50 supporters** — increased from Top 20; backend endpoint updated accordingly
- **Sortable config table** — Wallets config tab columns are now clickable with ascending/descending sort indicators (↑↓↕); default sort by label
- **Icon buttons** — Edit/Delete text buttons replaced with SVG pencil/trash icons in Wallets and Nodes views
- **DEV simulation** — all 5 rank scenarios available in debug panel; rank propagates globally to all banners

### Changed
- **Wallet & filter sorting** — wallet filter buttons, owner group pills, and portfolio groups now sorted alphabetically by label
- **Statistics** — wallet panels sorted by name; long owner names truncated with full-name tooltip on hover
- **i18n** — added `banner_suppressed_rank`, `banner_suppressed_rank_forever`, `check_title_rank` keys in DE and EN

---

## [0.1.11] — 2026-04-28

### Changed
- **Top 20 supporters** — addresses now show only the first 5 characters (no explorer link)
- **Eko thank-you** — honorary note below the Top 20 list is now centered
- **README** — updated Docker installation instructions (`docker compose` instead of `docker-compose`); added `qubicflow.webp` asset

---

## [0.1.10] — 2026-04-28

### Added
- **UmbrelOS quick-start section** — new "Start with UmbrelOS" section in both README.md (EN) and README.de.md (DE), above "Start with Docker"; includes 4-step Community App Store installation guide and link to https://github.com/AndyQus/qubicflow-umbrel-store
- **Dashboard screenshot** — QubicFlow dashboard screenshot added at the top of both READMEs

---

## [0.1.9] — 2026-04-27

### Added
- **Event notes** — every transaction/event can now have a user-defined note; editable inline directly in the list (pencil icon → input → green checkmark to save / red X to cancel); stored persistently in the database
- **Add Wallet in Portfolio tab** — the "+ Add Wallet" button is now visible directly in the portfolio view without having to switch to the configuration tab; filter pills (All / Private / Business) moved into the same row on the left
- **i18n** — note field keys added for German and English

### Changed
- Copy icons removed from all event columns (Source, Destination, TxId, Tick); the value itself is now clickable to copy — saves space and reduces visual clutter
- "Banner hidden until" label renamed to "Thank you forever banner" in the support page (EN)

---

## [0.1.8] — 2026-04-27

### Changed
- Submitted to the official Umbrel App Store (PR [#5461](https://github.com/getumbrel/umbrel-apps/pull/5461) — pending review)
- README updated in English and German with official store submission announcement
- Both README.md (EN) and README.de.md (DE) are now maintained in sync

---

## [0.1.7] — 2026-04-27

### Added
- **Token-Dividenden-Erfassung dokumentiert** — Qubics, die über Token-Ausschüttungen eingehen (z. B. QMine-Dividenden), werden automatisch als EVENTs erkannt und je Epoche vollständig erfasst; Token-Issuer-Adressen werden täglich vom Qubic-Assets-Register synchronisiert

### Fixed
- Tax report returned HTTP 500 on Umbrel OS — `OpeningPosition` was missing from `Base.metadata` registration, so the `opening_positions` table was never created on fresh deployments via the `create_all` fallback path
- Error logging added to the tax report endpoint (`logger.exception`) for better diagnostics in production

### Changed
- Balance is now refreshed immediately in the background when a wallet is updated/saved (previously only on wallet creation)
- Balance scheduler confirmed at 1-hour interval

---

## [0.1.0] — 2026-04-26

### First public release

**Core Features**
- Unlimited wallet tracking (Private & Business)
- Automatic sync every 60 seconds via RPC or BOB Node
- Live event updates via WebSocket
- Daily EUR/USD price history from CoinGecko
- German & English UI, Dark & Light Mode

**Tax Reporting**
- FIFO / LIFO / HIFO / AVCO cost-basis methods
- Country-specific tax rules for 14 countries (DE, AT, CH, US, GB, AU, CA, FR, NL, IT, ES, PT, SE, NO)
- 1-year holding-period exemption (e.g. Germany)
- Opening positions for pre-tracked balances
- CSV export for CoinTracking & tax advisors
- PDF tax report

**Dashboard & Statistics**
- Stats panels: Hour / Day / Epoch / Month / Year
- Epoch view with per-wallet breakdown (TX / Event split) — all epochs navigable, not just the current one
- Dividends from Smart Contract payouts and token distributions (e.g. QX shares, Qearn, QMine) are automatically detected as EVENTs and fully visible per epoch
- Weekly snapshots (every Wednesday 12:00 UTC)
- Events table with TxId, Tick, copy & Explorer links

**Infrastructure**
- Fully containerized — one `docker compose up --build` command
- Available on Umbrel OS via Community App Store
- Disclaimer banner & footer (beta notice, version, links)
- Open Source — MIT License

---

*Format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/).*
