# EcoTwin — Smart Lab Waste Bin (App + Dashboard)

A runnable prototype based on the EcoTwin Stage 2 design specification.

## Included
- Responsive web dashboard with bin status, deposits, alerts, storage-age monitoring, and dispatch reconciliation.
- FastAPI backend with SQLite persistence for local testing.
- Demo deposit endpoint to simulate a load-cell event.
- CSV export for deposit records.
- Seeded demo data so the dashboard is populated on first run.

## Important prototype boundary
This is software-only demo mode. It does **not** connect to an ESP32-S3, HX711 load cell, lid switch, MQTT broker, e-paper display, or production PostgreSQL database yet. Deposit events are simulated through the dashboard/API. Do not use the demo data for actual hazardous-waste compliance or safety decisions.

## Requirements
- Python 3.10+
- Node.js 18+

## 1. Start the backend
Open a terminal in this folder:

```bash
cd backend
python -m venv .venv
```

Windows:
```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:
```bash
source .venv/bin/activate
```

Then:
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API: http://127.0.0.1:8000  
API docs: http://127.0.0.1:8000/docs  
Health check: http://127.0.0.1:8000/health

## 2. Start the frontend
Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open the local URL printed by Vite (normally http://localhost:5173).

## Features to test
1. Click **Simulate deposit** to create a demo deposit event.
2. Filter the deposit table by bin or status.
3. Use **Export CSV** to download deposit records.
4. Add a dispatch weight from the Dispatch reconciliation panel.
5. Review storage-age alerts for bins approaching 75/85/90 days.
6. Open API docs to try endpoints directly.

## GitHub
Create an empty repository on GitHub, then from this folder:

```bash
git init
git add .
git commit -m "Build EcoTwin dashboard prototype"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```

Replace the remote URL with your own repository URL. Never commit API keys, passwords, or private credentials.

## API overview
- `GET /health`
- `GET /api/summary`
- `GET /api/bins`
- `GET /api/deposits`
- `POST /api/deposits/simulate`
- `GET /api/alerts`
- `GET /api/dispatches`
- `POST /api/dispatches`
- `GET /api/deposits/export.csv`

## Next integration steps
1. Replace simulated events with MQTT/TLS messages from the ESP32-S3 firmware.
2. Add per-device credentials and authentication.
3. Migrate local SQLite to PostgreSQL for multi-user deployments.
4. Implement role-based access, audit logs, backup, and deployment hardening.
5. Validate weight calibration and alert logic against real bench tests.
