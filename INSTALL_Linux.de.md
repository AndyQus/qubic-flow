# QubicFlow – Linux Installationsanleitung

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/open%20source-%E2%9D%A4-brightgreen.svg)](https://github.com/AndyQus/qubic-flow)

---

## Inhaltsverzeichnis

- [Voraussetzungen: Docker installieren](#voraussetzungen-docker-installieren)
- [Schritt 1 – Repository klonen](#schritt-1--repository-klonen)
- [Schritt 2 – Volume-Berechtigungen vorbereiten](#schritt-2--volume-berechtigungen-vorbereiten-)
- [Schritt 3 – Starten](#schritt-3--starten)
- [Schritt 4 – Zugriff](#schritt-4--zugriff)
- [App verwalten](#app-verwalten)
- [Häufige Fehler & Lösungen](#häufige-fehler--lösungen)

---

## Voraussetzungen: Docker installieren

Falls Docker noch nicht auf deinem System installiert ist:

```bash
# Alte Versionen entfernen (falls vorhanden)
sudo apt-get remove docker docker-engine docker.io containerd runc

# Abhängigkeiten installieren
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Offiziellen Docker GPG-Key hinzufügen
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Docker-Repository hinzufügen
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Docker installieren
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

> **Debian / Raspberry Pi OS:** In der Repository-Zeile `ubuntu` durch `debian` ersetzen.

### Docker ohne sudo verwenden (empfohlen)

```bash
sudo usermod -aG docker $USER
newgrp docker   # Gruppe sofort aktivieren (oder neu einloggen)
```

---

## Schritt 1 – Repository klonen

```bash
git clone https://github.com/AndyQus/qubic-flow.git
cd qubic-flow
```

---

## Schritt 2 – Volume-Berechtigungen vorbereiten ⚠️

Der Backend-Container läuft mit User-ID `1000`. Auf dem Raspberry Pi und vielen anderen Systemen kann die eigene UID abweichen — das führt beim ersten Start zu einem **Permission denied: 'app/data'** Fehler.

Diese Befehle vor dem ersten Start ausführen:

```bash
# Eigene UID prüfen
id -u

# docker-compose.yml automatisch mit der eigenen UID/GID patchen
sed -i "s/\"1000:1000\"/\"$(id -u):$(id -g)\"/" docker-compose.yml

# Lokalen Datenordner anlegen und Volume darauf umleiten (zuverlässiger auf dem Pi)
mkdir -p ~/qubic-flow/data
chmod 755 ~/qubic-flow/data
sed -i "s|qubicflow-data:/app/data|./data:/app/data|" docker-compose.yml
```

---

## Schritt 3 – Starten

```bash
# Erster Start — baut die Docker-Images (dauert 2–5 Minuten):
docker compose up --build

# Bei allen folgenden Starts im Hintergrund starten:
docker compose up -d
```

Die Datenbank wird beim ersten Start automatisch über `alembic upgrade head` initialisiert — kein manueller Eingriff nötig.

---

## Schritt 4 – Zugriff

| Dienst | URL |
|---|---|
| **App (Frontend)** | http://localhost:8080 |
| Backend API | http://localhost:8000/api/v1/health |
| API-Dokumentation | http://localhost:8000/docs |

> Die Ports sind auf `127.0.0.1` gebunden — standardmäßig nur lokal erreichbar, nicht aus dem Netzwerk.

---

## App verwalten

```bash
docker compose down          # Stoppen (Daten bleiben erhalten)
docker compose down -v       # Stoppen und alle Daten löschen
docker compose logs -f       # Live-Logs anzeigen
docker compose restart       # Neustart ohne Rebuild
```

---

## Häufige Fehler & Lösungen

### „Got permission denied" beim Ausführen von Docker

```bash
sudo usermod -aG docker $USER && newgrp docker
```

### „docker-compose: command not found"

Das moderne Docker-Plugin verwendet ein Leerzeichen statt eines Bindestrichs:

```bash
docker compose up --build   # ✅ richtig (modernes Plugin)
docker-compose up --build   # funktioniert nur mit dem veralteten Paket
```

### Port 8080 bereits belegt

```bash
# Prüfen, was den Port belegt
sudo lsof -i :8080
```

Dann in `docker-compose.yml` die Zeile `"127.0.0.1:8080:80"` auf einen anderen Port ändern, z.B. `"127.0.0.1:9090:80"`.

### Backend startet nicht: „Permission denied: app/data" (Raspberry Pi)

Das ist das häufigste Problem auf dem Raspberry Pi. Vollständige Lösung:

```bash
cd ~/qubic-flow
sed -i "s/\"1000:1000\"/\"$(id -u):$(id -g)\"/" docker-compose.yml
mkdir -p ~/qubic-flow/data && chmod 755 ~/qubic-flow/data
sed -i "s|qubicflow-data:/app/data|./data:/app/data|" docker-compose.yml
docker compose down -v
docker compose up --build
```

---

*Weitere Informationen unter [github.com/AndyQus/qubic-flow](https://github.com/AndyQus/qubic-flow)*
