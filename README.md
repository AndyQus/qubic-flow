# QubicFlow

Selbst gehosteter Qubic Wallet Tracker für steuerliche Dokumentation (BMF-konform).  
Unterstützt unbegrenzt viele Wallets (PRIVATE / BUSINESS), automatische EUR/USD-Kurse, Live-Events per WebSocket, Steuerauswertung (FIFO/LIFO, länderspezifische Regeln) sowie CSV-Export für CoinTracking und den Steuerberater.

---

## Inhaltsverzeichnis

- [Features](#features)
- [Voraussetzungen](#voraussetzungen)
- [Start mit Docker](#start-mit-docker)
- [Start in VSCode (Entwicklung)](#start-in-vscode-entwicklung)
- [Konfiguration (.env)](#konfiguration-env)
- [Nodes konfigurieren](#nodes-konfigurieren)
- [Projektstruktur](#projektstruktur)
- [API-Übersicht](#api-übersicht)
- [Export / Steuer-CSVs](#export--steuer-csvs)
- [Steuerauswertung (Tax Engine)](#steuerauswertung-tax-engine)
- [Hintergrund-Jobs](#hintergrund-jobs)
- [Tests ausführen](#tests-ausführen)
- [Technologie-Stack](#technologie-stack)

---

## Features

- **Unbegrenzte Wallets** — PRIVATE und BUSINESS, verwaltbar über die Oberfläche
- **Dual-Node-Unterstützung** — Standard-RPC (`rpc.qubic.org`) **und** BOB-Node (`bobnet.qubic.li`) werden unterstützt; der beste verfügbare Node wird automatisch gewählt
- **Event-Sync** — automatisch alle 60 Sekunden; RPC-Nodes via `getEventLogs`, BOB-Nodes via `POST /getQuTransferForIdentity`
- **TX-Sync** — Transfer-Transaktionen via Qubic Archiver API, dedupliziert gegen Events; probiert mehrere Feldnamen (`transactionId`, `txId`, `id`, `digest`, `hash`) und bevorzugt die echte 60-Zeichen-Qubic-TxID
- **Smart-Contract-aware Klassifikation** — `logType=0` Transfers werden über Adress-Labels als `TX` (normaler Transfer) oder `EVENT` (Smart Contract / Token Issuer, z. B. QX, Qearn) eingeordnet
- **Manueller Resync** — Button „Daten neu abrufen" in den Einstellungen (`POST /wallets/resync-all`) setzt Sync-Zähler zurück und importiert insert-only (bestehende Records bleiben unverändert, nur fehlende werden ergänzt)
- **Tick-Range-Windowing** — überwindet das 10.000-Records-Limit der RPC-API durch rekursives Halbieren
- **Adress-Namen-Auflösung** — automatische Auflösung von Qubic-Adressen zu Tokens/Labels (Assets-Seite + CSV)
- **Assets-Seite** — Übersicht aller Smart Contracts und Tokens mit Ticker, Kategorie, Dezimalstellen, Website
- **Wallet-Balances** — aktueller Kontostand je Wallet wird automatisch nachgeführt
- **EUR/USD-Kurse** — täglich von CoinGecko abgerufen, in DB gecacht
- **Statistik-Panels** — Stunden / Tag / Epoch / Monat / Jahr, je mit aktueller und vorheriger Periode
- **Epochen-Ansicht** — aktuelle Epoche als Wallet-Panel-Grid (Label, Besitzer, eingehende Qubics inkl. TX-/Event-Split, ausgehende Qubics inkl. EUR-Wert); Filter „Alle“ / „Nur mit Eingang“ plus „Alles anzeigen"-Toggle (`?ext=1`) zum Ein-/Ausblenden leerer Sub-Zeilen
- **Events-Tabelle** — getrennte Spalten für TxId und Tick, je mit Copy-Button und Explorer-Link (`/network/tx/{id}` bzw. `/network/tick/{tick}`); Kurzanzeige 5 Zeichen mit Tooltip, voller Wert beim Kopieren/Öffnen
- **Wöchentliche Snapshots** — jeden Mittwoch 12:00 UTC
- **3 Animations-Varianten** für neue Events: Push Down, Slide In, Beam Drop (einstellbar)
- **Live-Updates** per WebSocket (Events + Node-Status)
- **Steuerauswertung (Tax Engine)**:
  - FIFO- und LIFO-Berechnung konfigurier­bar
  - Länderspezifische Regeln (DE, AT, CH, u. a.) — inkl. Jahresfrist-Steuerfreiheit
  - Eröffnungspositionen (Opening Positions) für Bestandsübertrag
  - Kurspreis-Lookup je Datum direkt in der UI
  - CSV- und PDF-Export des Steuerberichts
- **Export CSV**:
  - CoinTracking-Format (PRIVATE Wallets, kommagetrennt, UTF-8 BOM)
  - Steuerberater-Format (BUSINESS Wallets, semikolongetrennt, UTF-8 BOM)
  - Mit aufgelösten Adress-Namen im Kommentar-Feld
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
docker-compose up --build   # erster Start oder nach Code-Änderungen
docker-compose up           # danach reicht das (ohne --build)
docker-compose down         # stoppen (Daten bleiben erhalten)
docker-compose down -v      # stoppen + Daten vollständig löschen
```

**→ Hauptseite: http://localhost:8080**

| Dienst    | URL                                    |
|-----------|----------------------------------------|
| Frontend  | http://localhost:8080                  |
| Backend   | http://localhost:8000/api/v1/health    |
| API-Docs  | http://localhost:8000/docs             |

> Die Ports sind auf `127.0.0.1` gebunden — von außen nicht erreichbar.

Das Backend führt beim Start automatisch `alembic upgrade head` aus — Datenbank-Migrationen laufen also ohne manuellen Eingriff.

Daten werden im Docker-Volume `qubicflow-data` gespeichert und bleiben beim Neustart erhalten.

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

### 2. Datenbank initialisieren (einmalig / nach Migrationen)

```bash
cd qubic-flow/backend
alembic upgrade head
```

> Muss nach dem ersten Checkout und nach jeder neuen Migration ausgeführt werden.  
> Erstellt alle Tabellen inkl. `events` (composite PK), `sync_state`, `address_labels`, `wallet_balances`, `opening_positions` u.a.

### 3. Starten

1. Ordner `qubic-flow` in VSCode öffnen
2. **Run & Debug** öffnen (`Ctrl+Shift+D`)
3. Oben **"QubicFlow (Full Stack)"** auswählen
4. **F5** drücken

VSCode startet Backend (Port 8000) und Frontend (Port 5173) gleichzeitig.  
**→ Hauptseite: http://localhost:5173**

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

## Nodes konfigurieren

Nodes werden über die Oberfläche unter **Einstellungen → Nodes** verwaltet.  
QubicFlow wählt beim Sync automatisch den höchst-priorisierten ONLINE-Node.

### Node-Typen

| Typ        | Beschreibung                           | Standard-URL                     |
|------------|----------------------------------------|----------------------------------|
| `RPC`      | Qubic Public RPC (REST)               | `https://rpc.qubic.org`         |
| `BOB_NODE` | Qubic BOB-Node (Core-Team, REST + WS) | `http://your-bob-node:40420`    |

### RPC-Node einrichten (Standard)

```
URL:      https://rpc.qubic.org
Typ:      RPC
Label:    Qubic RPC
Priorität: 1
```

### BOB-Node einrichten

```
URL:      https://bobnet.qubic.li:40420
Typ:      BOB_NODE
Label:    BOB Public Node
Priorität: 1
```

Der BOB-Node nutzt eine eigene REST-API auf Port **40420** — die Standard-RPC-Endpunkte (`/v1/tick-info` usw.) sind dort **nicht** verfügbar.  
QubicFlow erkennt den Typ automatisch anhand von `node_type = BOB_NODE` und verwendet die richtigen Endpunkte.

#### Verwendete BOB-Endpunkte

| Endpunkt                         | Methode | Zweck                          |
|----------------------------------|---------|--------------------------------|
| `/status`                        | GET     | Health-Check, aktueller Tick   |
| `/getQuTransferForIdentity`      | POST    | QU-Transfers je Wallet + Tick-Bereich |

#### Bekannte Einschränkungen (BOB)

- **Timestamps fehlen** in den Transfer-Log-Einträgen — Transaktionsdaten zeigen kein korrektes Datum. Eine Verbesserung über `GET /tick/{tickNumber}` ist geplant.
- Der öffentliche BOB-Node (`bobnet.qubic.li:40420`) ist ein Community-Dienst ohne garantierte Verfügbarkeit. Für Produktion empfiehlt sich ein eigener BOB-Node.

> Detaillierte BOB-API-Dokumentation: [`docs/bob_node.md`](docs/bob_node.md)

### Node-Failover

Der Sync-Job (`sync_all_wallets`, alle 60 s) wählt den Node nach folgender Logik:

1. Nur `is_active = 1`-Nodes werden berücksichtigt
2. ONLINE-Nodes haben Vorrang vor DEGRADED-Nodes
3. Bei Gleichstand entscheidet die **Priorität** (niedrigere Zahl = höhere Priorität)
4. Ist kein Node verfügbar, fällt das System auf `QUBIC_RPC_URL` aus `.env` zurück

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
│   │   │   ├── labels.py    # Adress-Namen-Auflösung
│   │   │   ├── health.py    # Gesundheitsstatus
│   │   │   ├── tax.py       # Steuerauswertung (Settings, Bericht, Opening Positions)
│   │   │   └── ws.py        # WebSocket-Endpunkt
│   │   ├── models/          # SQLAlchemy ORM-Modelle
│   │   │   ├── wallet.py
│   │   │   ├── event.py
│   │   │   ├── node.py
│   │   │   ├── sync_state.py
│   │   │   ├── sync_gap.py
│   │   │   ├── price_cache.py
│   │   │   ├── address_label.py
│   │   │   ├── snapshot.py
│   │   │   ├── settings.py
│   │   │   ├── wallet_balance.py    # Wallet-Kontostand
│   │   │   └── opening_position.py  # Eröffnungspositionen für Steuer
│   │   ├── services/        # Business-Logik
│   │   │   ├── sync_engine.py      # Tick-Sync mit Windowing (Event + TX); Node-Auswahl dynamisch
│   │   │   ├── qubic_client.py     # RPCClient + BOBClient (3x Retry, BOB-Response-Mapping)
│   │   │   ├── coingecko.py        # Kurs-Abruf mit Rate-Limit
│   │   │   ├── label_service.py    # Adress-Namen-Sync
│   │   │   ├── export_service.py   # CSV-Generierung
│   │   │   ├── health_monitor.py   # Node-Statusprüfung
│   │   │   ├── snapshot_service.py # Wöchentliche Snapshots
│   │   │   ├── balance_service.py  # Wallet-Balance-Tracking
│   │   │   ├── tax_engine.py       # Steuerberechnung (FIFO/LIFO, länderspezifisch)
│   │   │   └── scheduler.py        # APScheduler-Jobs
│   │   ├── websocket/
│   │   │   └── manager.py   # WebSocket ConnectionManager
│   │   ├── utils/
│   │   │   └── time.py      # UTC-Hilfsfunktionen
│   │   ├── config.py        # Pydantic-Settings
│   │   ├── database.py      # SQLAlchemy Engine + Session
│   │   └── main.py          # FastAPI App + Lifespan
│   ├── tests/               # pytest-Suite
│   ├── alembic/
│   │   └── versions/        # DB-Migrationen
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
│   │   ├── views/           # Seiten (Dashboard, Wallets, Assets, Statistics, Tax, etc.)
│   │   ├── components/      # AppHeader, AppNav, StatsPanel, EventsTable, WalletFilter
│   │   ├── composables/     # useWebSocket (Auto-Reconnect)
│   │   ├── stores/          # Pinia-Store (App-State)
│   │   ├── i18n/            # DE / EN Übersetzungen
│   │   ├── router/          # vue-router Routen
│   │   └── api.js           # Backend-HTTP-Client
│   ├── Dockerfile           # Multi-Stage: node build → nginx
│   ├── nginx.conf           # SPA-Routing + /api Proxy
│   ├── vite.config.js       # Dev-Proxy zu Backend
│   └── package.json
├── docs/
│   └── bob_node.md          # BOB-Node API-Referenz
├── docker-compose.yml
└── .vscode/
    ├── launch.json          # F5: Full Stack starten
    └── tasks.json           # Build-Tasks
```

---

## API-Übersicht

Alle Endpunkte unter `/api/v1/`. Interaktive Doku: `http://localhost:8000/docs`

| Methode | Pfad                                  | Beschreibung                             |
|---------|---------------------------------------|------------------------------------------|
| GET     | `/health`                             | Backend-Status                           |
| GET     | `/wallets`                            | Alle aktiven Wallets                     |
| POST    | `/wallets`                            | Wallet anlegen                           |
| PUT     | `/wallets/{id}`                       | Wallet bearbeiten                        |
| DELETE  | `/wallets/{id}`                       | Wallet soft-löschen                      |
| POST    | `/wallets/{id}/resync-tx`             | TX-Sync für ein Wallet neu starten       |
| POST    | `/wallets/resync-all`                 | Alle Wallets neu synchronisieren (insert-only) |
| GET     | `/events`                             | Events (filter: wallet_id, pagination)   |
| GET     | `/labels`                             | Adress-Labels (optional `?address=`)     |
| GET     | `/nodes`                              | Nodes                                    |
| POST    | `/nodes`                              | Node anlegen                             |
| PUT     | `/nodes/{id}`                         | Node bearbeiten                          |
| DELETE  | `/nodes/{id}`                         | Node löschen                             |
| GET     | `/stats/current`                      | Statistik-Panels (current + previous)    |
| GET     | `/stats/history`                      | Wöchentliche/monatliche Zeitreihe        |
| GET     | `/stats/snapshots`                    | Gespeicherte Weekly-Snapshots            |
| GET     | `/stats/epochs`                       | Epochen-Breakdown je Wallet (Ein-/Ausgang, TX/Event-Split) |
| GET     | `/export/cointracking`                | CoinTracking CSV (`?year=2024`)          |
| GET     | `/export/steuerberater`               | Steuerberater CSV (`?year=2024`)         |
| GET     | `/tax/settings`                       | Steuer-Einstellungen lesen               |
| PUT     | `/tax/settings`                       | Steuer-Einstellungen speichern           |
| GET     | `/tax/countries`                      | Verfügbare Länder + Steuerregeln         |
| GET     | `/tax/opening-positions`              | Eröffnungspositionen auflisten           |
| POST    | `/tax/opening-positions`              | Eröffnungsposition anlegen               |
| DELETE  | `/tax/opening-positions/{id}`         | Eröffnungsposition löschen               |
| GET     | `/tax/report`                         | Steuerbericht berechnen                  |
| GET     | `/tax/price`                          | EUR/USD-Kurs für ein Datum (`?date=`)    |
| WS      | `/ws`                                 | WebSocket (event.new, node.health)       |

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
- Kommentar-Feld enthält aufgelöste Adress-Namen: `"source_name → dest_name"`
- Download: `GET /api/v1/export/cointracking?year=2024`

### Steuerberater (BUSINESS Wallets)

- Format: Semikolon-getrennt, UTF-8 BOM
- Enthält: alle Transfers inkl. interne (mit Typ-Kennzeichnung)
- Kommentar-Feld enthält aufgelöste Adress-Namen: `"source_name → dest_name"`
- Download: `GET /api/v1/export/steuerberater?year=2024`

Beide Exporte enthalten EUR-Werte, gerundet auf 2 Dezimalstellen.

---

## Steuerauswertung (Tax Engine)

Die **Tax**-Seite berechnet Gewinne und Einkommen nach länderspezifischen Regeln direkt in der App.

### Konfiguration

Unter **Steuer → Einstellungen** (oder Tax → Settings):

| Einstellung   | Beschreibung                                      | Standard |
|---------------|---------------------------------------------------|----------|
| Land          | Steuerjurisdiktion (DE, AT, CH, …)               | DE       |
| Methode       | Berechnungsreihenfolge (FIFO / LIFO)             | FIFO     |

### Unterstützte Länder

Die verfügbaren Länder und ihre Regeln liefert `GET /api/v1/tax/countries`.  
Für Deutschland (DE) gilt u. a.: Gewinne aus Verkäufen nach mehr als 12 Monaten Haltedauer sind steuerfrei.

### Eröffnungspositionen (Opening Positions)

Wer bereits vor dem ersten aufgezeichneten Event QU besessen hat, kann den Bestand als **Eröffnungsposition** eintragen:

- Wallet, Datum, Menge (QU), optionaler EUR-/USD-Kurs, Notiz
- Verwaltung über `GET/POST/DELETE /api/v1/tax/opening-positions`
- Der Kurs zum eingetragenen Datum kann über `GET /api/v1/tax/price?date=YYYY-MM-DD` nachgeschlagen werden

### Steuerbericht

`GET /api/v1/tax/report?year=2024&mode=private&wallet_ids=…` liefert:

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

Der Bericht kann direkt in der UI als **CSV** oder **PDF** heruntergeladen werden.

---

## Hintergrund-Jobs

| Job                | Intervall              | Beschreibung                                      |
|--------------------|------------------------|---------------------------------------------------|
| `sync_all_wallets` | alle 60 Sekunden       | Event-Sync + TX-Sync + Balance-Update; wählt dynamisch den besten verfügbaren Node |
| `health_monitor`   | alle 30 Sekunden       | Node-Status prüfen (`/v1/tick-info` für RPC, `/status` für BOB), WS-Broadcast |
| `sync_labels`      | alle 24 Stunden        | Adress-Namen-Auflösung (address_labels, tokens, issuances) |
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

---

## Technologie-Stack

### Backend

| Paket              | Version   | Zweck                        |
|--------------------|-----------|------------------------------|
| FastAPI            | 0.115     | REST + WebSocket             |
| SQLAlchemy         | 2.0       | ORM + SQLite (WAL)           |
| Alembic            | 1.14      | DB-Migrationen               |
| Pydantic           | 2.10      | Validierung                  |
| APScheduler        | 3.10      | Hintergrundjobs              |
| httpx              | 0.28      | Async HTTP (RPC, CoinGecko)  |
| uvicorn            | 0.32      | ASGI-Server                  |

### Frontend

| Paket         | Version  | Zweck                          |
|---------------|----------|--------------------------------|
| Vue 3         | 3.5      | UI-Framework                   |
| Vite          | 6.0      | Build-Tool + Dev-Server        |
| Pinia         | 2.3      | State Management               |
| vue-router    | 4.5      | SPA-Routing                    |
| Tailwind CSS  | 3.4      | Styling                        |
| Chart.js      | 4.4      | Snapshot-Liniendiagramm        |
| i18next       | 24.1     | DE/EN-Übersetzungen            |
| jsPDF         | 2.x      | PDF-Export (Steuerbericht)     |

### Infrastruktur

| Komponente  | Details                              |
|-------------|--------------------------------------|
| Container   | Docker + docker-compose              |
| Webserver   | nginx (alpine) für Frontend + Proxy  |
| Datenbank   | SQLite mit WAL-Modus                 |
| Datenpfad   | Docker-Volume `qubicflow-data`       |
