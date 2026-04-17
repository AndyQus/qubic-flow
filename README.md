# QubicFlow

Universeller Qubic Wallet Tracker für steuerliche Dokumentation.

## Start

```bash
docker-compose up
```

→ Backend: http://localhost:8000/api/v1/health  
→ Frontend: http://localhost:8080

## Development

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
