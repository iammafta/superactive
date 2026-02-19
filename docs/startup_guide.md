# Superactive — Startup Guide

To run the full Superactive platform, you need to run these **3 separate terminal commands** in parallel.

## 1. Backend Server (The Brain)
Run this in the root `Superactive` directory. This handles calls, AI logic, and campaigns.
```bash
# Terminal 1
cd ~/Documents/Superactive
source venv/bin/activate
python3 server.py
```

## 2. Ngrok Tunnel (The Connection)
Exposes your local server to Twilio.
```bash
# Terminal 2
cd ~/Documents/Superactive
ngrok http 8765
```
**Note**: Ensure your Twilio webhook is configured to point to the URL ngrok generates (e.g. `https://<id>.ngrok-free.app/incoming-call`).

## 3. Frontend Dashboard (The UI)
The web interface for managing campaigns and viewing logs.
```bash
# Terminal 3
cd ~/Documents/Superactive/dashboard
npm run dev
```
Access the dashboard at: [http://localhost:3000](http://localhost:3000)

---

### How it works:
- **Twilio** calls -> **Ngrok** -> **Server.py** (AI runs here)
- **Dashboard** -> **Server.py** (API calls to manage campaigns)

## Shutdown / Cleanup
If you need to force-stop everything (even if terminals are closed), run these commands:

### 1. Kill Backend (Python)
```bash
pkill -f "python.*server.py"
```

### 2. Kill Tunnel (Ngrok)
```bash
pkill -f ngrok
```

### 3. Kill Dashboard (Node/Next.js)
```bash
# Find and kill process on port 3000
lsof -ti:3000 | xargs kill -9
```
