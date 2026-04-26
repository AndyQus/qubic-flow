# QubicFlow

Selbst gehosteter Qubic Wallet Tracker für steuerliche Dokumentation (BMF-konform).  
Unterstützt unbegrenzte Wallets (PRIVAT / GESCHÄFTLICH), automatische EUR/USD-Kurse, Live-Events per WebSocket, Steuerauswertung (FIFO/LIFO/HIFO/AVCO, länderspezifische Regeln) sowie CSV-Export für CoinTracking und den Steuerberater.

---

## Inhaltsverzeichnis

- [Funktionen](#funktionen)
- [Voraussetzungen](#voraussetzungen)
- [Start mit Docker](#start-mit-docker)
- [Start in VSCode (Entwicklung)](#start-in-vscode-entwicklung)
- [Konfiguration (.env)](#konfiguration-env)
- [Nodes konfigurieren](#nodes-konfigurieren)
- [Projektstruktur](#projektstruktur)
- [API-Übersicht](#api-übersicht)
- [Export / Steuer-CSVs](#export--steuer-csvs)
- [Steuerauswertung](#steuerauswertung)
- [Hintergrund-Jobs](#hintergrund-jobs)
- [Tests ausführen](#tests-ausführen)
- [Technologie-Stack](#technologie-stack)
- [Deployment & Veröffentlichung](#deployment--veröffentlichung)

---

## Funktionen

- **Unbegrenzte Wallets** — PRIVAT und GESCHÄFTLICH, verwaltbar über die Oberfläche
- **Dual-Node-Unterstützung** — Standard-RPC (`rpc.qubic.org`) **und** BOB-Node (`bobnet.qubic.li`) werden unterstützt; der beste verfügbare Node wird automatisch gewählt
- **Event-Sync** — automatisch alle 60 Sekunden; RPC-Nodes via `getEventLogs` (nutzt `transactionHash` **direkt als Primärschlüssel** — die gleiche 60-Zeichen-ID, die der Qubic-Explorer zeigt), BOB-Nodes via `POST /getQuTransferForIdentity`. SC-interne Events ohne `transactionHash` fallen auf die numerische `logId` zurück (der 16-Zeichen-`logDigest` ist dann auch die Explorer-ID für diese Events).
- **TX-Sync** — Transfer-Transaktionen via Qubic Archiver API, dedupliziert gegen Events; probiert mehrere Feldnamen (`transactionId`, `txId`, `id`, `digest`, `hash`) und bevorzugt die echte 60-Zeichen-Qubic-TxID. Stub-Abgleich: bestehende Event-Zeilen werden anhand `(Tick, Quelle, Ziel, Betrag)` gefunden und mit der echten TxID aktualisiert (Nutzerfelder wie Kommentar/Position bleiben erhalten). Chunk-basierter Fortschritt mit Checkpoint je Chunk — fehlgeschlagene Chunks landen als Synchronisierungslücke und setzen `last_tx_tick` nicht zurück. Erstsynchronisierung startet bei `current_tick − 500 000` (Archiver-Aufbewahrungszeitraum), nicht bei Tick 1.
- **Intelligente Smart-Contract-Klassifikation** — `logType=0`-Transfers werden über Adress-Labels als `TX` (normaler Transfer) oder `EVENT` (Smart Contract / Token Issuer, z. B. QX, Qearn) eingeordnet
- **Manueller Resync** — Schaltfläche „Daten neu abrufen" in den Einstellungen (`POST /wallets/resync-all`) setzt Sync-Zähler zurück und importiert nur fehlende Einträge (bestehende Datensätze bleiben unverändert)
- **Tick-Range-Fenstertechnik** — überwindet das 10.000-Datensätze-Limit der RPC-API durch rekursives Halbieren
- **Adress-Namensauflösung** — automatische Auflösung von Qubic-Adressen zu Tokens/Labels (Assets-Seite + CSV)
- **Assets-Seite** — Übersicht aller Smart Contracts und Tokens mit Ticker, Kategorie, Dezimalstellen, Website
- **Wallet-Kontostände** — aktueller Kontostand je Wallet wird automatisch nachgeführt
- **EUR/USD-Kurse** — täglich von CoinGecko abgerufen, in der Datenbank zwischengespeichert
- **Statistik-Panels** — Stunden / Tag / Epoche / Monat / Jahr, je mit aktueller und vorheriger Periode
- **Epochen-Ansicht** — aktuelle Epoche als Wallet-Panel-Raster (Label, Besitzer, eingehende Qubics inkl. TX-/Event-Aufteilung, ausgehende Qubics inkl. EUR-Wert); Filter „Alle" / „Nur mit Eingang" plus „Alles anzeigen"-Umschalter (`?ext=1`) zum Ein-/Ausblenden leerer Unterzeilen
- **Events-Tabelle** — getrennte Spalten für TxId und Tick, je mit Kopier-Schaltfläche und Explorer-Link (`/network/tx/{id}` bzw. `/network/tick/{tick}`); Kurzanzeige 5 Zeichen mit Tooltip, voller Wert beim Kopieren/Öffnen. Nur echte 60-Zeichen-Qubic-TxIDs werden angezeigt — SC-interne Events ohne Nutzer-TX zeigen in der TxID-Spalte einen Bindestrich.
- **Wöchentliche Schnappschüsse** — jeden Mittwoch 12:00 UTC
- **3 Animations-Varianten** für neue Events: Herunterschieben, Einfahren, Balken-Einblenden (einstellbar)
- **Live-Updates** per WebSocket (Events + Node-Status)
- **Steuerauswertung**:
  - FIFO, LIFO, HIFO und AVCO als Berechnungsmethode wählbar
  - Länderspezifische Regeln (DE, AT, CH u. a.) — inkl. Jahresfrist-Steuerfreiheit
  - Eröffnungspositionen für den Bestandsübertrag
  - Kurspreis-Nachschlag je Datum direkt in der Oberfläche
  - CSV- und PDF-Export des Steuerberichts
- **CSV-Export**:
  - CoinTracking-Format (PRIVAT-Wallets, kommagetrennt, UTF-8 BOM)
  - Steuerberater-Format (GESCHÄFTLICH-Wallets, semikolongetrennt, UTF-8 BOM)
  - Aufgelöste Adress-Namen im Kommentarfeld
- **Interne Transfers** — Wallet-zu-Wallet-Transfers werden beim Export steuerlich neutral behandelt
- **Deutsch / Englisch** Benutzeroberfläche, Dunkel- / Hellmodus
- **Einstellungen in Reitern** — `Darstellung` (Währung, Schrift, Theme, Sprache, Animationen), `Steuern` (Land/Methode, Persönliche/Geschäftsdaten), `Daten` (Export, Sicherung/Wiederherstellung, Ledger-Import, Resync); aktiver Reiter wird per URL-Abfrageparameter (`?tab=…`) gespiegelt
- **Vollständig containerisiert** — ein `docker-compose up --build` genügt

---

## Voraussetzungen

### Docker (empfohlen für den Produktivbetrieb)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows / Mac / Linux)
- `docker-compose` (bei Docker Desktop inklusive)

### Lokale Entwicklung (VSCode)

- Python 3.12+
- Node.js 22+
- VSCode mit den Erweiterungen **Python** (ms-python.python) und **Debugpy**

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
| API-Doku  | http://localhost:8000/docs             |

> Die Ports sind auf `127.0.0.1` gebunden — von außen nicht erreichbar.

Das Backend führt beim Start automatisch `alembic upgrade head` aus — Datenbankmigrationen laufen ohne manuellen Eingriff.

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

> Muss nach dem ersten Auschecken und nach jeder neuen Migration ausgeführt werden.  
> Erstellt alle Tabellen inkl. `events` (zusammengesetzter Primärschlüssel), `sync_state`, `address_labels`, `wallet_balances`, `opening_positions` u. a.

### 3. Starten

1. Ordner `qubic-flow` in VSCode öffnen
2. **Ausführen und Debuggen** öffnen (`Strg+Umschalt+D`)
3. Oben **„QubicFlow (Full Stack)"** auswählen
4. **F5** drücken

VSCode startet Backend (Port 8000) und Frontend (Port 5173) gleichzeitig.  
**→ Hauptseite: http://localhost:5173**

Der Vite-Entwicklungsserver leitet `/api/...`-Anfragen automatisch an das Backend weiter (Proxy in `vite.config.js`).  
Python-Haltepunkte funktionieren direkt in den `.py`-Dateien.

### Einzelstart (optional)

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
QubicFlow wählt beim Sync automatisch den höchstpriorisierten ONLINE-Node.

### Node-Typen

| Typ        | Beschreibung                              | Standard-URL                     |
|------------|-------------------------------------------|----------------------------------|
| `RPC`      | Qubic Public RPC (REST)                  | `https://rpc.qubic.org`         |
| `BOB_NODE` | Qubic BOB-Node (Core-Team, REST + WS)    | `http://eigener-bob-node:40420` |

### RPC-Node einrichten (Standard)

```
URL:       https://rpc.qubic.org
Typ:       RPC
Label:     Qubic RPC
Priorität: 1
```

### BOB-Node einrichten

```
URL:       https://bobnet.qubic.li:40420
Typ:       BOB_NODE
Label:     BOB Public Node
Priorität: 1
```

Der BOB-Node nutzt eine eigene REST-API auf Port **40420** — die Standard-RPC-Endpunkte (`/v1/tick-info` usw.) sind dort **nicht** verfügbar.  
QubicFlow erkennt den Typ automatisch anhand von `node_type = BOB_NODE` und verwendet die richtigen Endpunkte.

#### Verwendete BOB-Endpunkte

| Endpunkt                         | Methode | Zweck                                 |
|----------------------------------|---------|---------------------------------------|
| `/status`                        | GET     | Statusprüfung, aktueller Tick         |
| `/getQuTransferForIdentity`      | POST    | QU-Transfers je Wallet + Tick-Bereich |

#### Bekannte Einschränkungen (BOB)

- **Zeitstempel fehlen** in den Transfer-Einträgen — Transaktionsdaten zeigen kein korrektes Datum. Eine Verbesserung über `GET /tick/{tickNumber}` ist geplant.
- Der öffentliche BOB-Node (`bobnet.qubic.li:40420`) ist ein Community-Dienst ohne garantierte Verfügbarkeit. Für den Produktivbetrieb empfiehlt sich ein eigener BOB-Node.

> Ausführliche BOB-API-Dokumentation: [`docs/bob_node.md`](docs/bob_node.md)

### Node-Ausfallsicherung

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

# CoinGecko (optional: API-Schlüssel für höhere Anfragelimits)
COINGECKO_API_URL=https://api.coingecko.com/api/v3
COINGECKO_API_KEY=

# CORS (kommagetrennte Ursprünge)
CORS_ORIGINS=http://localhost:8080,http://localhost:5173

# Protokollierung
LOG_LEVEL=INFO
TZ=UTC
```

> Die `.env`-Datei ist in `.gitignore` eingetragen — niemals einchecken.  
> Ohne `.env` starten Backend und Docker-Container mit den eingebauten Standardwerten.

---

## Projektstruktur

```
qubic-flow/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # REST-Endpunkte
│   │   │   ├── wallets.py   # Wallet CRUD
│   │   │   ├── events.py    # Event-Liste mit Seitenweise-Abruf
│   │   │   ├── nodes.py     # Node CRUD + Reihenfolge
│   │   │   ├── stats.py     # Statistik-Panels
│   │   │   ├── export.py    # CSV-Download
│   │   │   ├── labels.py    # Adress-Namensauflösung
│   │   │   ├── health.py    # Systemstatus
│   │   │   ├── tax.py       # Steuerauswertung (Einstellungen, Bericht, Eröffnungspositionen)
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
│   │   ├── services/        # Geschäftslogik
│   │   │   ├── sync_engine.py      # Tick-Sync mit Fenstertechnik (Event + TX); Node-Auswahl dynamisch
│   │   │   ├── qubic_client.py     # RPCClient + BOBClient (3× Wiederholung, BOB-Antwort-Mapping)
│   │   │   ├── coingecko.py        # Kursabruf mit Anfragelimit
│   │   │   ├── label_service.py    # Adress-Namen-Sync
│   │   │   ├── export_service.py   # CSV-Erstellung
│   │   │   ├── health_monitor.py   # Node-Statusprüfung
│   │   │   ├── snapshot_service.py # Wöchentliche Schnappschüsse
│   │   │   ├── balance_service.py  # Wallet-Kontostand-Nachführung
│   │   │   ├── tax_engine.py       # Steuerberechnung (FIFO/LIFO/HIFO/AVCO, länderspezifisch)
│   │   │   └── scheduler.py        # APScheduler-Jobs
│   │   ├── websocket/
│   │   │   └── manager.py   # WebSocket-Verbindungsverwaltung
│   │   ├── utils/
│   │   │   └── time.py      # UTC-Hilfsfunktionen
│   │   ├── config.py        # Pydantic-Einstellungen
│   │   ├── database.py      # SQLAlchemy Engine + Sitzung
│   │   └── main.py          # FastAPI App + Lebenszyklus
│   ├── tests/               # pytest-Suite (test_tax_engine.py, test_coingecko.py)
│   ├── alembic/
│   │   └── versions/        # Datenbankmigrationen
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
│   │   ├── views/           # Seiten (Dashboard, Wallets, Assets, Statistiken, Steuer usw.)
│   │   ├── components/      # AppHeader, AppNav, StatsPanel, EventsTable, WalletFilter
│   │   ├── composables/     # useWebSocket (automatische Wiederverbindung)
│   │   ├── stores/          # Pinia-Zustandsspeicher
│   │   ├── i18n/            # DE / EN Übersetzungen
│   │   ├── router/          # vue-router Routen
│   │   └── api.js           # Backend-HTTP-Client
│   ├── src/tests/unit/      # Vitest Unit-Tests
│   ├── tests/e2e/           # Playwright End-to-End-Tests
│   ├── vitest.config.js     # Vitest-Konfiguration
│   ├── playwright.config.js # Playwright-Konfiguration
│   ├── Dockerfile           # Mehrstufig: Node-Build → nginx
│   ├── nginx.conf           # SPA-Routing + /api Proxy
│   ├── vite.config.js       # Entwicklungs-Proxy zum Backend
│   └── package.json
├── docs/
│   └── bob_node.md          # BOB-Node API-Referenz
├── docker-compose.yml
└── .vscode/
    ├── launch.json          # F5: Full Stack starten
    └── tasks.json           # Build-Aufgaben
```

---

## API-Übersicht

Alle Endpunkte unter `/api/v1/`. Interaktive Dokumentation: `http://localhost:8000/docs`

| Methode | Pfad                                  | Beschreibung                                          |
|---------|---------------------------------------|-------------------------------------------------------|
| GET     | `/health`                             | Backend-Status                                        |
| GET     | `/wallets`                            | Alle aktiven Wallets                                  |
| POST    | `/wallets`                            | Wallet anlegen                                        |
| PUT     | `/wallets/{id}`                       | Wallet bearbeiten                                     |
| DELETE  | `/wallets/{id}`                       | Wallet als gelöscht markieren                         |
| POST    | `/wallets/{id}/resync-tx`             | TX-Sync für ein Wallet neu starten                    |
| POST    | `/wallets/resync-all`                 | Alle Wallets neu synchronisieren (nur fehlende)       |
| GET     | `/events`                             | Events (Filter: wallet_id, seitenweise)               |
| GET     | `/labels`                             | Adress-Labels (optional `?address=`)                  |
| GET     | `/nodes`                              | Nodes auflisten                                       |
| POST    | `/nodes`                              | Node anlegen                                          |
| PUT     | `/nodes/{id}`                         | Node bearbeiten                                       |
| DELETE  | `/nodes/{id}`                         | Node löschen                                          |
| GET     | `/stats/current`                      | Statistik-Panels (Aktuell + Vorperiode)               |
| GET     | `/stats/history`                      | Wöchentliche/monatliche Zeitreihe                     |
| GET     | `/stats/snapshots`                    | Gespeicherte Wochenschnappschüsse                     |
| GET     | `/stats/epochs`                       | Epochen-Aufschlüsselung je Wallet (Ein-/Ausgang, TX/Event-Aufteilung) |
| GET     | `/export/cointracking`                | CoinTracking-CSV (`?year=2024`)                       |
| GET     | `/export/steuerberater`               | Steuerberater-CSV (`?year=2024`)                      |
| GET     | `/tax/settings`                       | Steuereinstellungen lesen                             |
| PUT     | `/tax/settings`                       | Steuereinstellungen speichern                         |
| GET     | `/tax/countries`                      | Verfügbare Länder + Steuerregeln                      |
| GET     | `/tax/opening-positions`              | Eröffnungspositionen auflisten                        |
| POST    | `/tax/opening-positions`              | Eröffnungsposition anlegen                            |
| DELETE  | `/tax/opening-positions/{id}`         | Eröffnungsposition löschen                            |
| GET     | `/tax/report`                         | Steuerbericht berechnen                               |
| GET     | `/tax/price`                          | EUR/USD-Kurs für ein Datum (`?date=`)                 |
| WS      | `/ws`                                 | WebSocket (event.new, node.health)                    |

### Wallet-Adresse

Qubic-Wallet-Adressen bestehen aus **genau 60 Großbuchstaben** (A–Z).  
Beispiel: `AAAAABBBBBCCCCCDDDDDEEEEEFFFFFGGGGGHHHHHIIIIIIJJJJJKKKKKLLLLL`

---

## Export / Steuer-CSVs

### CoinTracking (PRIVAT-Wallets)

- Format: kommagetrennt, UTF-8 BOM
- Enthält: Einzahlungen und Auszahlungen
- Interne Transfers (Wallet → Wallet) werden **automatisch ausgeschlossen**
- `is_internal` wird beim Export dynamisch berechnet — auch rückwirkend korrekt, wenn neue Wallets hinzugefügt werden
- Kommentarfeld enthält aufgelöste Adress-Namen: `„Quellname → Zielname"`
- Download: `GET /api/v1/export/cointracking?year=2024`

### Steuerberater (GESCHÄFTLICH-Wallets)

- Format: semikolongetrennt, UTF-8 BOM
- Enthält: alle Transfers inkl. interne (mit Typkennzeichnung)
- Kommentarfeld enthält aufgelöste Adress-Namen: `„Quellname → Zielname"`
- Download: `GET /api/v1/export/steuerberater?year=2024`

Beide Exporte enthalten EUR-Werte, gerundet auf 2 Dezimalstellen.

---

## Steuerauswertung

Die **Steuer**-Seite berechnet Gewinne und Einkommen nach länderspezifischen Regeln direkt in der Anwendung.

### Konfiguration

Unter **Einstellungen → Steuern**:

| Einstellung | Beschreibung                                      | Standard |
|-------------|---------------------------------------------------|----------|
| Land        | Steuerjurisdiktion (DE, AT, CH, …)               | DE       |
| Methode     | Berechnungsreihenfolge (FIFO / LIFO / HIFO / AVCO) | FIFO   |

### Unterstützte Länder

Die verfügbaren Länder und ihre Regeln liefert `GET /api/v1/tax/countries`.  
Für Deutschland (DE) gilt u. a.: Gewinne aus Verkäufen nach mehr als 12 Monaten Haltedauer sind steuerfrei.

### Eröffnungspositionen

Wer bereits vor dem ersten aufgezeichneten Event QU besessen hat, kann den Bestand als **Eröffnungsposition** eintragen:

- Wallet, Datum, Menge (QU), optionaler EUR-/USD-Kurs, Notiz
- Verwaltung über `GET/POST/DELETE /api/v1/tax/opening-positions`
- Der Kurs zum eingetragenen Datum kann über `GET /api/v1/tax/price?date=JJJJ-MM-TT` nachgeschlagen werden

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

Der Bericht kann direkt in der Oberfläche als **CSV** oder **PDF** heruntergeladen werden.

---

## Hintergrund-Jobs

| Job                | Intervall            | Beschreibung                                                              |
|--------------------|----------------------|---------------------------------------------------------------------------|
| `sync_all_wallets` | alle 60 Sekunden     | Event-Sync + TX-Sync + Kontostand-Aktualisierung; wählt dynamisch den besten verfügbaren Node |
| `health_monitor`   | alle 30 Sekunden     | Node-Status prüfen (`/v1/tick-info` für RPC, `/status` für BOB), WebSocket-Broadcast |
| `sync_labels`      | alle 24 Stunden      | Adress-Namensauflösung (address_labels, tokens, issuances)               |
| `weekly_snapshot`  | Mi 12:00 UTC (Cron)  | Wöchentlichen Aggregations-Schnappschuss speichern                        |

Jobs laufen mit `max_instances=1` und `coalesce=True` — kein paralleler Doppellauf.

Wenn der RPC für einen Tick-Bereich weniger Daten liefert als erwartet (`validForTick < to_tick`), wird eine Synchronisierungslücke angelegt und der fehlende Bereich beim nächsten Lauf erneut versucht.

---

## Tests ausführen

### Backend (pytest)

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/ -v
```

| Datei                      | Tests | Beschreibung                                                         |
|----------------------------|-------|----------------------------------------------------------------------|
| `tests/test_tax_engine.py` | 27    | Lot-Abgleich (FIFO/LIFO/HIFO/AVCO), Haltedauer, Steuerregeln, Datumsparser |
| `tests/test_coingecko.py`  | 6     | Kurs-Zwischenspeicher Treffer/Fehltreffer, Netzwerkfehler, Seiteneffektfreiheit |

### Frontend — Unit-Tests (Vitest)

```bash
cd frontend
npm test              # einmalig ausführen
npm run test:watch    # im Beobachtungsmodus
```

| Datei                                  | Tests | Beschreibung                                             |
|----------------------------------------|-------|----------------------------------------------------------|
| `src/tests/unit/useQubicUtils.test.js` | 12    | `explorerUrl`, `txUrl`, `tickUrl`, `shortAddr`, `maskLabel` |
| `src/tests/unit/store.test.js`         | 17    | Pinia-Speicher: `locale`, `filteredWallets`, `activeNode`, `prependEvent`, localStorage |

### Frontend — End-to-End-Tests (Playwright)

```bash
cd frontend
npx playwright install   # einmalig: Browser herunterladen
npm run test:e2e         # alle E2E-Tests ausführen
```

Setzt einen laufenden Backend-Server voraus. Der Vite-Entwicklungsserver wird von Playwright automatisch gestartet.

| Datei                          | Tests | Beschreibung                                      |
|--------------------------------|-------|---------------------------------------------------|
| `tests/e2e/dashboard.spec.js`  | 4     | Titel, Navigation, Event-Tabelle, Kopfbereich     |
| `tests/e2e/navigation.spec.js` | 8     | Seitenwechsel, Einstellungs-Reiter, URL-Persistenz |
| `tests/e2e/wallets.spec.js`    | 6     | Wallet-Liste, Hinzufügen-Dialog, Filterschaltflächen |

---

## Technologie-Stack

### Backend

| Paket       | Version | Zweck                              |
|-------------|---------|------------------------------------|
| FastAPI     | 0.115   | REST + WebSocket                   |
| SQLAlchemy  | 2.0     | ORM + SQLite (WAL)                 |
| Alembic     | 1.14    | Datenbankmigrationen               |
| Pydantic    | 2.10    | Validierung                        |
| APScheduler | 3.10    | Hintergrundjobs                    |
| httpx       | 0.28    | Asynchrones HTTP (RPC, CoinGecko)  |
| uvicorn     | 0.32    | ASGI-Server                        |
| pytest      | 8.3     | Testframework                      |

### Frontend

| Paket        | Version | Zweck                            |
|--------------|---------|----------------------------------|
| Vue 3        | 3.5     | UI-Framework                     |
| Vite         | 6.0     | Build-Werkzeug + Entwicklungsserver |
| Pinia        | 2.3     | Zustandsverwaltung               |
| vue-router   | 4.5     | SPA-Routing                      |
| Tailwind CSS | 3.4     | Gestaltung                       |
| Chart.js     | 4.4     | Liniendiagramm für Schnappschüsse |
| i18next      | 24.1    | DE/EN-Übersetzungen              |
| jsPDF        | 2.x     | PDF-Export (Steuerbericht)       |
| Vitest       | 2.1     | Unit-Tests (happy-dom)           |
| Playwright   | 1.49    | End-to-End-Tests                 |

### Infrastruktur

| Komponente | Details                                |
|------------|----------------------------------------|
| Container  | Docker + docker-compose                |
| Webserver  | nginx (alpine) für Frontend + Proxy    |
| Datenbank  | SQLite mit WAL-Modus                   |
| Datenpfad  | Docker-Volume `qubicflow-data`         |

---

## Deployment & Veröffentlichung

QubicFlow wird als Multi-Arch Docker Image (linux/amd64 + linux/arm64) auf Docker Hub veröffentlicht und ist über den Umbrel Community App Store installierbar.

### Branch-Strategie

```
develop  →  Entwicklung, Tests, Bugfixes  (kein automatischer Build)
   ↓  merge
main     →  GitHub Actions startet automatisch  →  Docker Hub + Umbrel Store
```

- Auf `develop` wird entwickelt — beliebig viele Commits, kein Build
- Jeder Merge zu `main` löst den vollständigen Release-Prozess aus
- Für offizielle Versionen: `git tag v1.2.3 && git push origin v1.2.3`

### GitHub Actions Workflow (`.github/workflows/docker-publish.yml`)

Der Workflow besteht aus 4 aufeinanderfolgenden Jobs:

| Job | Beschreibung |
|-----|--------------|
| `prepare` | Berechnet die Version: `YYYY.MM.DD` bei Branch-Merge, Semver `1.2.3` bei Tag |
| `build-backend` | Cython-Kompilierung + Multi-Arch Docker Image → Docker Hub |
| `build-frontend` | Vue-Build + nginx Docker Image → Docker Hub |
| `update-umbrel-store` | Aktualisiert automatisch die Versionsnummern im Store-Repo |

**Versionierung:**
- Merge zu `main` → Version `2025.04.25` (Datum des Builds)
- Tag `v1.2.3` → Version `1.2.3` (explizite Semver-Version)

### Quellcode-Schutz (Cython)

Die folgenden sensitiven Services werden vor dem Docker-Push zu `.so`-Binaries kompiliert — der Python-Quellcode ist im veröffentlichten Image nicht lesbar:

- `backend/app/services/tax_engine.py`
- `backend/app/services/sync_engine.py`
- `backend/app/services/export_service.py`
- `backend/app/services/label_service.py`

Das Kompilier-Script liegt unter `backend/compile.py`. Der `backend/Dockerfile` verwendet einen Multi-Stage-Build: Stage 1 kompiliert und löscht die `.py`-Dateien, Stage 2 enthält nur das saubere Runtime-Image.

### Erforderliche GitHub Secrets

Im `qubic-flow` Repository unter Settings → Secrets and variables → Actions:

| Secret | Wert |
|--------|------|
| `DOCKERHUB_USERNAME` | Docker Hub Benutzername |
| `DOCKERHUB_TOKEN` | Docker Hub Personal Access Token |
| `STORE_REPO_TOKEN` | GitHub Fine-grained PAT für `qubicflow-umbrel-store` (Contents: Read+Write) |

### Ersten Release auslösen

```bash
git checkout main
git merge develop
git push origin main
# → Build startet automatisch auf GitHub Actions
```

### Umbrel Installation

Community App Store URL im Umbrel-Gerät eintragen:

```
https://github.com/AndyQus/qubicflow-umbrel-store
```

Umbrel → App Store → ⋮ → Community App Stores → URL einfügen → QubicFlow installieren
