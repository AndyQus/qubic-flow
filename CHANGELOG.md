# Changelog

All notable changes to QubicFlow are documented here.

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
- Epoch view with per-wallet breakdown (TX / Event split)
- Weekly snapshots (every Wednesday 12:00 UTC)
- Events table with TxId, Tick, copy & Explorer links

**Infrastructure**
- Fully containerized — one `docker compose up --build` command
- Available on Umbrel OS via Community App Store
- Disclaimer banner & footer (beta notice, version, links)
- Open Source — MIT License

---

*Format follows [Keep a Changelog](https://keepachangelog.com/). Versions follow [Semantic Versioning](https://semver.org/).*
