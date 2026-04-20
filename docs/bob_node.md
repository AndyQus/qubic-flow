# BOB-Node Integration

QubicFlow unterstützt neben dem Standard-Qubic-RPC auch den **BOB-Node** des Core-Teams (`github.com/qubic/core-bob`).  
BOB-Nodes bieten eine eigene REST-API auf Port **40420** sowie WebSocket-Subscriptions.

---

## Einrichtung in QubicFlow

Einstellungen → Nodes → Node hinzufügen:

```
URL:       https://bobnet.qubic.li:40420
Typ:       BOB_NODE
Label:     BOB Public Node
Priorität: 1
```

QubicFlow erkennt `node_type = BOB_NODE` und wählt automatisch die richtigen API-Endpunkte.

---

## BOB REST-API (Port 40420)

Vollständige OpenAPI-Spezifikation: `RESTAPI/openapi.json` im GitHub-Repository.  
Interaktiver Playground: `rpc_playground.html` im Repository.

### Verwendete Endpunkte (QubicFlow)

| Endpunkt                         | Methode | Verwendung in QubicFlow         |
|----------------------------------|---------|----------------------------------|
| `GET /status`                    | GET     | Health-Check, aktueller Tick     |
| `POST /getQuTransferForIdentity` | POST    | QU-Transfer-Sync je Wallet       |

### Alle verfügbaren Endpunkte

#### GET-Endpunkte

| Pfad                                             | Beschreibung                          |
|--------------------------------------------------|---------------------------------------|
| `GET /status`                                    | Node-Status: currentTick, currentEpoch, verifiedTick |
| `GET /balance/{identity}`                        | Kontostand + Transfer-Zähler          |
| `GET /asset/{identity}/{issuer}/{assetName}/{manageSCIndex}` | Asset-Info           |
| `GET /epochinfo/{epoch}`                         | Epoch-Informationen                   |
| `GET /tx/{txHash}`                               | Transaktion per Hash (60 Kleinbuchstaben) |
| `GET /tick/{tickNumber}`                         | Tick-Daten                            |
| `GET /log/{epoch}/{fromId}/{toId}`               | Logs per ID-Bereich                   |

#### POST-Endpunkte

| Pfad                             | Pflichtfelder                                      | Beschreibung               |
|----------------------------------|----------------------------------------------------|----------------------------|
| `POST /findLog`                  | fromTick, toTick, scIndex, logType, topic1–3       | Logs nach Filter suchen    |
| `POST /getlogcustom`             | epoch, scIndex, logType                            | Logs nach Epoch + Typ      |
| `POST /getQuTransferForIdentity` | fromTick, toTick, identity                         | QU-Transfers je Adresse    |
| `POST /getAssetTransferForIdentity` | fromTick, toTick, identity, assetIssuer, assetName | Asset-Transfers je Adresse |
| `POST /getAllAssetTransfer`      | fromTick, toTick, assetIssuer, assetName           | Alle Transfers eines Assets |
| `POST /querySmartContract`       | nonce, scIndex, funcNumber, data                   | Smart Contract abfragen    |
| `POST /broadcastTransaction`     | data (hex-encoded signed tx)                       | Transaktion senden         |

#### WebSocket

```
ws://host:40420/ws/qubic
```

Unterstützte Subscriptions (`qubic_subscribe`):

| Subscription | Beschreibung                                     |
|--------------|--------------------------------------------------|
| `newTicks`   | Live-Benachrichtigung bei neuem Tick             |
| `transfers`  | QU-Transfer-Events mit optionalem Catch-Up       |
| `logs`       | Alle Log-Events mit optionalem Catch-Up          |
| `tickStream` | Vollständige Tick-Daten mit Transaktionen + Logs |

---

## JSON-RPC 2.0 (Alternative zu REST)

Neben der REST-API bietet BOB auch eine JSON-RPC-2.0-Schnittstelle:

```
POST http://host:40420/qubic
```

Beispiel:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "qubic_getBalance",
  "params": ["IDENTITY60CHARS..."]
}
```

Vollständige Methodenreferenz: `docs/QUBIC_JSON_RPC.md` im GitHub-Repository.

---

## Response-Formate

### GET /status

```json
{
  "currentTick": 49854441,
  "currentEpoch": 209,
  "verifiedTick": 49854440,
  "bmConnections": 3
}
```

### POST /getQuTransferForIdentity

Request:
```json
{
  "fromTick": 49850000,
  "toTick": 49854441,
  "identity": "IDENTITY60CHARS..."
}
```

Response:
```json
{
  "transfers": [
    {
      "logId": 12345678,
      "tick": 49852100,
      "epoch": 209,
      "type": 0,
      "scIndex": 0,
      "logType": 0,
      "message": {
        "sourceId": "SENDER60CHARS...",
        "destId": "RECIPIENT60CHARS...",
        "amount": 100000000
      }
    }
  ]
}
```

> Das `message`-Feld ist unstrukturiert und abhängig von `logType`.  
> Für `logType = 0` (QU_TRANSFER) enthält es `sourceId`, `destId` und `amount`.

---

## Log-Typen

| Wert | Name                                           |
|------|------------------------------------------------|
| 0    | QU_TRANSFER                                    |
| 1    | ASSET_ISSUANCE                                 |
| 2    | ASSET_OWNERSHIP_CHANGE                         |
| 3    | ASSET_POSSESSION_CHANGE                        |
| 4    | CONTRACT_ERROR_MESSAGE                         |
| 5    | CONTRACT_WARNING_MESSAGE                       |
| 6    | CONTRACT_INFORMATION_MESSAGE                   |
| 7    | CONTRACT_DEBUG_MESSAGE                         |
| 8    | BURNING                                        |
| 9    | DUST_BURNING                                   |
| 10   | SPECTRUM_STATS                                 |
| 255  | CUSTOM_MESSAGE                                 |

---

## Bekannte Einschränkungen

### ⚠ Timestamps fehlen in Transfer-Logs (offene Aufgabe)

**Problem:** `POST /getQuTransferForIdentity` liefert kein `timestamp`-Feld in den Log-Einträgen.  
QubicFlow speichert BOB-Events deshalb mit Timestamp `"0"` → Anzeige als `01.01.1970`.

**Geplante Lösung:** Nach dem Sync für jeden einzigartigen Tick-Wert einen `GET /tick/{tickNumber}`-Aufruf durchführen und den Timestamp aus der Tick-Antwort nachträglich einsetzen. Alternativ: Batched-Lookup über `POST /getTickLogRanges`.

**Betroffene Dateien:**
- `backend/app/services/qubic_client.py` — `BOBClient.get_event_logs()` / `_map_bob_transfer()`
- `backend/app/services/sync_engine.py` — `_persist_logs()`

**Workaround bis zur Lösung:** Der Hintergrund-Job `backfill_missing_rates` (alle 6 h) füllt fehlende EUR/USD-Kurse nach — Beträge sind also korrekt. Nur das angezeigte Datum ist falsch.

---

## Weiterführende Links

- GitHub-Repository: https://github.com/qubic/core-bob
- JSON-RPC-Dokumentation: `docs/QUBIC_JSON_RPC.md` im Repository
- REST-API-Dokumentation: `docs/REST_API.md` im Repository
- OpenAPI-Spezifikation: `RESTAPI/openapi.json` im Repository
- Interaktiver Playground: `rpc_playground.html` im Repository
