# Changelog

All notable changes to QubicFlow are documented here.

---

## [0.2.10] — 2026-07-04

### Added
- **🇩🇰 Danish tax model** — new country profile DK with mandatory FIFO and separate reporting of gains and deductible losses (no netting, per Danish Spekulationsbeskatning). The Settings UI locks the cost-basis method to FIFO when DK is selected. (Community request)
- **Portfolio value chart** — "Portfolio value over time" line chart (balance × daily rate) on Statistics → Overview, with the QU balance on a second axis; respects the wallet/function filter (`GET /stats/portfolio-history`)
- **Koinly & Blockpit CSV export** — two new export formats for PRIVATE wallets, available on the Tax page (`GET /export/koinly`, `GET /export/blockpit`)
- **Webhook notifications** — optional notifications for new incoming transfers with generic JSON, Discord, or ntfy format, minimum-amount filter and test button; configured under Settings → Data → Notifications. Only live events are reported, never historical imports
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
