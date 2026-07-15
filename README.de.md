# QubicFlow

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/open%20source-%E2%9D%A4-brightgreen.svg)](https://github.com/AndyQus/qubic-flow)

Selbst gehosteter, **Open-Source** Qubic Wallet Tracker für steuerliche Dokumentation (BMF-konform).  
Unterstützt unbegrenzte Wallets (PRIVAT / GESCHÄFTLICH), automatische EUR/USD-Kurse, Live-Events per WebSocket, Steuerauswertung (FIFO/LIFO/HIFO/AVCO, länderspezifische Regeln inkl. 🇩🇰 Dänemark) sowie CSV-Export für CoinTracking, Koinly, Blockpit und den Steuerberater.

**GitHub:** https://github.com/AndyQus/qubic-flow

![Dashboard](https://raw.githubusercontent.com/AndyQus/qubicflow-umbrel-store/main/qfstore-qubicflow/gallery/1.png)

---

## Inhaltsverzeichnis

- [Funktionen](#funktionen)
- [Voraussetzungen](#voraussetzungen)
- [Start mit UmbrelOS](#start-mit-umbrelos)
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
- **Intelligente Smart-Contract-Klassifikation** — `logType=0`-Transfers werden über Adress-Labels als `TX` (normaler Transfer) oder `EVENT` (Smart Contract / Token Issuer, z. B. QX, Qearn, QMine) eingeordnet
- **Token-Dividenden-Erfassung** — Qubics, die über Token-Ausschüttungen eingehen (z. B. QMine-Dividenden), werden automatisch erkannt: Die Token-Issuer-Adressen werden täglich vom Qubic-Assets-Register (`static.qubic.org`) synchronisiert; eingehende Transfers von diesen Adressen werden als EVENTs klassifiziert und je Epoche mit Datum, Betrag und EUR/USD-Kurs vollständig erfasst
- **Manueller Resync** — Schaltfläche „Daten neu abrufen" in den Einstellungen (`POST /wallets/resync-all`) setzt Sync-Zähler zurück und importiert nur fehlende Einträge (bestehende Datensätze bleiben unverändert)
- **Tick-Range-Fenstertechnik** — überwindet das 10.000-Datensätze-Limit der RPC-API durch rekursives Halbieren
- **Adress-Namensauflösung** — automatische Auflösung von Qubic-Adressen zu Tokens/Labels (Assets-Seite + CSV)
- **Assets-Seite** — Übersicht aller Smart Contracts und Tokens mit Ticker, Kategorie, Dezimalstellen, Website
- **Wallet-Kontostände** — aktueller Kontostand je Wallet wird automatisch nachgeführt
- **EUR/USD-Kurse** — täglich von CoinGecko abgerufen, in der Datenbank zwischengespeichert
- **Statistik-Panels** — Stunden / Tag / Epoche / Monat / Jahr, je mit aktueller und vorheriger Periode
- **Epochen-Ansicht** — alle Epochen navigierbar als Wallet-Panel-Raster (Label, Besitzer, eingehende Qubics inkl. TX-/Event-Aufteilung, ausgehende Qubics inkl. EUR-Wert); Dividenden aus Smart-Contract-Ausschüttungen und Token-Payouts (z. B. QX-Shares, Qearn, QMine) werden je Epoche als EVENTs automatisch erkannt und sind vollständig sichtbar; Filter „Alle" / „Nur mit Eingang" plus „Alles anzeigen"-Umschalter (`?ext=1`) zum Ein-/Ausblenden leerer Unterzeilen
- **Events-Tabelle** — getrennte Spalten für TxId und Tick, je mit Kopier-Schaltfläche und Explorer-Link (`/network/tx/{id}` bzw. `/network/tick/{tick}`); Kurzanzeige 5 Zeichen mit Tooltip, voller Wert beim Kopieren/Öffnen. Nur echte 60-Zeichen-Qubic-TxIDs werden angezeigt — SC-interne Events ohne Nutzer-TX zeigen in der TxID-Spalte einen Bindestrich.
- **Wöchentliche Schnappschüsse** — jeden Mittwoch 12:00 UTC
- **Bestandsverlauf** — automatische Bestandserfassung aller aktiven Wallets in drei einzeln aktivierbaren Serien: stündlich, täglich (12:00 UTC) und wöchentlich zum Epochenwechsel (Mittwoch ab 12:00 UTC; gewartet wird, bis der RPC die neue Epoche meldet). Jeder Datensatz speichert Bestand, Differenz zum letzten Datensatz, Zu-/Abfluss im Intervall, Tick, Epoche und EUR/USD-Kurs. Neuer Statistik-Tab mit allen Sheets (Ledger-Übersicht, absolute Bestände je Wallet mit Konsistenz-Kontrolle gegen die erfassten Zu-/Abflüsse, Ledger je Besitzer, Transfer, Transaktionen), „Jetzt erfassen"-Testbutton, Inline-Bearbeitung (geänderte Werte werden markiert, der ursprüngliche Messwert bleibt intern als Nachweis erhalten) und manuellen Datensätzen. Erzeugt drei Excel-Dateien im persönlichen Ledger-Layout — Wallet-Spalten und Besitzer-Sheets entstehen dynamisch aus der lokalen Datenbank — nach jeder Erfassung/Änderung neu geschrieben und jederzeit herunterladbar. Konfiguration auf einem eigenen Einstellungen-Tab „Bestandsverlauf" mit Zurücksetzen je Serie (mit Sicherheitsabfrage) und integrierter Kurz-Doku zur Funktionsweise. Alle Ansichten umfassen nur den Erfassungszeitraum (ab der ersten Erfassung einer Serie); die App zeigt Zeiten in der lokalen Zeitzone des Browsers, Excel-Datumsangaben nutzen die Server-Zeitzone (`TZ`-Umgebungsvariable, Standard UTC)
- **3 Animations-Varianten** für neue Events: Herunterschieben, Einfahren, Balken-Einblenden (einstellbar)
- **Live-Updates** per WebSocket (Events + Node-Status)
- **Steuerauswertung**:
  - FIFO, LIFO, HIFO und AVCO als Berechnungsmethode wählbar
  - Länderspezifische Regeln (DE, AT, CH, DK u. a.) — inkl. Jahresfrist-Steuerfreiheit (DE) und dänischem Modell (FIFO verpflichtend, Gewinne und abzugsfähige Verluste getrennt, keine Verrechnung)
  - Einkommens-Events (Dividenden, Rewards) werden bei Zufluss versteuert und mit Marktwert-Kostenbasis eingebucht — keine Doppelbesteuerung beim späteren Verkauf
  - Ehrliche Berichtswährung: Länder ohne erfasste Lokalwährungskurse (CHF, GBP, DKK, …) werden in EUR berechnet **und ausgewiesen**
  - Eröffnungspositionen für den Bestandsübertrag
  - Kurspreis-Nachschlag je Datum direkt in der Oberfläche
  - CSV- und PDF-Export des Steuerberichts
- **CSV-Export**:
  - CoinTracking-Format (PRIVAT-Wallets, kommagetrennt, UTF-8 BOM)
  - Koinly-Universal-Format (PRIVAT-Wallets)
  - Blockpit-Import-Format (PRIVAT-Wallets)
  - Steuerberater-Format (GESCHÄFTLICH-Wallets, semikolongetrennt, UTF-8 BOM)
  - Aufgelöste Adress-Namen im Kommentarfeld
- **Portfolio-Wertverlauf** — täglicher QU-Bestand × Tageskurs als Liniendiagramm auf der Statistik-Seite (Bestand auf zweiter Achse)
- **Webhook-Benachrichtigungen** — neue eingehende Zahlungen können einen Webhook auslösen (generisches JSON, Discord oder ntfy) mit Mindestbetrags-Filter, TX-/SC-Event-Typfilter (Checkboxen entscheiden, welcher Typ eine Nachricht auslöst) und Test-Schaltfläche (Einstellungen → Daten); jede Nachricht enthält den vollständigen Datensatz mit dem Event-Typ in der ersten Zeile
- **Token- & Asset-Bestände** — Live-Token-Bestände (z. B. QX-Shares) je Wallet auf der Wallet-Detailseite, aufgelöst über das Qubic-Assets-Register; je Asset mit aktuellem Kurs (letzter QX-Trade in QU, von der offiziellen QX-API) und dem daraus berechneten Wert in QU und EUR/USD
- **Token/Shares-Portfolio-Ansicht** — Umschalter „QUBIC | Token/Shares" im Wallets → Portfolio-Tab: Token-Werte nach Besitzer gruppiert, Token-Drilldown je Wallet und der Gesamtwert der Wallet inklusive QUBIC (Batch-Endpoint mit serverseitigem Cache)
- **Interne Transfers** — Wallet-zu-Wallet-Transfers werden beim Export steuerlich neutral behandelt
- **Datenschutz-Modus** — Auge-Symbol im Header blendet alle sensiblen Werte app-weit aus: Wallet-Adressen, Kontostände, Portfolio-Werte, Gewinn/Verlust, Steuerbeträge, EUR/USD-Summen sowie persönliche Datenfelder im Steuerformular
- **Dashboard-Suche & Paginierung** — Volltextsuche mit Entprellung über alle Events; einstellbare Seitengröße (10–1000), wird in localStorage gespeichert
- **Ledger-Import** — Wallet-Historie aus [myledger.qubic.tools](https://myledger.qubic.tools/) als JSON direkt in Einstellungen → Daten importieren
- **Deutsch / Englisch** Benutzeroberfläche, Dunkel- / Hellmodus
- **Einstellungen in Reitern** — `Darstellung` (Währung, Schrift, Theme, Sprache, Animationen), `Steuern` (Land/Methode, Persönliche/Geschäftsdaten), `Daten` (Export, Sicherung/Wiederherstellung, Resync, Ledger-Import); aktiver Reiter wird per URL-Abfrageparameter (`?tab=…`) gespiegelt
- **Vollständig containerisiert** — ein `docker-compose up --build` genügt
- **Footer** — Haftungsausschluss-Banner und fixer Footer mit Copyright, Links (Qubic.org, Nutzungsbedingungen, Datenschutz) und Versionsnummer

---

## Voraussetzungen

### Docker (empfohlen für den Produktivbetrieb)

- [Docker](https://docs.docker.com/engine/install/) (Windows / Mac / Linux)
- Docker Compose Plugin — bei Docker Desktop enthalten, auf Linux als `docker-compose-plugin` Paket

> **Hinweis:** Der moderne Befehl lautet `docker compose` (mit Leerzeichen). Das veraltete `docker-compose` (mit Bindestrich) ist nicht mehr aktuell und möglicherweise nicht auf deinem System verfügbar.

### Lokale Entwicklung (VSCode)

- Python 3.12+
- Node.js 22+
- VSCode mit den Erweiterungen **Python** (ms-python.python) und **Debugpy**

---

## Start mit UmbrelOS

QubicFlow ist für [UmbrelOS](https://umbrel.com/) verfügbar — das selbst gehostete Home-Server-Betriebssystem, das auf einem Raspberry Pi oder einem beliebigen Linux-Rechner läuft.

**Umbrel-Store-Repository:** https://github.com/AndyQus/qubicflow-umbrel-store

### Installation über den Community App Store (jetzt verfügbar)

1. Öffne den Umbrel App Store
2. Klicke auf **⋮** (Menü oben rechts) → **Community App Stores**
3. Store-URL eingeben: `https://github.com/AndyQus/qubicflow-umbrel-store`
4. Auf **Installieren** neben QubicFlow klicken

QubicFlow ist nach der Installation unter `http://<deine-umbrel-ip>:8080` erreichbar.

> **Offizieller App Store** — Eine Einreichung in den offiziellen Umbrel App Store ist ausstehend (PR #5461). Sobald genehmigt, kann QubicFlow direkt aus dem integrierten Store installiert werden, ohne eine Community-Quelle hinzuzufügen.

---

## Start mit Docker

```bash
cd qubic-flow
docker compose up --build   # erster Start oder nach Code-Änderungen
docker compose up -d        # danach reicht das, läuft im Hintergrund
docker compose down         # stoppen (Daten bleiben erhalten)
docker compose down -v      # stoppen + Daten vollständig löschen
```

> **Hinweis:** Bitte `docker compose` (mit Leerzeichen) verwenden — das veraltete `docker-compose` (mit Bindestrich) ist nicht mehr aktuell.

**→ Hauptseite: http://localhost:8080**

| Dienst    | URL                                    |
|-----------|----------------------------------------|
| Frontend  | http://localhost:8080                  |
| Backend   | http://localhost:8000/api/v1/health    |
| API-Doku  | http://localhost:8000/docs             |

> Die Ports sind auf `127.0.0.1` gebunden — von außen nicht erreichbar.

Das Backend führt beim Start automatisch `alembic upgrade head` aus — Datenbankmigrationen laufen ohne manuellen Eingriff.

Daten werden im Docker-Volume `qubicflow-data` gespeichert und bleiben beim Neustart erhalten.

### Linux / Raspberry Pi — Ausführliche Installationsanleitung

Eine vollständige Schritt-für-Schritt-Anleitung mit Docker-Installation, Berechtigungs-Fixes (wichtig für Raspberry Pi) und Fehlerbehebung findest du hier:

📄 **[INSTALL_Linux.de.md](INSTALL_Linux.de.md)** (Deutsch)  
📄 **[INSTALL_Linux.md](INSTALL_Linux.md)** (English)

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
Für den Live-Sync wählt QubicFlow automatisch die BOB-Node mit dem **höchsten Tick** (am weitesten fortgeschritten) und fällt auf RPC zurück, falls alle BOB-Nodes hängen. Welche Node aktuell den Live-Sync speist, zeigt das Verbindungs-Pill (oben rechts) sowie ein pulsierender Punkt in der Node-Liste.

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

- **Zeitstempel** fehlen in den rohen BOB-Transfer-Einträgen — QubicFlow löst sie beim Sync automatisch über `qubic_getTickByNumber` / `GET /tick/{tickNumber}` auf; ältere Events ohne Zeitstempel werden vom 6-stündlichen Timestamp-Backfill-Job repariert.
- Der öffentliche BOB-Node (`bobnet.qubic.li:40420`) ist ein Community-Dienst ohne garantierte Verfügbarkeit. Für den Produktivbetrieb empfiehlt sich ein eigener BOB-Node.

> Ausführliche BOB-API-Dokumentation: [`docs/bob_node.md`](docs/bob_node.md)

### Node-Ausfallsicherung

Der Sync-Job (`sync_all_wallets`, alle 60 s) wählt die **Live-Sync**-Node nach folgender Logik:

1. Nur `is_active = 1`-Nodes mit Status ONLINE oder DEGRADED werden berücksichtigt
2. Unter den BOB-Nodes gewinnt die mit dem **höchsten Tick** (am weitesten fortgeschritten); die **Priorität** entscheidet nur als Tiebreaker bei (nahezu) gleichem Tick
3. Hängt selbst die beste BOB-Node mehr als `MAX_BOB_LAG` (1000) Ticks hinter dem RPC-Netzwerk-Tick zurück, gilt sie als „stehengeblieben" und RPC übernimmt den Live-Sync (wird als Warnung geloggt)
4. Ist kein Node verfügbar, fällt das System auf `QUBIC_RPC_URL` aus `.env` zurück

> Beim Wechsel der aktiven Node gehen keine Daten verloren: Der inkrementelle Sync setzt immer beim persistierten `last_tick` an; jeder Bereich, den eine Node nicht liefern konnte, wird per RPC nachgefüllt oder als Gap aufgezeichnet und erneut versucht.

---

## Konfiguration (.env)

Datei `backend/.env` anlegen (Vorlage: `backend/.env.example`):

```env
# Umgebung: production (Standard) oder development.
# Im Development-Modus sind die Bestandsverlauf-Serien zum Testen vorab aktiviert;
# in Produktion starten sie deaktiviert und werden je Nutzer in den Einstellungen aktiviert.
APP_ENV=production

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
│   │   │   ├── wallets.py   # Wallet CRUD, Resync, Asset-Bestände
│   │   │   ├── events.py    # Event-Liste, Filter, Notizen, Spenden-Endpunkte
│   │   │   ├── nodes.py     # Node CRUD, Logs, Diagnose, Sync-Now
│   │   │   ├── stats.py     # Statistik-Panels, Epochen, Portfolio-Verlauf
│   │   │   ├── export.py    # CSV-Downloads (CoinTracking, Koinly, Blockpit, Steuerberater)
│   │   │   ├── backup.py    # Vollständiges JSON-Backup Export/Restore
│   │   │   ├── notifications.py # Webhook-Benachrichtigungen (Einstellungen + Test)
│   │   │   ├── labels.py    # Adress-Namensauflösung
│   │   │   ├── health.py    # Systemstatus + Metriken
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
│   │   │   ├── donor_cache.py       # Spenden-/Supporter-Cache
│   │   │   └── opening_position.py  # Eröffnungspositionen für Steuer
│   │   ├── services/        # Geschäftslogik
│   │   │   ├── sync_engine.py      # Tick-Sync mit Fenstertechnik (Event + TX); dynamische Node-Auswahl; Timestamp-/Epoch-/Kurs-Backfill
│   │   │   ├── qubic_client.py     # RPCClient + BOBClient (3× Wiederholung, BOB-Antwort-Mapping, Asset-Abfrage)
│   │   │   ├── coingecko.py        # Kursabruf mit Anfragelimit
│   │   │   ├── label_service.py    # Adress-Namen-Sync
│   │   │   ├── export_service.py   # CSV-Erstellung (4 Formate)
│   │   │   ├── notification_service.py # Webhook-Benachrichtigungen (JSON/Discord/ntfy)
│   │   │   ├── health_monitor.py   # Node-Statusprüfung
│   │   │   ├── snapshot_service.py # Wöchentliche Schnappschüsse
│   │   │   ├── balance_service.py  # Wallet-Kontostand-Nachführung
│   │   │   ├── donation_cache_service.py # Supporter-/Spendenerkennung
│   │   │   ├── tax_engine.py       # Steuerberechnung (FIFO/LIFO/HIFO/AVCO, länderspezifisch inkl. DK)
│   │   │   └── scheduler.py        # APScheduler-Jobs
│   │   ├── websocket/
│   │   │   └── manager.py   # WebSocket-Verbindungsverwaltung
│   │   ├── utils/
│   │   │   ├── time.py      # UTC-Hilfsfunktionen
│   │   │   └── log_buffer.py # In-Memory-Log-Ringpuffer (Logs-Reiter)
│   │   ├── config.py        # Pydantic-Einstellungen
│   │   ├── database.py      # SQLAlchemy Engine + Sitzung
│   │   └── main.py          # FastAPI App + Lebenszyklus
│   ├── tests/               # pytest-Suite (13 Dateien, 212 Tests)
│   ├── alembic/
│   │   └── versions/        # Datenbankmigrationen (001 … 013)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── views/           # Seiten (Dashboard, Wallets, Assets, Statistiken, Steuer usw.)
│   │   ├── components/      # AppHeader, AppNav, AppFooter, StatsPanel, EventsTable, WalletFilter
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
| GET     | `/metrics`                            | Basis-Laufzeitmetriken                                |
| GET     | `/wallets`                            | Alle aktiven Wallets                                  |
| POST    | `/wallets`                            | Wallet anlegen                                        |
| PUT     | `/wallets/{id}`                       | Wallet bearbeiten                                     |
| DELETE  | `/wallets/{id}`                       | Wallet als gelöscht markieren                         |
| GET     | `/wallets/{id}/assets`                | Live-Token-/Asset-Bestände inkl. QX-Kursen (RPC-Proxy) |
| GET     | `/wallets/assets-summary`             | Token-Bestände + Werte aller Wallets (Batch, gecacht) |
| POST    | `/wallets/{id}/resync-tx`             | TX-Sync für ein Wallet neu starten                    |
| POST    | `/wallets/resync-all`                 | Alle Wallets neu synchronisieren (nur fehlende)       |
| GET     | `/events`                             | Events (Filter: Wallet, Epoche, Monat, Jahr, source_type; seitenweise) |
| GET     | `/events/count`                       | Anzahl Events für den aktuellen Filter                |
| GET     | `/events/filter-options`              | Verfügbare Jahre/Monate/Epochen für Filter            |
| PATCH   | `/events/{id}/note`                   | Notiz an einem Event speichern                        |
| GET     | `/labels`                             | Adress-Labels (optional `?address=`)                  |
| GET     | `/nodes`                              | Nodes auflisten                                       |
| POST    | `/nodes`                              | Node anlegen                                          |
| PUT     | `/nodes/{id}`                         | Node bearbeiten                                       |
| DELETE  | `/nodes/{id}`                         | Node löschen                                          |
| PATCH   | `/nodes/{id}/toggle`                  | Node aktivieren/deaktivieren                          |
| POST    | `/nodes/{id}/check-now`               | Sofortiger Health-Check                               |
| POST    | `/nodes/sync-now`                     | Sofortigen Voll-Sync auslösen                         |
| POST    | `/nodes/diagnose`                     | Verbindungs- + Sync-Diagnose                          |
| GET     | `/nodes/logs`                         | In-Memory-Log-Puffer (Logs-Reiter)                    |
| GET     | `/stats/current`                      | Statistik-Panels (Aktuell + Vorperiode)               |
| GET     | `/stats/history`                      | Wöchentliche/monatliche Zeitreihe                     |
| GET     | `/stats/snapshots`                    | Gespeicherte Wochenschnappschüsse                     |
| GET     | `/stats/epochs`                       | Alle Epochen-Aufschlüsselungen je Wallet (Ein-/Ausgang, TX/Event-Aufteilung, Dividenden als EVENTs) |
| GET     | `/stats/portfolio-history`            | Täglicher Portfolio-Wert (Bestand × Kurs)             |
| GET     | `/export/cointracking`                | CoinTracking-CSV (`?year=2026`)                       |
| GET     | `/export/koinly`                      | Koinly-Universal-CSV (`?year=2026`)                   |
| GET     | `/export/blockpit`                    | Blockpit-Import-CSV (`?year=2026`)                    |
| GET     | `/export/steuerberater`               | Steuerberater-CSV (`?year=2026`)                      |
| GET     | `/backup`                             | Vollständiges JSON-Backup (Wallets, Nodes, Events, Steuereinstellungen) |
| POST    | `/backup/restore`                     | Backup wiederherstellen (dedupliziert)                |
| GET     | `/notifications/settings`             | Webhook-Einstellungen lesen                           |
| PUT     | `/notifications/settings`             | Webhook-Einstellungen speichern                       |
| POST    | `/notifications/test`                 | Test-Benachrichtigung senden                          |
| GET     | `/tax/settings`                       | Steuereinstellungen lesen                             |
| PUT     | `/tax/settings`                       | Steuereinstellungen speichern                         |
| GET     | `/tax/countries`                      | Verfügbare Länder + Steuerregeln                      |
| GET     | `/tax/opening-positions`              | Eröffnungspositionen auflisten                        |
| POST    | `/tax/opening-positions`              | Eröffnungsposition anlegen                            |
| DELETE  | `/tax/opening-positions/{id}`         | Eröffnungsposition löschen                            |
| GET     | `/tax/report`                         | Steuerbericht berechnen                               |
| GET     | `/tax/price`                          | EUR/USD-Kurs für ein Datum (`?date=`)                 |
| GET     | `/balance-history/settings`           | Bestandsverlauf-Einstellungen (Serien-Schalter, Aufbewahrung, Auto-Export) |
| PUT     | `/balance-history/settings`           | Bestandsverlauf-Einstellungen speichern               |
| GET     | `/balance-history/overview`           | Erfassungszeilen einer Serie (`?kind=hourly\|daily\|weekly`) |
| POST    | `/balance-history/capture`            | Jetzt erfassen (manueller Auslöser, gleiche Funktion wie der Scheduler) |
| PATCH   | `/balance-history/snapshots/{id}`     | Erfassten Wert ändern (Original bleibt als Nachweis erhalten) |
| PATCH   | `/balance-history/annotations`        | why/Informationen/Anmerkungen einer Zeile speichern   |
| POST    | `/balance-history/rows`               | Manuellen Datensatz anlegen                           |
| DELETE  | `/balance-history/rows`               | Manuellen Datensatz löschen (`?kind=&bucket=`)        |
| GET     | `/balance-history/owner-ledger`       | Event-Ledger je Besitzer (`?owner=`)                  |
| GET     | `/balance-history/transfers`          | Interne Transfers zwischen eigenen Wallets ab Serien-Baseline (`?kind=`) |
| GET     | `/balance-history/transactions`       | Flache Transaktionsliste (paginiert)                  |
| GET     | `/balance-history/export/{kind}`      | Excel-Datei einer Serie herunterladen (`?lang=de\|en`) |
| POST    | `/balance-history/export/rebuild`     | Alle aktivierten Excel-Dateien im Datenordner neu erzeugen |
| DELETE  | `/balance-history/series/{kind}`      | Eine Serie komplett zurücksetzen (löscht alle ihre Erfassungen, erzeugt ihre Excel-Datei leer neu) |
| WS      | `/ws`                                 | WebSocket (event.new, node.health, sync.node)         |

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
- Download: `GET /api/v1/export/cointracking?year=2026`

### Koinly (PRIVAT-Wallets)

- Koinly-Universal-CSV-Format (Datum, Sent/Received Amount + Currency, Net Worth, Label, TxHash)
- Reward-Einkommen wird als `reward` gekennzeichnet; interne Transfers ausgeschlossen
- Download: `GET /api/v1/export/koinly?year=2026`

### Blockpit (PRIVAT-Wallets)

- Blockpit-Import-Format (Date (UTC), Integration Name, Label, Outgoing/Incoming Asset + Amount, Trx. ID)
- Eingehende Rewards werden als `Staking` gekennzeichnet, Transfers als `Deposit`/`Withdrawal`; interne Transfers ausgeschlossen
- Download: `GET /api/v1/export/blockpit?year=2026`

### Steuerberater (GESCHÄFTLICH-Wallets)

- Format: semikolongetrennt, UTF-8 BOM
- Enthält: alle Transfers inkl. interne (mit Typkennzeichnung)
- Kommentarfeld enthält aufgelöste Adress-Namen: `„Quellname → Zielname"`
- Download: `GET /api/v1/export/steuerberater?year=2026`

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

- **Deutschland (DE):** Gewinne aus Verkäufen nach mehr als 12 Monaten Haltedauer sind steuerfrei; 1.000 € Freigrenze
- **Dänemark (DK):** FIFO ist verpflichtend (die Methodenauswahl ist gesperrt); Gewinne und Verluste werden **nicht verrechnet** — steuerpflichtige Gewinne und abzugsfähige Verluste werden getrennt ausgewiesen (Spekulationsbeskatning)
- **Berichtswährung:** Kurse werden nur in EUR und USD erfasst. Die USA werden in USD berechnet, alles andere in EUR — Länder mit anderer Lokalwährung (CHF, GBP, DKK, …) werden ehrlich als EUR ausgewiesen. Einkommens-Events werden mit Marktwert-Kostenbasis eingebucht und daher nicht doppelt besteuert.

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

| Job                       | Intervall            | Beschreibung                                                              |
|---------------------------|----------------------|---------------------------------------------------------------------------|
| `sync_all_wallets`        | alle 60 Sekunden     | Event-Sync + TX-Sync + Kontostand-Aktualisierung; wählt dynamisch den besten verfügbaren Node |
| `health_monitor`          | alle 30 Sekunden     | Node-Status prüfen (`/v1/tick-info` für RPC, `/status` für BOB), WebSocket-Broadcast |
| `retry_sync_gaps`         | alle 15 Minuten      | Ungelöste Sync-Lücken (EVENT + TX) per RPC erneut versuchen               |
| `check_balances`          | stündlich            | Live-RPC-Kontostand mit berechnetem Bestand vergleichen; bei Abweichung gezielten Resync auslösen |
| `backfill_tx_epochs`      | stündlich            | Fehlende Epochen-Nummern an TX-Datensätzen ergänzen                       |
| `refresh_donation_cache`  | stündlich            | Supporter-/Spenden-Cache aktualisieren                                    |
| `backfill_rates`          | alle 6 Stunden       | EUR/USD-Kurse für Events ohne Kurs nachladen                              |
| `backfill_timestamps`     | alle 6 Stunden       | Events ohne verwertbaren Zeitstempel (alte BOB-Importe) über Tick-Daten reparieren |
| `sync_labels`             | alle 24 Stunden      | Adress-Namensauflösung (address_labels, tokens, issuances)               |
| `weekly_snapshot`         | Mi 12:00 UTC (Cron)  | Wöchentlichen Aggregations-Schnappschuss speichern                        |

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

| Datei                             | Tests | Beschreibung                                                         |
|-----------------------------------|-------|----------------------------------------------------------------------|
| `tests/test_tax_engine.py`        | 27    | Lot-Abgleich (FIFO/LIFO/HIFO/AVCO), Haltedauer, Steuerregeln, Datumsparser |
| `tests/test_tax_report_fixes.py`  | 8     | Einkommens-Kostenbasis, Jahresend-Bestände, Berichtswährung, dänisches Modell |
| `tests/test_export_service.py`    | 25    | CSV-Exporte (Klassifikation, Formate, interne Transfers)             |
| `tests/test_review_fixes.py`      | 46    | API-Regressionen (Nodes, Sync-Guard, Diagnose)                       |
| `tests/test_bob_client.py`        | 25    | BOB-JSON-RPC-Client, Antwort-Mapping, Timestamp-Auflösung            |
| `tests/test_wallets_api.py`       | 23    | Wallet-CRUD + Resync-Endpunkte                                       |
| `tests/test_time_utils.py`        | 15    | UTC-Hilfsfunktionen                                                  |
| `tests/test_donation_utils.py`    | 13    | Supporter-Rang- / Spendenlogik                                       |
| `tests/test_bob_selection.py`     | 8     | Tick-basierte BOB-Node-Wahl + Lag-Fallback                           |
| `tests/test_sync_engine_logic.py` | 8     | Sync-Fenster- / Persistenzlogik                                      |
| `tests/test_sync_gap_type.py`     | 7     | Lücken-Erfassung (EVENT vs. TX)                                      |
| `tests/test_coingecko.py`         | 6     | Kurs-Zwischenspeicher Treffer/Fehltreffer, Netzwerkfehler, Seiteneffektfreiheit |

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
- Die Datei `VERSION` enthält die **zuletzt veröffentlichte** Version — die Pipeline erhöht die Patch-Nummer selbst vor dem Taggen. **`VERSION` niemals manuell anheben**, sonst wird eine Versionsnummer übersprungen (Doppel-Bump).

### GitHub Actions Workflow (`.github/workflows/docker-publish.yml`)

Der Workflow besteht aus 4 aufeinanderfolgenden Jobs:

| Job | Beschreibung |
|-----|--------------|
| `tag` | Erhöht die Patch-Version in `VERSION`, committet sie und erstellt den Git-Tag `v{VERSION}` (übersprungen, falls vorhanden) |
| `build-backend` | Multi-Arch Docker Image für das Backend → Docker Hub |
| `build-frontend` | Vue-Build + nginx Docker Image → Docker Hub |
| `update-umbrel-store` | Aktualisiert automatisch die Versionsnummern im Store-Repo |
| `sync-develop` | Pusht den Versions-Bump-Commit zurück nach `develop` |

Der `workflow_dispatch`-Trigger erlaubt manuelle Neustarts über die GitHub-Actions-Oberfläche, falls ein Build fehlschlägt.

### Erforderliche GitHub Secrets

Im `qubic-flow` Repository unter Settings → Secrets and variables → Actions:

| Secret | Wert |
|--------|------|
| `DOCKERHUB_USERNAME` | Docker Hub Benutzername |
| `DOCKERHUB_TOKEN` | Docker Hub Personal Access Token |
| `STORE_REPO_TOKEN` | GitHub Fine-grained PAT für `qubicflow-umbrel-store` (Contents: Read+Write) |

### Release auslösen

```bash
# 1. Eintrag in CHANGELOG.md ergänzen (VERSION NICHT anfassen — die Pipeline erhöht sie selbst)
git add CHANGELOG.md
git commit -m "docs: changelog for next release"
git push origin develop

# 2. Merge nach main → löst die Pipeline automatisch aus
git checkout main
git merge develop
git push origin main

# 3. Danach develop pullen — CI pusht den Versions-Bump-Commit zurück
git checkout develop && git pull
```

### Umbrel Installation

#### Community App Store (sofort verfügbar)

1. Umbrel öffnen → **App Store**
2. Oben rechts auf **⋮** klicken → **Community App Stores**
3. Folgenden Link einfügen und bestätigen:
   ```
   https://github.com/AndyQus/qubicflow-umbrel-store
   ```
4. QubicFlow erscheint im App Store → **Installieren**

#### Offizieller Umbrel App Store (Einreichung läuft)

QubicFlow wurde beim offiziellen Umbrel App Store eingereicht und wird derzeit vom Umbrel-Team geprüft.

> **PR:** https://github.com/getumbrel/umbrel-apps/pull/5461

Sobald die Einreichung akzeptiert wurde, ist QubicFlow direkt im eingebauten Umbrel App Store verfügbar — ohne zusätzliche Community-Store-URL. Bis dahin bitte den Community-Store-Link oben verwenden.

---

## Lizenz

MIT License — siehe [LICENSE](LICENSE)

QubicFlow ist freie Open-Source-Software. Der Quellcode ist öffentlich auf GitHub verfügbar:  
**https://github.com/AndyQus/qubic-flow**
