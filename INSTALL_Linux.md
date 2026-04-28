# QubicFlow – Linux Installation Guide

[![MIT License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Open Source](https://img.shields.io/badge/open%20source-%E2%9D%A4-brightgreen.svg)](https://github.com/AndyQus/qubic-flow)

---

## Table of Contents

- [Prerequisites: Install Docker](#prerequisites-install-docker)
- [Step 1 – Clone the Repository](#step-1--clone-the-repository)
- [Step 2 – Fix Volume Permissions](#step-2--fix-volume-permissions-)
- [Step 3 – Start](#step-3--start)
- [Step 4 – Access](#step-4--access)
- [Managing the App](#managing-the-app)
- [Common Errors & Fixes](#common-errors--fixes)

---

## Prerequisites: Install Docker

If Docker is not yet installed on your system:

```bash
# Remove old versions (if any)
sudo apt-get remove docker docker-engine docker.io containerd runc

# Install dependencies
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add official Docker GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

> **Debian / Raspberry Pi OS:** Replace `ubuntu` with `debian` in the repository line above.

### Allow Docker without sudo (recommended)

```bash
sudo usermod -aG docker $USER
newgrp docker   # activate group immediately (or log out and back in)
```

---

## Step 1 – Clone the Repository

```bash
git clone https://github.com/AndyQus/qubic-flow.git
cd qubic-flow
```

---

## Step 2 – Fix Volume Permissions ⚠️

The backend container runs as User ID `1000`. On Raspberry Pi and many systems your UID may differ, which causes a **Permission denied: 'app/data'** error on first start.

Run these commands to fix it before starting:

```bash
# Check your current UID
id -u

# Automatically patch docker-compose.yml with your actual UID/GID
sed -i "s/\"1000:1000\"/\"$(id -u):$(id -g)\"/" docker-compose.yml

# Create a local data folder and point the volume to it (more reliable on Pi)
mkdir -p ~/qubic-flow/data
chmod 755 ~/qubic-flow/data
sed -i "s|qubicflow-data:/app/data|./data:/app/data|" docker-compose.yml
```

---

## Step 3 – Start

```bash
# First start — builds the Docker images (takes 2–5 minutes):
docker compose up --build

# On subsequent starts, run in the background:
docker compose up -d
```

The database is initialized automatically on first start via `alembic upgrade head` — no manual steps required.

---

## Step 4 – Access

| Service | URL |
|---|---|
| **App (Frontend)** | http://localhost:8080 |
| Backend API | http://localhost:8000/api/v1/health |
| API Documentation | http://localhost:8000/docs |

> Ports are bound to `127.0.0.1` — only accessible locally by default, not from the network.

---

## Managing the App

```bash
docker compose down          # Stop (data is preserved)
docker compose down -v       # Stop and delete all data
docker compose logs -f       # Show live logs
docker compose restart       # Restart without rebuild
```

---

## Common Errors & Fixes

### "Got permission denied" when running Docker

```bash
sudo usermod -aG docker $USER && newgrp docker
```

### "docker-compose: command not found"

The modern Docker plugin uses a space, not a hyphen:

```bash
docker compose up --build   # ✅ correct (modern plugin)
docker-compose up --build   # only works if the legacy package is installed
```

### Port 8080 already in use

```bash
# Find out what is using the port
sudo lsof -i :8080
```

Then edit `docker-compose.yml` and change `"127.0.0.1:8080:80"` to another port, e.g. `"127.0.0.1:9090:80"`.

### Backend crashes with "Permission denied: app/data" (Raspberry Pi)

This is the most common issue on Raspberry Pi. Run the full fix:

```bash
cd ~/qubic-flow
sed -i "s/\"1000:1000\"/\"$(id -u):$(id -g)\"/" docker-compose.yml
mkdir -p ~/qubic-flow/data && chmod 755 ~/qubic-flow/data
sed -i "s|qubicflow-data:/app/data|./data:/app/data|" docker-compose.yml
docker compose down -v
docker compose up --build
```

---

*For more information visit [github.com/AndyQus/qubic-flow](https://github.com/AndyQus/qubic-flow)*
