# QubicFlow

Selbst gehosteter Qubic Wallet Tracker für steuerliche Dokumentation (BMF-konform).  
Unterstützt unbegrenzt viele Wallets (PRIVATE / BUSINESS), automatische EUR/USD-Kurse, Live-Events per WebSocket und CSV-Export für CoinTracking und den Steuerberater.

---

## Inhaltsverzeichnis

- [Features](#features)
- [Voraussetzungen](#voraussetzungen)
- [Start mit Docker](#start-mit-docker)
- [Start in VSCode (Entwicklung)](#start-in-vscode-entwicklung)
- [Konfiguration (.env)](#konfiguration-env)
- [Projektstruktur](#projektstruktur)
- [API-Übersicht](#api-übersicht)
- [Export / Steuer-CSVs](#export--steuer-csvs)
- [Hintergrund-Jobs](#hintergrund-jobs)
- [Tests ausführen](#tests-ausführen)
- [Technologie-Stack](#technologie-stack)

---

## Features

- **Unbegrenzte Wallets** — PRIVATE und BUSINESS, verwaltbar über die Oberfläche
- **Automatische Synchronisation** alle 60 Sekunden via Qubic RPC (`rpc.qubic.org`)
- **Tick-Range-Windowing** — überwindet das 10.000-Records-Limit der RPC-API durch rekursives Halbieren
- **EUR/USD-Kurse** — täglich von CoinGecko abgerufen, in DB gecacht
- **Statistik-Panels** — Stunden / Tag / Epoch / Monat / Jahr, je mit aktueller und vorheriger Periode
- **Wöchentliche Snapshots** — jeden Mittwoch 12:00 UTC
- **3 Animations-Varianten** für neue Events: Push Down, Slide In, Beam Drop (einstellbar)
- **Live-Updates** per WebSocket (Events + Node-Status)
- **Export CSV**:
  - CoinTracking-Format (PRIVATE Wallets, kommagetrennt, UTF-8 BOM)
  - Steuerberater-Format (BUSINESS Wallets, semikolongetrennt, UTF-8 BOM)
- **Interne Transfers** (`is_internal`) — Wallet-zu-Wallet-Transfers werden beim Export steuerlich neutral behandelt
- **DE / EN** Benutzeroberfläche, Dark / Light Mode
- **Vollständig containerisiert** — ein `docker-compose up --build` genügt

---

## Voraussetzungen

### Docker (empfohlen für Produktion)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac / Linux)
- `docker-compose` (bei Docker Desktop inklusive)

### Lokale Entwicklung (VSCode)

- Python 3.12+
- Node.js 22+
- VSCode mit der Erweiterung **Python** (ms-python.python) und **Debugpy**

---

## Start mit Docker

```bash
cd qubic-flow
docker-compose up --build
```

| Dienst    | URL                                    |
|-----------|----------------------------------------|
| Frontend  | http://localhost:8080                  |
| Backend   | http://localhost:8000/api/v1/health    |
| API-Docs  | http://localhost:8000/docs             |

> Die Ports sind auf `127.0.0.1` gebunden — von außen nicht erreichbar.

Daten werden im Docker-Volume `qubicflow-data` gespeichert und bleiben beim Neustart erhalten.

**Stoppen:**

```bash
docker-compose down
```

**Daten vollständig löschen:**

```bash
docker-compose down -v
```

---

## Start in VSCode (Entwicklung)

### 1. Abhängigkeiten einmalig installieren

```bash
# Backend
cd qubic-flow/backend
pip install -r requirements.txt

# Frontend
cd qubic-flow/frontend
npm install
```

### 2. Starten

1. Ordner `qubic-flow` in VSCode öffnen
2. **Run & Debug** öffnen (`Ctrl+Shift+D`)
3. Oben **"QubicFlow (Full Stack)"** auswählen
4. **F5** drücken

VSCode startet Backend (Port 8000) und Frontend (Port 5173) gleichzeitig.  
Chrome öffnet sich automatisch auf `http://localhost:5173`.

Der Vite-Dev-Server leitet `/api/...`-Anfragen automatisch an das Backend weiter (Proxy in `vite.config.js`).  
Python-Breakpoints funktionieren direkt in den `.py`-Dateien.

### Einzel-Start (optional)

```bash
# Nur Backend
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Nur Frontend
cd frontend
npm run dev
```

---

## Konfiguration (.env)

Datei `backend/.env` anlegen (Vorlage: `backend/.env.example`):

```env
# Datenbank (lokal: relativer Pfad, Docker: absoluter Pfad im Container)
DATABASE_URL=sqlite:///./data/qubicflow.db

# Qubic RPC
QUBIC_RPC_URL=https://rpc.qubic.org

# CoinGecko (optional: API-Key für höhere Rate Limits)
COINGECKO_API_URL=https://api.coingecko.com/api/v3
COINGECKO_API_KEY=

# CORS (kommagetrennte Origins)
CORS_ORIGINS=http://localhost:8080,http://localhost:5173

# Logging
LOG_LEVEL=INFO
TZ=UTC
```

> Die `.env`-Datei ist in `.gitignore` — nie einchecken.  
> Ohne `.env` starten Backend und Docker-Container mit den eingebauten Standardwerten.

---

## Projektstruktur

```
qubic-flow/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST-Endpunkte
│   │   │   ├── wallets.py   # Wallet CRUD
│   │   │   ├── events.py    # Event-Liste mit Pagination
│   │   │   ├── nodes.py     # Node CRUD + Reihenfolge
│   │   │   ├── stats.py     # Statistik-Panels
│   │   │   ├── export.py    # CSV-Download
│   │   │   ├── health.py    # Gesundheitsstatus
│   │   │   └── ws.py        # WebSocket-Endpunkt
│   │   ├── models/          # SQLAlchemy ORM-Modelle
│   │   │   ├── wallet.py
│   │   │   ├── event.py
│   │   │   ├── node.py
│   │   │   ├── sync_state.py
│   │   │   ├── sync_gap.py
│   │   │   ├── price_cache.py
│   │   │   ├── snapshot.py
│   │   │   └── settings.py
│   │   ├── services/        # Business-Logik
│   │   │   ├── sync_engine.py      # Tick-Sync mit Windowing
│   │   │   ├── qubic_client.py     # RPC-Client (3x Retry)
│   │   │   ├── coingecko.py        # Kurs-Abruf mit Rate-Limit
│   │   │   ├── export_service.py   # CSV-Generierung
│   │   │   ├── health_monitor.py   # Node-Statusprüfung
│   │   │   ├── snapshot_service.py # Wöchentliche Snapshots
│   │   │   └── scheduler.py        # APScheduler-Jobs
│   │   ├── websocket/
│   │   │   └── manager.py   # WebSocket ConnectionManager
│   │   ├── utils/
│   │   │   └── time.py      # UTC-Hilfsfunktionen
│   │   ├── config.py        # Pydantic-Settings
│   │   ├── database.py      # SQLAlchemy Engine + Session
│   │   └── main.py          # FastAPI App + Lifespan
│   ├── tests/               # pytest-Suite (72 Tests)
│   ├── alembic/             # DB-Migrationen
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/           # Seiten (Dashboard, Wallets, etc.)
│   │   ├── components/      # AppHeader, AppNav, StatsPanel, EventsTable
│   │   ├── composables/     # useWebSocket (Auto-Reconnect)
│   │   ├── stores/          # Pinia-Store (App-State)
│   │   ├── i18n/            # DE / EN Übersetzungen
│   │   ├── router/          # vue-router Routen
│   │   └── api.js           # Backend-HTTP-Client
│   ├── Dockerfile           # Multi-Stage: node build → nginx
│   ├── nginx.conf           # SPA-Routing + /api Proxy
│   ├── vite.config.js       # Dev-Proxy zu Backend
│   └── package.json
├── docker-compose.yml
└── .vscode/
    ├── launch.json          # F5: Full Stack starten
    └── tasks.json           # Build-Tasks
```

---

## API-Übersicht

Alle Endpunkte unter `/api/v1/`. Interaktive Doku: `http://localhost:8000/docs`

| Methode | Pfad                          | Beschreibung                          |
|---------|-------------------------------|---------------------------------------|
| GET     | `/health`                     | Backend-Status                        |
| GET     | `/wallets`                    | Alle aktiven Wallets                  |
| POST    | `/wallets`                    | Wallet anlegen                        |
| PUT     | `/wallets/{id}`               | Wallet bearbeiten                     |
| DELETE  | `/wallets/{id}`               | Wallet soft-löschen                   |
| GET     | `/events`                     | Events (filter: wallet_id, pagination)|
| GET     | `/nodes`                      | Nodes                                 |
| POST    | `/nodes`                      | Node anlegen                          |
| PUT     | `/nodes/{id}`                 | Node bearbeiten                       |
| DELETE  | `/nodes/{id}`                 | Node löschen                          |
| GET     | `/stats`                      | Statistik-Panels (current + previous) |
| GET     | `/export/cointracking`        | CoinTracking CSV (`?year=2024`)       |
| GET     | `/export/steuerberater`       | Steuerberater CSV (`?year=2024`)      |
| WS      | `/ws`                         | WebSocket (event.new, node.health)    |

### Wallet-Adresse

Qubic-Wallet-Adressen bestehen aus **genau 60 Großbuchstaben** (A–Z).  
Beispiel: `AAAAABBBBBCCCCCDDDDDEEEEEFFFFFGGGGGHHHHHIIIIIIJJJJJKKKKKLLLLL`

---

## Export / Steuer-CSVs

### CoinTracking (PRIVATE Wallets)

- Format: Komma-getrennt, UTF-8 BOM
- Enthält: Deposits und Withdrawals
- Interne Transfers (Wallet → Wallet) werden **automatisch ausgeschlossen**
- `is_internal` wird beim Export dynamisch berechnet — auch rückwirkend korrekt, wenn neue Wallets hinzugefügt werden
- Download: `GET /api/v1/export/cointracking?year=2024`

### Steuerberater (BUSINESS Wallets)

- Format: Semikolon-getrennt, UTF-8 BOM
- Enthält: alle Transfers inkl. interne (mit Typ-Kennzeichnung)
- Download: `GET /api/v1/export/steuerberater?year=2024`

Beide Exporte enthalten EUR-Werte, gerundet auf 2 Dezimalstellen.

---

## Hintergrund-Jobs

| Job                | Intervall              | Beschreibung                                      |
|--------------------|------------------------|---------------------------------------------------|
| `sync_all_wallets` | alle 60 Sekunden       | Neue Events von Qubic RPC holen, Kurse anreichern |
| `health_monitor`   | alle 30 Sekunden       | Node-Status prüfen, WS-Broadcast                  |
| `weekly_snapshot`  | Mi 12:00 UTC (Cron)   | Wöchentlichen Aggregations-Snapshot speichern     |

Jobs laufen mit `max_instances=1` und `coalesce=True` — kein paralleler Doppellauf.

Wenn der RPC für einen Tick-Bereich weniger Daten liefert als erwartet (`validForTick < to_tick`), wird eine **SyncGap**-Zeile angelegt und der fehlende Bereich beim nächsten Lauf erneut versucht.

---

## Tests ausführen

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

**72 Tests** in 4 Dateien:

| Datei                          | Inhalt                                        |
|-------------------------------|-----------------------------------------------|
| `test_time_utils.py`          | UTC-Konvertierungen, Z-Suffix                 |
| `test_export_service.py`      | CoinTracking- und Steuerberater-CSV-Format   |
| `test_sync_engine_logic.py`   | is_internal-Logik, Idempotenz, Preisspeicher  |
| `test_wallets_api.py`         | Wallet CRUD, Soft-Delete, 409 Duplikat       |

---

## Technologie-Stack

### Backend

| Paket              | Version   | Zweck                        |
|--------------------|-----------|------------------------------|
| FastAPI            | 0.115     | REST + WebSocket             |
| SQLAlchemy         | 2.0       | ORM + SQLite (WAL)           |
| Alembic            | 1.13      | DB-Migrationen               |
| Pydantic           | 2.9       | Validierung                  |
| APScheduler        | 3.10      | Hintergrundjobs              |
| httpx              | 0.27      | Async HTTP (RPC, CoinGecko)  |
| uvicorn            | 0.30      | ASGI-Server                  |

### Frontend

| Paket         | Version  | Zweck                      |
|---------------|----------|----------------------------|
| Vue 3         | 3.5      | UI-Framework               |
| Vite          | 6.0      | Build-Tool + Dev-Server    |
| Pinia         | 2.3      | State Management           |
| vue-router    | 4.5      | SPA-Routing                |
| Tailwind CSS  | 3.4      | Styling                    |
| Chart.js      | 4.4      | Snapshot-Liniendiagramm    |
| i18next       | 24.1     | DE/EN-Übersetzungen        |

### Infrastruktur

| Komponente  | Details                              |
|-------------|--------------------------------------|
| Container   | Docker + docker-compose              |
| Webserver   | nginx (alpine) für Frontend + Proxy  |
| Datenbank   | SQLite mit WAL-Modus                 |
| Datenpfad   | Docker-Volume `qubicflow-data`       |
