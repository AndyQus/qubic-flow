# QubicFlow — Discord Post (Deutsch)

**QubicFlow — Selbst gehosteter Qubic Wallet Tracker**

Hey zusammen! Ich hab in den letzten Wochen an einem Tool gearbeitet, das ich gerne der Community vorstellen möchte — und es ist **Open Source** 🎉

**Was ist QubicFlow?**
Ein selbst gehosteter Wallet Tracker speziell für Qubic — eure Daten bleiben auf eurem Rechner/Server, nichts landet bei Dritten.

**Features:**
- Beliebig viele Wallets tracken (privat & geschäftlich)
- Automatische Synchronisierung alle 60 Sekunden via RPC oder BOB Node
- Live-Updates per WebSocket direkt in der Oberfläche
- EUR/USD-Kurse täglich von CoinGecko
- Deutsch & Englisch, Dark/Light Mode

**Steuer-Tools:**
- FIFO / LIFO / HIFO / AVCO-Berechnung
- Länderspezifische Regeln (DE, AT, CH …) inkl. Jahresfrist-Steuerfreiheit
- CSV-Export für CoinTracking & Steuerberater
- PDF-Steuerbericht auf Knopfdruck

**Quellcode (MIT Lizenz):**
https://github.com/AndyQus/qubic-flow

**Start mit einem Befehl:**
```
docker compose up --build
```

**Installation auf Umbrel OS:**
1. Umbrel öffnen → App Store
2. Oben rechts auf **⋮** klicken → **Community App Stores**
3. Folgenden Link einfügen und bestätigen:
   `https://github.com/AndyQus/qubicflow-umbrel-store`
4. QubicFlow erscheint im App Store → **Installieren**

---

**Unterstützung / Spenden**
QubicFlow ist kostenlos nutzbar. Wer das Projekt unterstützen möchte, kann QU an folgende Adresse senden:
`CCCJKFMDTUFFWDCRBFNHMQRYOBABEKBDUZWEJMARUETQPTFZWBCJLYUGREXI`

QubicFlow erkennt Spenden aus euren eigenen Wallets automatisch direkt on-chain. Kein Abo, keine Cloud, kein Konto — nur eine On-Chain-Zahlung direkt aus eurer eigenen Wallet.

**Spenden-Stufen:**
- **1.000.000 QU** = 1 Monat Dankeschön-Hinweis in der App
- **12.000.000 QU** = 1 Jahr
- **ab 100.000.000 QU** = für immer

Wer dauerhaft als Unterstützer angezeigt werden möchte, kann mich einfach hier auf Discord anschreiben (@AndyQus ױ) — ich trage euch manuell in die Lifetime-Liste ein.

---

**Weitere Tools von mir**
Falls ihr noch andere Qubic-Tools braucht — ich hab da noch ein paar Sachen gebaut:

- [MyLedger](https://myledger.qubic.tools) — Qubic Ledger Tool
- [Dividends](https://dividends.qubic.tools) — Dividend Tracker
- [Auctions](https://auctions.qubic.tools) — Qubic Auction Monitor
- [Doge-Mining-Stats](https://doge.qubic.tools) — Doge Mining Stats
- [Explorer](https://live.qubic.org/explorer) — Qubic Live Explorer
- [Live](https://live.qubic.org) — Qubic Live Network
- [QPI Language Support](https://marketplace.visualstudio.com/items?itemName=AndyQus.qubic-org-qpi) — VSCode Extension für QPI
