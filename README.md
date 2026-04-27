# QubicFlow

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/open%20source-%E2%9D%A4-brightgreen.svg)](https://github.com/AndyQus/qubic-flow)

Self-hosted, **open-source** Qubic wallet tracker for tax documentation.  
Supports unlimited wallets (PRIVATE / BUSINESS), automatic EUR/USD rates, live events via WebSocket, tax reporting (FIFO/LIFO/HIFO/AVCO, country-specific rules) and CSV export for CoinTracking and tax advisors.

**GitHub:** https://github.com/AndyQus/qubic-flow  
**German README:** [README.de.md](README.de.md)

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Start with Docker](#start-with-docker)
- [Start in VSCode (Development)](#start-in-vscode-development)
- [Configuration (.env)](#configuration-env)
- [Node Configuration](#node-configuration)
- [Project Structure](#project-structure)
- [API Overview](#api-overview)
- [Export / Tax CSVs](#export--tax-csvs)
- [Tax Reporting](#tax-reporting)
- [Background Jobs](#background-jobs)
- [Running Tests](#running-tests)
- [Technology Stack](#technology-stack)
- [Deployment & Publishing](#deployment--publishing)

---

## Features

- **Unlimited wallets** — PRIVATE and BUSINESS, manageable via the UI
- **Dual-node support** — Standard RPC (`rpc.qubic.org`) **and** BOB Node (`bobnet.qubic.li`); the best available node is chosen automatically
- **Event sync** — automatically every 60 seconds; RPC nodes via `getEventLogs` (uses `transactionHash` **directly as primary key** — the same 60-character ID shown in the Qubic Explorer), BOB nodes via `POST /getQuTransferForIdentity`. SC-internal events without `transactionHash` fall back to the numeric `logId` (the 16-character `logDigest` is then the Explorer ID for those events)
- **TX sync** — transfer transactions via Qubic Archiver API, deduplicated against events; tries multiple field names (`transactionId`, `txId`, `id`, `digest`, `hash`) and prefers the real 60-character Qubic TxID. Stub matching: existing event rows are found by `(tick, source, destination, amount)` and updated with the real TxID (user fields like notes/labels are preserved). Chunk-based progress with checkpoint per chunk — failed chunks become a sync gap and do not reset `last_tx_tick`. Initial sync starts at `current_tick − 500,000` (archiver retention period), not at tick 1
- **Smart contract classification** — `logType=0` transfers are classified as `TX` (normal transfer) or `EVENT` (smart contract / token issuer, e.g. QX, Qearn, QMine) via address labels
- **Token dividend tracking** — Qubics received via token distributions (e.g. QMine dividends) are automatically detected: token issuer addresses are synced daily from the Qubic assets registry (`static.qubic.org`); incoming transfers from these addresses are classified as EVENTs and recorded per epoch with date, amount and EUR/USD rate
- **Manual resync** — "Refresh data" button in settings (`POST /wallets/resync-all`) resets sync counters and imports only missing records (existing data is preserved)
- **Tick-range window technique** — overcomes the 10,000-record RPC API limit via recursive halving
- **Address name resolution** — automatic resolution of Qubic addresses to tokens/labels (assets page + CSV)
- **Assets page** — overview of all smart contracts and tokens with ticker, category, decimal places, website
- **Wallet balances** — current balance per wallet is updated automatically
- **EUR/USD rates** — fetched daily from CoinGecko, cached in the database
- **Statistics panels** — Hour / Day / Epoch / Month / Year, each with current and previous period
- **Epoch view** — all epochs navigable as a wallet panel grid (label, owner, incoming Qubics incl. TX/event split, outgoing Qubics incl. EUR value); dividends from smart contract payouts and token distributions (e.g. QX shares, Qearn, QMine) are automatically detected per epoch as EVENTs; filter "All" / "With income only" plus "Show all" toggle (`?ext=1`) to show/hide empty sub-rows
- **Events table** — separate columns for TxId and Tick, each with copy button and Explorer link (`/network/tx/{id}` and `/network/tick/{tick}`); short display (5 chars) with tooltip, full value on copy/open. Only real 60-character Qubic TxIDs are shown — SC-internal events without user TX show a dash in the TxID column
- **Weekly snapshots** — every Wednesday at 12:00 UTC
- **3 animation variants** for new events: slide down, fly in, bar fade (configurable)
- **Live updates** via WebSocket (events + node status)
- **Tax reporting**:
  - FIFO, LIFO, HIFO and AVCO cost-basis methods
  - Country-specific rules (DE, AT, CH, and more) — including 1-year holding-period tax exemption
  - Opening positions for pre-tracked balances
  - Price lookup per date directly in the UI
  - CSV and PDF export of the tax report
- **CSV export**:
  - CoinTracking format (PRIVATE wallets, comma-separated, UTF-8 BOM)
  - Tax advisor format (BUSINESS wallets, semicolon-separated, UTF-8 BOM)
  - Resolved address names in the comment field
- **Internal transfers** — wallet-to-wallet transfers are treated as tax-neutral in exports
- **German / English** UI, dark / light mode
- **Tabbed settings** — `Appearance` (currency, font, theme, language, animations), `Tax` (country/method, personal/business data), `Data` (export, backup/restore, ledger import, resync); active tab is reflected in the URL query parameter (`?tab=…`)
- **Fully containerized** — a single `docker compose up --build` is all you need
- **Footer** — disclaimer banner and fixed footer with copyright, links (Qubic.org, terms, privacy) and version number

---

## Requirements

### Docker (recommended for production)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac / Linux)
- `docker-compose` (included with Docker Desktop)

### Local Development (VSCode)

- Python 3.12+
- Node.js 22+
- VSCode with the **Python** (ms-python.python) and **Debugpy** extensions

---

## Start with Docker

```bash
cd qubic-flow
docker-compose up --build   # first start or after code changes
docker-compose up           # subsequent starts (no --build needed)
docker-compose down         # stop (data is preserved)
docker-compose down -v      # stop + delete all data
```

**→ Main page: http://localhost:8080**

| Service   | URL                                    |
|-----------|----------------------------------------|
| Frontend  | http://localhost:8080                  |
| Backend   | http://localhost:8000/api/v1/health    |
| API docs  | http://localhost:8000/docs             |

> Ports are bound to `127.0.0.1` — not reachable from outside.

The backend automatically runs `alembic upgrade head` on startup — database migrations run without manual intervention.

Data is stored in the Docker volume `qubicflow-data` and persists across restarts.

---

## Start in VSCode (Development)

### 1. Install dependencies (once)

```bash
# Backend
cd qubic-flow/backend
pip install -r requirements.txt

# Frontend
cd qubic-flow/frontend
npm install
```

### 2. Initialize the database (once / after migrations)

```bash
cd qubic-flow/backend
alembic upgrade head
```

> Run after first checkout and after every new migration.  
> Creates all tables including `events` (composite primary key), `sync_state`, `address_labels`, `wallet_balances`, `opening_positions` and more.

### 3. Start

1. Open the `qubic-flow` folder in VSCode
2. Open **Run and Debug** (`Ctrl+Shift+D`)
3. Select **"QubicFlow (Full Stack)"** at the top
4. Press **F5**

VSCode starts the backend (port 8000) and frontend (port 5173) simultaneously.  
**→ Main page: http://localhost:5173**

The Vite dev server automatically proxies `/api/...` requests to the backend (proxy in `vite.config.js`).  
Python breakpoints work directly in `.py` files.

### Individual start (optional)

```bash
# Backend only
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Frontend only
cd frontend
npm run dev
```

---

## Node Configuration

Nodes are managed via the UI under **Settings → Nodes**.  
QubicFlow automatically selects the highest-priority ONLINE node during sync.

### Node Types

| Type       | Description                               | Default URL                      |
|------------|-------------------------------------------|----------------------------------|
| `RPC`      | Qubic Public RPC (REST)                  | `https://rpc.qubic.org`         |
| `BOB_NODE` | Qubic BOB Node (core team, REST + WS)    | `http://your-bob-node:40420`    |

### Setting up an RPC node (default)

```
URL:       https://rpc.qubic.org
Type:      RPC
Label:     Qubic RPC
Priority:  1
```

### Setting up a BOB node

```
URL:       https://bobnet.qubic.li:40420
Type:      BOB_NODE
Label:     BOB Public Node
Priority:  1
```

The BOB node uses its own REST API on port **40420** — the standard RPC endpoints (`/v1/tick-info` etc.) are **not** available there.  
QubicFlow detects the type automatically via `node_type = BOB_NODE` and uses the correct endpoints.

#### BOB endpoints used

| Endpoint                         | Method | Purpose                                |
|----------------------------------|--------|----------------------------------------|
| `/status`                        | GET    | Status check, current tick             |
| `/getQuTransferForIdentity`      | POST   | QU transfers per wallet + tick range   |

#### Known limitations (BOB)

- **Timestamps missing** in transfer entries — transaction data shows no correct date. An improvement via `GET /tick/{tickNumber}` is planned.
- The public BOB node (`bobnet.qubic.li:40420`) is a community service with no guaranteed availability. For production use, running your own BOB node is recommended.

> Full BOB API documentation: [`docs/bob_node.md`](docs/bob_node.md)

### Node failover

The sync job (`sync_all_wallets`, every 60 s) selects the node using the following logic:

1. Only `is_active = 1` nodes are considered
2. ONLINE nodes take priority over DEGRADED nodes
3. In case of a tie, **priority** decides (lower number = higher priority)
4. If no node is available, the system falls back to `QUBIC_RPC_URL` from `.env`

---

## Configuration (.env)

Create `backend/.env` (template: `backend/.env.example`):

```env
# Database (local: relative path, Docker: absolute path in container)
DATABASE_URL=sqlite:///./data/qubicflow.db

# Qubic RPC
QUBIC_RPC_URL=https://rpc.qubic.org

# CoinGecko (optional: API key for higher rate limits)
COINGECKO_API_URL=https://api.coingecko.com/api/v3
COINGECKO_API_KEY=

# CORS (comma-separated origins)
CORS_ORIGINS=http://localhost:8080,http://localhost:5173

# Logging
LOG_LEVEL=INFO
TZ=UTC
```

> The `.env` file is in `.gitignore` — never commit it.  
> Without `.env`, the backend and Docker container start with built-in defaults.

---

## Project Structure

```
qubic-flow/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST endpoints
│   │   │   ├── wallets.py   # Wallet CRUD
│   │   │   ├── events.py    # Event list with pagination
│   │   │   ├── nodes.py     # Node CRUD + ordering
│   │   │   ├── stats.py     # Statistics panels
│   │   │   ├── export.py    # CSV download
│   │   │   ├── labels.py    # Address name resolution
│   │   │   ├── health.py    # System status
│   │   │   ├── tax.py       # Tax reporting (settings, report, opening positions)
│   │   │   └── ws.py        # WebSocket endpoint
│   │   ├── models/          # SQLAlchemy ORM models
│   │   │   ├── wallet.py
│   │   │   ├── event.py
│   │   │   ├── node.py
│   │   │   ├── sync_state.py
│   │   │   ├── sync_gap.py
│   │   │   ├── price_cache.py
│   │   │   ├── address_label.py
│   │   │   ├── snapshot.py
│   │   │   ├── settings.py
│   │   │   ├── wallet_balance.py    # Wallet balance
│   │   │   └── opening_position.py  # Opening positions for tax
│   │   ├── services/        # Business logic
│   │   │   ├── sync_engine.py      # Tick sync with window technique (event + TX); dynamic node selection
│   │   │   ├── qubic_client.py     # RPCClient + BOBClient (3× retry, BOB response mapping)
│   │   │   ├── coingecko.py        # Rate fetching with rate limiting
│   │   │   ├── label_service.py    # Address name sync
│   │   │   ├── export_service.py   # CSV generation
│   │   │   ├── health_monitor.py   # Node status checking
│   │   │   ├── snapshot_service.py # Weekly snapshots
│   │   │   ├── balance_service.py  # Wallet balance updates
│   │   │   ├── tax_engine.py       # Tax calculation (FIFO/LIFO/HIFO/AVCO, country-specific)
│   │   │   └── scheduler.py        # APScheduler jobs
│   │   ├── websocket/
│   │   │   └── manager.py   # WebSocket connection management
│   │   ├── utils/
│   │   │   └── time.py      # UTC helper functions
│   │   ├── config.py        # Pydantic settings
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   └── main.py          # FastAPI app + lifespan
│   ├── tests/               # pytest suite (test_tax_engine.py, test_coingecko.py)
│   ├── alembic/
│   │   └── versions/        # Database migrations
│   │       ├── 001_composite_pk_events.py
│   │       ├── 002_add_last_tx_tick.py
│   │       ├── 003_address_labels.py
│   │       ├── 004_wallet_balance.py
│   │       └── 005_opening_positions.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/           # Pages (Dashboard, Wallets, Assets, Statistics, Tax, etc.)
│   │   ├── components/      # AppHeader, AppNav, AppFooter, StatsPanel, EventsTable, WalletFilter
│   │   ├── composables/     # useWebSocket (auto-reconnect)
│   │   ├── stores/          # Pinia state stores
│   │   ├── i18n/            # DE / EN translations
│   │   ├── router/          # vue-router routes
│   │   └── api.js           # Backend HTTP client
│   ├── src/tests/unit/      # Vitest unit tests
│   ├── tests/e2e/           # Playwright end-to-end tests
│   ├── vitest.config.js     # Vitest config
│   ├── playwright.config.js # Playwright config
│   ├── Dockerfile           # Multi-stage: Node build → nginx
│   ├── nginx.conf           # SPA routing + /api proxy
│   ├── vite.config.js       # Dev proxy to backend
│   └── package.json
├── docs/
│   └── bob_node.md          # BOB Node API reference
├── VERSION                  # Current version number (read by CI)
├── docker-compose.yml
└── .vscode/
    ├── launch.json          # F5: start full stack
    └── tasks.json           # Build tasks
```

---

## API Overview

All endpoints under `/api/v1/`. Interactive docs: `http://localhost:8000/docs`

| Method | Path                                  | Description                                           |
|--------|---------------------------------------|-------------------------------------------------------|
| GET    | `/health`                             | Backend status                                        |
| GET    | `/wallets`                            | All active wallets                                    |
| POST   | `/wallets`                            | Create wallet                                         |
| PUT    | `/wallets/{id}`                       | Update wallet                                         |
| DELETE | `/wallets/{id}`                       | Soft-delete wallet                                    |
| POST   | `/wallets/{id}/resync-tx`             | Restart TX sync for a wallet                          |
| POST   | `/wallets/resync-all`                 | Resync all wallets (missing records only)             |
| GET    | `/events`                             | Events (filter: wallet_id, paginated)                 |
| GET    | `/labels`                             | Address labels (optional `?address=`)                 |
| GET    | `/nodes`                              | List nodes                                            |
| POST   | `/nodes`                              | Create node                                           |
| PUT    | `/nodes/{id}`                         | Update node                                           |
| DELETE | `/nodes/{id}`                         | Delete node                                           |
| GET    | `/stats/current`                      | Statistics panels (current + previous period)         |
| GET    | `/stats/history`                      | Weekly/monthly time series                            |
| GET    | `/stats/snapshots`                    | Stored weekly snapshots                               |
| GET    | `/stats/epochs`                       | All epoch breakdowns per wallet (in/out, TX/event split, dividends as EVENTs) |
| GET    | `/export/cointracking`                | CoinTracking CSV (`?year=2024`)                       |
| GET    | `/export/steuerberater`               | Tax advisor CSV (`?year=2024`)                        |
| GET    | `/tax/settings`                       | Read tax settings                                     |
| PUT    | `/tax/settings`                       | Save tax settings                                     |
| GET    | `/tax/countries`                      | Available countries + tax rules                       |
| GET    | `/tax/opening-positions`              | List opening positions                                |
| POST   | `/tax/opening-positions`              | Create opening position                               |
| DELETE | `/tax/opening-positions/{id}`         | Delete opening position                               |
| GET    | `/tax/report`                         | Calculate tax report                                  |
| GET    | `/tax/price`                          | EUR/USD rate for a date (`?date=`)                    |
| WS     | `/ws`                                 | WebSocket (event.new, node.health)                    |

### Wallet address format

Qubic wallet addresses consist of **exactly 60 uppercase letters** (A–Z).  
Example: `AAAAABBBBBCCCCCDDDDDEEEEEFFFFFGGGGGHHHHHIIIIIIJJJJJKKKKKLLLLL`

---

## Export / Tax CSVs

### CoinTracking (PRIVATE wallets)

- Format: comma-separated, UTF-8 BOM
- Contains: deposits and withdrawals
- Internal transfers (wallet → wallet) are **automatically excluded**
- `is_internal` is calculated dynamically at export time — retroactively correct when new wallets are added
- Comment field contains resolved address names: `"Source name → Destination name"`
- Download: `GET /api/v1/export/cointracking?year=2024`

### Tax advisor (BUSINESS wallets)

- Format: semicolon-separated, UTF-8 BOM
- Contains: all transfers including internal (with type flag)
- Comment field contains resolved address names: `"Source name → Destination name"`
- Download: `GET /api/v1/export/steuerberater?year=2024`

Both exports include EUR values rounded to 2 decimal places.

---

## Tax Reporting

The **Tax** page calculates gains and income according to country-specific rules directly in the app.

### Configuration

Under **Settings → Tax**:

| Setting | Description                                        | Default |
|---------|----------------------------------------------------|---------|
| Country | Tax jurisdiction (DE, AT, CH, …)                  | DE      |
| Method  | Calculation order (FIFO / LIFO / HIFO / AVCO)     | FIFO    |

### Supported countries

Available countries and their rules are provided by `GET /api/v1/tax/countries`.  
For Germany (DE): gains from disposals held for more than 12 months are tax-free.

### Opening positions

If you held QU before the first recorded event, you can enter the balance as an **opening position**:

- Wallet, date, amount (QU), optional EUR/USD rate, note
- Managed via `GET/POST/DELETE /api/v1/tax/opening-positions`
- The rate for the entered date can be looked up via `GET /api/v1/tax/price?date=YYYY-MM-DD`

### Tax report

`GET /api/v1/tax/report?year=2024&mode=private&wallet_ids=…` returns:

```json
{
  "summary": {
    "taxable_gains_eur": 1234.56,
    "tax_free_gains_eur": 500.00,
    "income_eur": 200.00,
    "total_disposed_qu": 50000,
    "total_acquired_qu": 100000
  },
  "disposals": [...],
  "income_events": [...],
  "meta": { "year": 2024, "mode": "private", "country": "DE", "method": "FIFO" }
}
```

The report can be downloaded directly in the UI as **CSV** or **PDF**.

---

## Background Jobs

| Job                | Interval             | Description                                                               |
|--------------------|----------------------|---------------------------------------------------------------------------|
| `sync_all_wallets` | every 60 seconds     | Event sync + TX sync + balance update; dynamically selects the best available node |
| `health_monitor`   | every 30 seconds     | Check node status (`/v1/tick-info` for RPC, `/status` for BOB), WebSocket broadcast |
| `sync_labels`      | every 24 hours       | Address name sync (address_labels, tokens, issuances)                    |
| `weekly_snapshot`  | Wed 12:00 UTC (cron) | Save weekly aggregation snapshot                                          |

Jobs run with `max_instances=1` and `coalesce=True` — no parallel duplicate runs.

If the RPC delivers fewer records than expected for a tick range (`validForTick < to_tick`), a sync gap is created and the missing range is retried on the next run.

---

## Running Tests

### Backend (pytest)

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

| File                       | Tests | Description                                                          |
|----------------------------|-------|----------------------------------------------------------------------|
| `tests/test_tax_engine.py` | 27    | Lot matching (FIFO/LIFO/HIFO/AVCO), holding period, tax rules, date parser |
| `tests/test_coingecko.py`  | 6     | Rate cache hit/miss, network errors, side-effect-free               |

### Frontend — Unit tests (Vitest)

```bash
cd frontend
npm test              # run once
npm run test:watch    # watch mode
```

| File                                   | Tests | Description                                              |
|----------------------------------------|-------|----------------------------------------------------------|
| `src/tests/unit/useQubicUtils.test.js` | 12    | `explorerUrl`, `txUrl`, `tickUrl`, `shortAddr`, `maskLabel` |
| `src/tests/unit/store.test.js`         | 17    | Pinia store: `locale`, `filteredWallets`, `activeNode`, `prependEvent`, localStorage |

### Frontend — End-to-end tests (Playwright)

```bash
cd frontend
npx playwright install   # once: download browsers
npm run test:e2e         # run all E2E tests
```

Requires a running backend server. The Vite dev server is started automatically by Playwright.

| File                          | Tests | Description                                       |
|-------------------------------|-------|---------------------------------------------------|
| `tests/e2e/dashboard.spec.js` | 4     | Title, navigation, events table, header           |
| `tests/e2e/navigation.spec.js`| 8     | Page switching, settings tabs, URL persistence    |
| `tests/e2e/wallets.spec.js`   | 6     | Wallet list, add dialog, filter buttons           |

---

## Technology Stack

### Backend

| Package     | Version | Purpose                            |
|-------------|---------|------------------------------------|
| FastAPI     | 0.115   | REST + WebSocket                   |
| SQLAlchemy  | 2.0     | ORM + SQLite (WAL)                 |
| Alembic     | 1.14    | Database migrations                |
| Pydantic    | 2.10    | Validation                         |
| APScheduler | 3.10    | Background jobs                    |
| httpx       | 0.28    | Async HTTP (RPC, CoinGecko)        |
| uvicorn     | 0.32    | ASGI server                        |
| pytest      | 8.3     | Test framework                     |

### Frontend

| Package      | Version | Purpose                            |
|--------------|---------|------------------------------------|
| Vue 3        | 3.5     | UI framework                       |
| Vite         | 6.0     | Build tool + dev server            |
| Pinia        | 2.3     | State management                   |
| vue-router   | 4.5     | SPA routing                        |
| Tailwind CSS | 3.4     | Styling                            |
| Chart.js     | 4.4     | Line chart for snapshots           |
| i18next      | 24.1    | DE/EN translations                 |
| jsPDF        | 2.x     | PDF export (tax report)            |
| Vitest       | 2.1     | Unit tests (happy-dom)             |
| Playwright   | 1.49    | End-to-end tests                   |

### Infrastructure

| Component  | Details                                |
|------------|----------------------------------------|
| Container  | Docker + docker-compose                |
| Web server | nginx (alpine) for frontend + proxy    |
| Database   | SQLite with WAL mode                   |
| Data path  | Docker volume `qubicflow-data`         |

---

## Deployment & Publishing

QubicFlow is published as a multi-arch Docker image (linux/amd64 + linux/arm64) to Docker Hub and can be installed via the Umbrel Community App Store.

### Branch strategy

```
develop  →  development, tests, bugfixes  (no automatic build)
   ↓  merge
main     →  GitHub Actions starts automatically  →  Docker Hub + Umbrel Store
```

- Development happens on `develop` — unlimited commits, no build triggered
- Every merge to `main` triggers the full release process
- The version is read from the `VERSION` file (plain semver, e.g. `0.1.7`)

### GitHub Actions Workflow (`.github/workflows/docker-publish.yml`)

The workflow consists of 4 sequential jobs:

| Job                  | Description                                                                 |
|----------------------|-----------------------------------------------------------------------------|
| `tag`                | Reads `VERSION` file, creates git tag `v{VERSION}` (skipped if already exists) |
| `build-backend`      | Multi-arch Docker image for backend → Docker Hub                            |
| `build-frontend`     | Vue build + nginx Docker image → Docker Hub                                 |
| `update-umbrel-store`| Automatically updates version numbers in the store repo                     |

The `workflow_dispatch` trigger allows manual re-runs from the GitHub Actions UI if a build fails.

### Required GitHub Secrets

In the `qubic-flow` repository under Settings → Secrets and variables → Actions:

| Secret               | Value                                                                 |
|----------------------|-----------------------------------------------------------------------|
| `DOCKERHUB_USERNAME` | Docker Hub username                                                   |
| `DOCKERHUB_TOKEN`    | Docker Hub Personal Access Token                                      |
| `STORE_REPO_TOKEN`   | GitHub fine-grained PAT for `qubicflow-umbrel-store` (Contents: Read+Write) |

### Triggering a release

```bash
# 1. Update version
echo "0.1.8" > VERSION
# Also update APP_VERSION in frontend/src/components/AppFooter.vue
# Also add entry to CHANGELOG.md

# 2. Commit and push to develop
git add VERSION frontend/src/components/AppFooter.vue CHANGELOG.md
git commit -m "chore: bump version to v0.1.8"
git push origin develop

# 3. Merge to main → triggers the pipeline automatically
git checkout main
git merge develop
git push origin main
```

### Umbrel Installation

#### Community App Store (available now)

1. Open Umbrel → **App Store**
2. Click **⋮** in the top right → **Community App Stores**
3. Enter the following link and confirm:
   ```
   https://github.com/AndyQus/qubicflow-umbrel-store
   ```
4. QubicFlow appears in the App Store → **Install**

#### Official Umbrel App Store (submission pending)

QubicFlow has been submitted to the official Umbrel App Store and is currently under review by the Umbrel team.

> **PR:** https://github.com/getumbrel/umbrel-apps/pull/5461

Once accepted, QubicFlow will be available directly in the built-in Umbrel App Store without adding a community store URL. Until then, use the community store link above.

---

## License

MIT License — see [LICENSE](LICENSE)

QubicFlow is free, open-source software. The source code is publicly available on GitHub:  
**https://github.com/AndyQus/qubic-flow**
