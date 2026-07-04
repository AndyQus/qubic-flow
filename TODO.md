# QubicFlow — Roadmap & Community Requests

This file tracks open feature requests and planned improvements.
Have an idea? Open an [issue](https://github.com/AndyQus/qubic-flow/issues) or leave a comment!

---

## 🗺️ Planned Features

| # | Feature | Requested by | Status |
|---|---------|-------------|--------|
| 1 | 💾 Automatic backups | AndyQus | 🔜 Planned |

---

## 💾 Automatic Backups

**Idea:**
Scheduled backups instead of manual export only — a tax app should never lose data.

**Details:**
- Scheduler job (e.g. weekly) that writes a JSON/SQLite backup automatically
- Rotation (e.g. keep the last 4 backups)
- **Open question:** storage location — inside the Docker volume, a user-configurable path, or an external target (SMB/S3/…)?

---

## ✅ Completed

- 🇩🇰 **Danish FIFO tax model** — shipped in v0.2.10 (mandatory FIFO, separate gain/loss reporting)

See [CHANGELOG.md](CHANGELOG.md) for all released features.
