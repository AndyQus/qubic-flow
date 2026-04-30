# Changelog

All notable changes to QubicFlow are documented here.

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
