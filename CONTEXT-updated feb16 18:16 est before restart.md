# Superactive — Session Context
> **Last updated:** Feb 16, 2026 at 6:01 PM EST

## Current State
**Phase 2 COMPLETE — AI brain wired up, not yet test-called.**

- Twilio phone: **+1 845-773-8193** (trial account)
- ngrok tunnel: `https://carlena-unadmonished-translationally.ngrok-free.dev`
- Pipeline: Google STT → Gemini 2.0 Flash (Vertex AI) → Google TTS (Chirp3 HD)
- Server: `server.py` on port 8765

## How to Restart (After PC Reboot)

```bash
cd /Users/maftaalif/Documents/Superactive
source venv/bin/activate

# 1. Start ngrok
ngrok http 8765 --log=stdout > ngrok.log &
sleep 2 && grep "url=" ngrok.log | tail -1

# 2. Update webhook with new ngrok URL
python setup_webhook.py

# 3. Start server
python -m uvicorn server:app --reload --port 8765

# 4. Call +1 845-773-8193
```

## File Inventory

| File | Purpose |
|---|---|
| `server.py` | Main server — full AI pipeline (STT → LLM → TTS) |
| `setup_webhook.py` | Auto-configures Twilio webhook to ngrok URL |
| `.env` | Twilio + GCP credentials |
| `service_account.json` | GCP service account key |
| `requirements.txt` | Python dependencies |
| `blueprint.md` | Full system architecture & business model |
| `task.md` | Task tracker |

## Google Cloud
- **$200** GCP credits + **$1,000** Gen AI App credits
- Project: `divine-apogee-480205-h8`
- Service account: `vertex-express@divine-apogee-480205-h8.iam.gserviceaccount.com`
- APIs enabled: Speech-to-Text, Text-to-Speech, Vertex AI
